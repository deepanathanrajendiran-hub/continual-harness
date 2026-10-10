import json
import subprocess
from pathlib import Path

import pytest

from bench.evo import config, patch, validate

TOML = """version = "1.0"
multi_step_reward_strategy = "mean"

[agent]
timeout_sec = 1800.0

[verifier]
timeout_sec = 900.0

[environment]
cpus = 2
memory_mb = 4096

[[steps]]
name = "round-1"

[[steps]]
name = "round-2"
"""
TAG = "evo-local/demo:9fcae3e5539d"


def cp(cmd, code=0, out=""):
    return subprocess.CompletedProcess(cmd, code, out, "")


def write_trial(trial: Path, rewards) -> None:
    """A Harbor multi-step trial; a None reward means the chain never reached that round."""
    trial.mkdir(parents=True)
    results = []
    for i, reward in enumerate(rewards, start=1):
        if reward is None:
            break
        name = f"round-{i}"
        verifier = trial / "steps" / name / "verifier"
        verifier.mkdir(parents=True)
        (verifier / "reward.txt").write_text(f"{reward}\n")
        (verifier / "test-stdout.txt").write_text(
            f"collected 4 items\nCASE_SUMMARY total_cases=4 success_count={4 if reward == 1 else 1}\n")
        results.append({"step_name": name, "verifier_result": {"rewards": {"reward": reward}}, "exception_info": None,
                        "agent_execution": {"started_at": "2026-10-09T10:00:00Z", "finished_at": "2026-10-09T10:01:00Z"}})
    (trial / "result.json").write_text(json.dumps({"trial_name": trial.name, "exception_info": None,
                                                   "step_results": results}))


class FakeHost:
    def __init__(self, rewards=None, arch="arm64", build_ok=True, ids=("sha256:img",), setup_sh=False):
        self.calls = []
        self.rewards = rewards or {"oracle": [1, 1], "nop": [0, 0], "planted": [1, 1]}
        self.arch, self.build_ok, self.ids = arch, build_ok, list(ids)
        self.setup_sh = setup_sh  # whether the image's working directory holds a project file named setup.sh

    def __call__(self, cmd, **kwargs):
        cmd = list(cmd)
        self.calls.append(cmd)
        if cmd[:2] == ["docker", "build"]:
            if not self.build_ok:
                raise subprocess.CalledProcessError(1, cmd)
            return cp(cmd)
        if cmd[:3] == ["docker", "image", "inspect"]:
            image_id = self.ids.pop(0) if len(self.ids) > 1 else self.ids[0]
            return cp(cmd, 0, json.dumps([{"Id": image_id, "Architecture": self.arch,
                                           "Config": {"WorkingDir": "/app", "User": ""}}]))
        if cmd[:2] == ["docker", "run"] and cmd[cmd.index("--entrypoint") + 1] == "test":
            return cp(cmd, 0 if self.setup_sh else 1)
        if cmd[:2] == ["docker", "run"]:
            return cp(cmd, 0, "3.10.12\n")
        if cmd[:2] == ["harbor", "run"]:
            job = cmd[cmd.index("--job-name") + 1]
            write_trial(Path(cmd[cmd.index("-o") + 1]) / job / "demo__AbCdEfG", self.rewards[job.split("__")[0]])
            return cp(cmd)
        return cp(cmd)

    def harbor_runs(self):
        return [(c[c.index("-a") + 1], Path(c[c.index("-p") + 1])) for c in self.calls if c[:2] == ["harbor", "run"]]


def make_task(runs: Path, name="demo") -> Path:
    task = runs / "dataset" / config.DATASET_REVISION / "tasks" / name
    (task / "environment").mkdir(parents=True)
    (task / "environment" / "Dockerfile").write_text("FROM ubuntu:22.04\nRUN apt-get update\n")
    (task / "task.toml").write_text(TOML)
    for step in ("round-1", "round-2"):
        for sub in ("tests", "solution"):
            (task / "steps" / step / sub).mkdir(parents=True)
        (task / "steps" / step / "instruction.md").write_text(f"Synthetic {step} request.\n")
        (task / "steps" / step / "tests" / "test.sh").write_text("#!/bin/bash\necho 1 > /logs/verifier/reward.txt\n")
        (task / "steps" / step / "solution" / "solve.sh").write_text(f"#!/bin/bash\necho {step}\n")
    return task


def test_check_command_runs_one_trial_with_the_evo_multiplier(tmp_path):
    assert validate.check_command(tmp_path / "copy", "oracle", "oracle__demo", tmp_path / "checks") == [
        "harbor", "run", "-p", str(tmp_path / "copy"), "-a", "oracle",
        "--agent-timeout-multiplier", "1.0", "--no-force-build", "-n", "1", "-k", "1", "-r", "0",
        "-o", str(tmp_path / "checks"), "--job-name", "oracle__demo", "-y"]


def test_happy_path_validates_every_round_and_writes_the_record(tmp_path):
    make_task(tmp_path)
    host = FakeHost()
    out = validate.validate_task("demo", runs=tmp_path, run=host)
    assert out["ok"], out["reason"]
    assert (out["rounds"], out["oracle"], out["nop"], out["planted"]) == (2, [1.0, 1.0], [0.0, 0.0], [1.0, 1.0])
    assert (out["image_tag"], out["image_id"], out["arch"], out["workdir"]) == (TAG, "sha256:img", "arm64", "/app")
    assert out["oracle_cases"] == [[4, 4], [4, 4]] and out["python"]["ok"]
    assert out["arm_patch"] == {"changed": [], "artifacts": [], "added": [validate.copies.PYTHON_LINE]}
    assert len(out["copy_digest"]) == 64 and len(out["validation_copy_digest"]) == 64
    assert json.loads((tmp_path / "validation" / "demo.json").read_text()) == out
    copies = tmp_path / "copies"
    assert not list((copies / "agent" / "demo").rglob("solution"))
    assert (copies / "validation" / "demo" / "steps" / "round-2" / "solution" / "solve.sh").is_file()
    assert host.harbor_runs() == [("oracle", copies / "validation" / "demo"), ("nop", copies / "validation" / "demo"),
                                  ("oracle", copies / "planted" / "demo")]
    assert ["docker", "build", "--platform", "linux/arm64", "-t", TAG,
            str(copies / "validation" / "demo" / "environment")] in host.calls


def test_planted_copy_wraps_round_one_only(tmp_path):
    src = make_task(tmp_path)
    dest = tmp_path / "planted"
    digest = validate.planted_copy(src, dest, "/work space/", "round-1")
    solution = dest / "steps" / "round-1" / "solution"
    wrapper = (solution / "solve.sh").read_text()
    assert len(digest) == 64
    assert "mkdir -p '/work space/.claude/harness'" in wrapper
    assert "cp -R /solution/horizon-ledger/. '/work space/.claude/harness'/" in wrapper
    assert "/solution/solve.orig.sh" in wrapper and (solution / "solve.sh").stat().st_mode & 0o111
    assert (solution / "solve.orig.sh").read_text() == "#!/bin/bash\necho round-1\n"
    planted = sorted(p.relative_to(solution / "horizon-ledger").as_posix()
                     for p in (solution / "horizon-ledger").rglob("*") if p.is_file())
    assert planted == sorted(validate.PLANTED_LEDGER)
    assert any(p.startswith("goals/") for p in planted) and any("test" in p for p in planted)
    assert (dest / "steps" / "round-2" / "solution" / "solve.sh").read_text() == "#!/bin/bash\necho round-2\n"
    assert (src / "steps" / "round-1" / "solution" / "solve.sh").read_text() == "#!/bin/bash\necho round-1\n"


def test_a_passing_nop_round_fails_the_task(tmp_path):
    make_task(tmp_path)
    out = validate.validate_task("demo", runs=tmp_path,
                                 run=FakeHost(rewards={"oracle": [1, 1], "nop": [0, 1], "planted": [1, 1]}))
    assert not out["ok"] and "nop rewards [0.0, 1.0]" in out["reason"]


def test_an_oracle_chain_that_stops_early_fails_the_task(tmp_path):
    make_task(tmp_path)
    out = validate.validate_task("demo", runs=tmp_path,
                                 run=FakeHost(rewards={"oracle": [1, None], "nop": [0, 0], "planted": [1, 1]}))
    assert not out["ok"] and out["oracle"] == [1.0, None] and "oracle rewards" in out["reason"]


def test_a_failing_planted_round_fails_the_task(tmp_path):
    make_task(tmp_path)
    out = validate.validate_task("demo", runs=tmp_path,
                                 run=FakeHost(rewards={"oracle": [1, 1], "nop": [0, 0], "planted": [1, 0]}))
    assert not out["ok"] and "planted rewards [1.0, 0.0]" in out["reason"]


def test_a_nop_run_without_any_graded_round_fails_the_task(tmp_path):
    make_task(tmp_path)
    out = validate.validate_task("demo", runs=tmp_path,
                                 run=FakeHost(rewards={"oracle": [1, 1], "nop": [None, None], "planted": [1, 1]}))
    assert not out["ok"] and "nop rewards [None, None]" in out["reason"]


def test_build_failure_stops_before_any_harbor_run(tmp_path):
    make_task(tmp_path)
    host = FakeHost(build_ok=False)
    out = validate.validate_task("demo", runs=tmp_path, run=host)
    assert not out["ok"] and out["reason"].startswith("build failed")
    assert host.harbor_runs() == []


def test_an_amd64_image_stops_before_any_harbor_run(tmp_path):
    make_task(tmp_path)
    host = FakeHost(arch="amd64")
    out = validate.validate_task("demo", runs=tmp_path, run=host)
    assert not out["ok"] and out["reason"] == "architecture amd64, expected arm64"
    assert host.harbor_runs() == []


def test_an_unknown_arch_pattern_is_recorded(tmp_path, monkeypatch):
    make_task(tmp_path)

    def refuse(*args, **kwargs):
        raise patch.UnknownArchPattern("RUN curl -LO https://example.invalid/tool_amd64.deb")

    monkeypatch.setattr(validate.copies, "make_copy", refuse)
    host = FakeHost()
    out = validate.validate_task("demo", runs=tmp_path, run=host)
    assert not out["ok"] and out["reason"].startswith("copy failed: RUN curl")
    assert host.calls == []


def test_an_image_that_changes_during_checks_fails_the_task(tmp_path):
    make_task(tmp_path)
    out = validate.validate_task("demo", runs=tmp_path, run=FakeHost(ids=("sha256:one", "sha256:two")))
    assert not out["ok"] and "image ID changed during checks" in out["reason"]


def test_revalidation_starts_from_clean_copies_and_jobs(tmp_path):
    make_task(tmp_path)
    validate.validate_task("demo", runs=tmp_path, run=FakeHost())
    out = validate.validate_task("demo", runs=tmp_path, run=FakeHost())
    assert out["ok"], out["reason"]


def ok_record(task, ok=True, reason=None):
    return {"task": task, "ok": ok, "reason": reason, "code": validate.CODE_DIGEST, "python": {"ok": True}}


def test_validate_in_order_replaces_a_failed_task_with_the_next_one(tmp_path, monkeypatch):
    (tmp_path / "validation").mkdir()
    (tmp_path / "validation" / "a.json").write_text(json.dumps(ok_record("a")))
    seen = []

    def fake_validate(task, *, runs, run):
        seen.append(task)
        out = ok_record(task, ok=task != "b", reason="nop rewards [1.0]" if task == "b" else None)
        (runs / "validation" / f"{task}.json").write_text(json.dumps(out))
        return out

    monkeypatch.setattr(validate, "validate_task", fake_validate)
    host, lines = FakeHost(), []
    summary = validate.validate_in_order(["a", "b", "c", "d"], 2, runs=tmp_path, run=host, log=lines.append)
    assert seen == ["b", "c"]
    assert summary["selected"] == ["a", "c"] and summary["complete"]
    assert summary["swaps"] == [{"dropped": "b", "reason": "nop rewards [1.0]", "replaced_by": "c"}]
    assert [w["task"] for w in summary["walked"]] == ["a", "b", "c"]
    assert ["docker", "image", "rm", "-f", config.image_tag("b")] in host.calls
    assert any("b" in line and "c" in line for line in lines)
    assert json.loads((tmp_path / "validation" / "summary.json").read_text()) == summary


def test_validate_in_order_reports_an_incomplete_walk(tmp_path, monkeypatch):
    monkeypatch.setattr(validate, "validate_task",
                        lambda task, *, runs, run: ok_record(task, ok=False, reason="build failed"))
    summary = validate.validate_in_order(["a", "b", "c"], 2, runs=tmp_path, run=FakeHost(), log=lambda m: None)
    assert summary["selected"] == [] and not summary["complete"]
    assert summary["swaps"] == [{"dropped": "a", "reason": "build failed", "replaced_by": None},
                                {"dropped": "b", "reason": "build failed", "replaced_by": None}]


def test_main_walks_the_saved_order_under_the_runner_lock(tmp_path, monkeypatch, capsys):
    (tmp_path / "order.json").write_text(json.dumps({"seed": 20261009, "order": ["a", "b"], "arm_orders": {}}))
    got = {}

    def fake_walk(order, n, *, runs, run=None, log=None):
        got.update(order=order, n=n, runs=runs, locked=(runs / "runner.lock").exists())
        return {"selected": order[:n], "swaps": [], "complete": True}

    monkeypatch.setattr(validate, "validate_in_order", fake_walk)
    assert validate.main(["--runs", str(tmp_path), "--n", "2"]) == 0
    assert got == {"order": ["a", "b"], "n": 2, "runs": tmp_path, "locked": True}
    assert json.loads(capsys.readouterr().out) == {"selected": ["a", "b"], "swaps": [], "complete": True,
                                                "python_missing": []}


def test_main_validates_one_named_task(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(validate, "validate_task", lambda task, *, runs, run=None: ok_record(task, ok=False,
                                                                                            reason="x"))
    assert validate.main(["--runs", str(tmp_path), "--task", "walk"]) == 1
    assert json.loads(capsys.readouterr().out) == {"task": "walk", "ok": False, "reason": "x"}


def test_a_selected_task_whose_image_lacks_python_310_is_named_in_the_summary(tmp_path):
    make_task(tmp_path)

    class NoPython(FakeHost):
        def __call__(self, cmd, **kwargs):
            if list(cmd)[:2] == ["docker", "run"]:
                self.calls.append(list(cmd))
                return cp(cmd, 127, "sh: 1: python3: not found\n")
            return super().__call__(cmd, **kwargs)

    summary = validate.validate_in_order(["demo"], 1, runs=tmp_path, run=NoPython(), log=lambda m: None)
    record = json.loads((tmp_path / "validation" / "demo.json").read_text())
    assert record["ok"] is True and record["python"]["ok"] is False
    assert summary["selected"] == ["demo"] and summary["python_missing"] == ["demo"]


def test_a_transient_build_failure_is_retried_once(tmp_path):
    make_task(tmp_path)

    class Flaky(FakeHost):
        builds = 0

        def __call__(self, cmd, **kwargs):
            if list(cmd)[:2] == ["docker", "build"]:
                self.builds += 1
                if self.builds == 1:
                    self.calls.append(list(cmd))
                    raise subprocess.CalledProcessError(1, cmd)
            return super().__call__(cmd, **kwargs)

    host = Flaky()
    out = validate.validate_task("demo", runs=tmp_path, run=host)
    assert out["ok"], out["reason"]
    assert host.builds == 2


def test_a_saved_record_made_by_other_copy_code_is_validated_again(tmp_path, monkeypatch):
    (tmp_path / "validation").mkdir()
    (tmp_path / "validation" / "a.json").write_text(json.dumps(
        {"task": "a", "ok": False, "reason": "copy failed: line 3: bundled amd64 file", "code": "older"}))
    seen = []

    def fake_validate(task, *, runs, run):
        seen.append(task)
        return {"task": task, "ok": True, "reason": None, "code": validate.CODE_DIGEST, "python": {"ok": True}}

    monkeypatch.setattr(validate, "validate_task", fake_validate)
    summary = validate.validate_in_order(["a"], 1, runs=tmp_path, run=FakeHost(), log=lambda m: None)
    assert seen == ["a"] and summary["selected"] == ["a"]


def test_planted_ledger_goes_to_the_task_toml_workdir_when_it_overrides_the_image(tmp_path):
    task = make_task(tmp_path)
    (task / "task.toml").write_text(TOML.replace("memory_mb = 4096", 'memory_mb = 4096\nworkdir = "/srv/app"'))
    out = validate.validate_task("demo", runs=tmp_path, run=FakeHost())
    assert out["ok"], out["reason"]
    assert out["workdir"] == "/srv/app"
    wrapper = (tmp_path / "copies" / "planted" / "demo" / "steps" / "round-1" / "solution" / "solve.sh").read_text()
    assert "mkdir -p /srv/app/.claude/harness" in wrapper


class ImageUser(FakeHost):
    """An image whose configured USER is `user`."""

    def __init__(self, user, **kwargs):
        super().__init__(**kwargs)
        self.user = user

    def __call__(self, cmd, **kwargs):
        if list(cmd)[:3] == ["docker", "image", "inspect"]:
            self.calls.append(list(cmd))
            return cp(cmd, 0, json.dumps([{"Id": "sha256:img", "Architecture": "arm64",
                                           "Config": {"WorkingDir": "/app", "User": self.user}}]))
        return super().__call__(cmd, **kwargs)


def test_the_user_each_step_runs_as_is_recorded(tmp_path):
    # Harbor 0.24.0 runs a step's setup.sh and agent as [steps.agent].user, else [agent].user, else the image USER
    task = make_task(tmp_path)
    step_user = TOML.replace('name = "round-2"\n', 'name = "round-2"\n\n[steps.agent]\nuser = "app"\n')
    (task / "task.toml").write_text(step_user)
    out = validate.validate_task("demo", runs=tmp_path, run=FakeHost())
    assert out["ok"], out["reason"]
    assert out["user"] == ["app", "root"]
    (task / "task.toml").write_text(step_user.replace("timeout_sec = 1800.0\n", 'timeout_sec = 1800.0\nuser = "app"\n'))
    assert validate.validate_task("demo", runs=tmp_path, run=FakeHost())["user"] == ["app"]
    (task / "task.toml").write_text(TOML.replace("timeout_sec = 1800.0\n", "timeout_sec = 1800.0\nuser = 0\n"))
    assert validate.validate_task("demo", runs=tmp_path, run=ImageUser("app"))["user"] == ["root"]


def test_a_task_that_sets_no_user_records_the_image_user(tmp_path):
    make_task(tmp_path)
    for image_user, expected in (("", ["root"]), ("0", ["root"]), ("root", ["root"]), ("1000:1000", ["1000:1000"])):
        assert validate.validate_task("demo", runs=tmp_path, run=ImageUser(image_user))["user"] == expected

def test_a_user_with_a_root_group_suffix_is_root():
    for user in ("0:0", "root:root", "root:0"):
        assert validate.agent_users({"agent": {"user": user}}, "app") == ["root"]
    assert validate.agent_users({"agent": {"user": "1000:0"}}, "") == ["1000:0"]


def test_the_code_digest_covers_every_module_that_makes_or_judges_a_copy():
    import hashlib

    here = Path(validate.__file__).resolve().parent
    assert validate.CODE_FILES == ("copies.py", "images.py", "patch.py", "steps.py", "validate.py")
    assert validate.CODE_DIGEST == hashlib.sha256(b"".join((here / n).read_bytes() for n in validate.CODE_FILES)).hexdigest()

SETUP_SH_REASON = "project file setup.sh in the working directory would be overwritten by the round hook"


def setup_sh_probe(workdir):
    return ["docker", "run", "--rm", "--platform", "linux/arm64", "--entrypoint", "test", TAG, "-e",
            f"{workdir}/setup.sh"]


def test_a_project_setup_sh_in_the_working_directory_fails_the_task_before_any_harbor_job(tmp_path):
    # Harbor uploads steps/<r>/workdir/setup.sh over it before every round, and the hook then deletes itself
    task = make_task(tmp_path)
    host = FakeHost(setup_sh=True)
    out = validate.validate_task("demo", runs=tmp_path, run=host)
    assert (out["ok"], out["reason"]) == (False, SETUP_SH_REASON)
    assert setup_sh_probe("/app") in host.calls and host.harbor_runs() == []
    (task / "task.toml").write_text(TOML.replace("memory_mb = 4096", 'memory_mb = 4096\nworkdir = "/srv/app"'))
    host = FakeHost()
    assert validate.validate_task("demo", runs=tmp_path, run=host)["ok"]
    assert setup_sh_probe("/srv/app") in host.calls


@pytest.mark.parametrize("name", ["", "..", "../victim", "a/b", "a\\b", "ABSOLUTE"])
def test_a_task_name_that_is_not_a_bare_directory_name_is_refused_before_anything_is_deleted(tmp_path, name):
    runs = tmp_path / "runs"
    outside, inside = tmp_path / "victim", runs / "copies" / "victim"
    for victim in (outside, inside):
        victim.mkdir(parents=True)
        (victim / "keep.txt").write_text("kept\n")
    name = str(outside) if name == "ABSOLUTE" else name
    host = FakeHost()
    with pytest.raises(ValueError, match="task name"):
        validate.validate_task(name, runs=runs, run=host)
    with pytest.raises(ValueError, match="task name"):
        validate.main(["--runs", str(runs), "--task", name])
    assert host.calls == []
    assert (outside / "keep.txt").is_file() and (inside / "keep.txt").is_file()
    assert (runs / "copies").is_dir()
