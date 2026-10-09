import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from bench.evo import config, copies, order, prereg, validate
from bench.tb4 import bundle, copies as tb4_copies


def cp(cmd, code=0, out=""):
    return subprocess.CompletedProcess(cmd, code, out, "")


def sha(data) -> str:
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


ORDER = order.seeded_order(config.POOL, config.SEED, config.DOMAINS)
TIMING_8 = {"m_control": 20.0, "m_horizon": 25.0, "rounds": {"control": 5, "horizon": 5}, "n": 8}
PIN = {"revision": config.DATASET_REVISION, "sha256": "a" * 64, "lfs_oid": "a" * 64,
       "url": "https://huggingface.co/x", "fetched_at": "2026-10-09T12:00:00Z"}
BUNDLE = {"commit": config.BUNDLE_COMMIT, "modules": list(config.BUNDLE_MODULES),
          "files": {"horizon/SKILL.md": "1" * 64, "horizon/scripts/reviewing.py": "2" * 64}}
OBSERVED = {"harbor": config.HARBOR_VERSION, "claude (host)": "2.1.293 (Claude Code)",
            "docker server": "29.0.0", "docker arch": "aarch64", "python (host)": "3.14.4"}
CODE = {"bench/evo/config.py": "3" * 64}


def check(job, attempt=1, ok=True, failures=(), **extra):
    return {"job_name": f"{job}__a{attempt}", "attempt": attempt, "ok": ok, "failures": list(failures),
            "sha256": sha(job), **extra}


PILOT = {job: check(job) for job in prereg.PILOT_JOBS}
PILOT["check__dummy-probe__control"] = check("check__dummy-probe__control", ok=None,
                                             recorded={"round_2_started": True, "round_1_reward": 0.0})


def infos(sixty=()):
    return {t: {"task": t, "dir": f"/data/{t}", "rounds": 10, "step_names": [f"round-{i}" for i in range(1, 11)],
                "agent_timeout_sec": 3600.0 if t in sixty else 1800.0, "verifier_timeout_sec": 900.0,
                "reward_strategy": "mean"} for t in ORDER}


def valid(task, rounds=10, **changes):
    record = {"task": task, "copy_digest": sha(task), "image_id": "sha256:" + sha("image " + task),
              "arch": "arm64", "rounds": rounds, "oracle": [1.0] * rounds, "nop": [0.0] * rounds,
              "planted": [1.0] * rounds, "ok": True, "reason": None, "code": validate.CODE_DIGEST}
    record.update(changes)
    return record


def payload():
    return {"seed": config.SEED, "algorithm": "domain round-robin", "order": list(ORDER),
            "arm_orders": {t: list(order.arm_order(t, config.SEED)) for t in ORDER}}


def make(n=8, validations=None, timing=TIMING_8, task_infos=None, order_payload=None, **changes):
    kwargs = {"task_infos": task_infos or infos(), "bundle": BUNDLE, "pin": PIN, "observed": OBSERVED,
              "code": CODE, "pilot": PILOT}
    kwargs.update(changes)
    validations = {t: valid(t) for t in ORDER} if validations is None else validations
    return prereg.collect(n, order_payload or payload(), validations, timing, **kwargs)


def test_collect_takes_the_first_n_ok_tasks_in_the_seeded_order():
    validations = {t: valid(t) for t in ORDER}
    validations[ORDER[1]] = valid(ORDER[1], ok=False, reason="nop reward 1.0 in round-3")
    out = make(validations=validations, task_infos=infos(sixty={ORDER[2]}))
    assert out["n"] == 8 and out["tasks"] == [ORDER[0]] + ORDER[2:9]
    assert out["replaced"] == [{"task": ORDER[1], "reason": "nop reward 1.0 in round-3"}]
    assert out["arm_orders"] == {t: list(order.arm_order(t, config.SEED)) for t in out["tasks"]}
    third = out["task_details"][ORDER[2]]
    assert (third["order"], third["rounds"], third["minutes"]) == (3, 10, 60)
    assert third["image_id"] == validations[ORDER[2]]["image_id"]
    assert third["image_tag"] == config.image_tag(ORDER[2])
    assert third["copy_digest"] == validations[ORDER[2]]["copy_digest"]
    assert out["task_details"][ORDER[0]]["minutes"] == 30
    assert sorted(out["prompts"]["texts"]) == ["control@30", "control@60", "horizon@30", "horizon@60"]
    assert out["prompts"]["texts"]["horizon@60"] == config.prompt_text("horizon", 60)
    assert out["prompts"]["text_sha256"]["control@30"] == sha(config.prompt_text("control", 30))
    assert out["n_rule"]["m_control"] == 20.0 and out["n_rule"]["n"] == 8
    assert out["analysis"] == "exact sign-flip permutation, two-sided, alpha 0.05"
    assert out["dataset"]["pin"] == PIN and out["bundle"] == BUNDLE and out["pilot"] == PILOT
    assert out["spec"]["path"] == prereg.SPEC
    assert out["spec"]["sha256"] == sha((config.REPO_ROOT / prereg.SPEC).read_bytes())


def test_collect_needs_no_validation_beyond_the_nth_ok_task():
    validations = {t: valid(t) for t in ORDER[:6]}
    assert make(n=6, validations=validations, timing={"m_control": 30.0, "m_horizon": 30.0})["tasks"] == ORDER[:6]


def test_collect_is_deterministic_and_survives_json():
    first, second = make(), make()
    assert first == second == json.loads(json.dumps(first))


def broken(case):
    validations = {t: valid(t) for t in ORDER}
    if case == "unvalidated task inside the window":
        del validations[ORDER[3]]
        return {"validations": validations}
    if case == "too few ok tasks":
        return {"validations": {t: valid(t, ok=t in ORDER[:7]) for t in ORDER}}
    if case == "ok claimed but a nop round passes":
        validations[ORDER[0]] = valid(ORDER[0], nop=[0.0] * 9 + [1.0])
        return {"validations": validations}
    if case == "ok claimed on amd64":
        validations[ORDER[0]] = valid(ORDER[0], arch="amd64")
        return {"validations": validations}
    if case == "validated by older copy code":
        validations[ORDER[0]] = valid(ORDER[0], code="older")
        return {"validations": validations}
    if case == "ok claimed with a missing round":
        validations[ORDER[0]] = valid(ORDER[0], oracle=[1.0] * 9 + [None])
        return {"validations": validations}
    return {
        "n differs from the rule": {"n": 10},
        "no fit at all": {"n": 6, "timing": {"m_control": 40.0, "m_horizon": 40.0}},
        "a dry arm without minutes": {"timing": {"m_control": 20.0, "m_horizon": None}},
        "order not seeded": {"order_payload": dict(payload(), order=list(reversed(ORDER)))},
        "arm order changed": {"order_payload": dict(payload(), arm_orders={t: ["horizon", "control"] for t in ORDER})},
        "pin mismatch": {"pin": dict(PIN, lfs_oid="b" * 64)},
        "pin of another revision": {"pin": dict(PIN, revision="main")},
        "task missing from the dataset": {"task_infos": {t: i for t, i in infos().items() if t != ORDER[5]}},
        "another harbor": {"observed": dict(OBSERVED, harbor="0.25.0")},
        "bundle from another commit": {"bundle": dict(BUNDLE, commit="2f65f2a24d753b6875bd126fc989335baff82ed8")},
        "bundle without reviewing": {"bundle": dict(BUNDLE, files={"horizon/SKILL.md": "1" * 64})},
        "pilot check missing": {"pilot": {k: v for k, v in PILOT.items() if k != "canary__dummy__horizon"}},
        "pilot check failed": {"pilot": dict(PILOT, canary__dummy__horizon=check(
            "canary__dummy__horizon", ok=False, failures=["no Write tool call created the file without an error"]))},
    }[case]


@pytest.mark.parametrize("case", [
    "unvalidated task inside the window", "too few ok tasks", "ok claimed but a nop round passes",
    "ok claimed on amd64", "ok claimed with a missing round", "validated by older copy code", "n differs from the rule", "no fit at all",
    "a dry arm without minutes", "order not seeded", "arm order changed", "pin mismatch",
    "pin of another revision", "task missing from the dataset", "another harbor", "bundle from another commit",
    "bundle without reviewing", "pilot check missing", "pilot check failed"])
def test_collect_refuses_inputs_that_break_the_protocol(case):
    with pytest.raises(prereg.FreezeError):
        make(**broken(case))


def test_n_from_timing():
    assert prereg.n_from_timing(TIMING_8) == 8
    assert prereg.n_from_timing({"m_control": 15.0, "m_horizon": 20.0}) == 10
    for timing in ({"m_control": 40.0, "m_horizon": 40.0}, {"m_control": None, "m_horizon": 1.0}, {}):
        with pytest.raises(prereg.FreezeError):
            prereg.n_from_timing(timing)


def test_prompt_digest_is_of_the_file_write_prompt_makes():
    data = (config.prompt_text("horizon", 30) + "\n").encode()
    assert prereg.prompt_file_digest("horizon", 30) == sha(data)

    def wrong(dest, arm, minutes):
        Path(dest).write_text("Do something else.\n")
        return Path(dest)

    with pytest.raises(prereg.FreezeError):
        prereg.prompt_file_digest("control", 30, write=wrong)


def test_write_renders_both_files(tmp_path):
    out = make(task_infos=infos(sixty={ORDER[0]}))
    json_path, md_path = prereg.write(out, tmp_path / "docs")
    assert json.loads(json_path.read_text()) == out
    text = md_path.read_text()
    for task in out["tasks"]:
        assert f"`{task}`" in text
    for key, prompt in out["prompts"]["texts"].items():
        assert all(paragraph in text for paragraph in prompt.split("\n\n"))
        assert out["prompts"]["text_sha256"][key] in text and out["prompts"]["file_sha256"][key] in text
    for needle in ("N = 8", "evo-prereg", "exact sign-flip permutation, two-sided, alpha 0.05", config.BUNDLE_COMMIT,
                   "../../superpowers/specs/2026-10-09-evocode-horizon-design.md", PIN["sha256"],
                   "`canary__dummy__horizon__a1`", "round_2_started", out["task_details"][ORDER[0]]["image_id"]):
        assert needle in text
    assert "None" not in text.replace("None of", "")


def test_build_bundle_builds_then_verifies(tmp_path):
    runs = tmp_path / "runs"
    manifest = prereg.build_bundle(runs)
    assert manifest["commit"] == config.BUNDLE_COMMIT and manifest["modules"] == list(config.BUNDLE_MODULES)
    assert len(manifest["files"]) == 12 and "horizon/scripts/reviewing.py" in manifest["files"]
    assert json.loads((runs / "bundle-manifest.json").read_text()) == manifest
    assert prereg.build_bundle(runs) == manifest
    (runs / "bundle" / "horizon" / "scripts" / "reviewing.py").write_text("# edited\n")
    with pytest.raises(prereg.BundleMismatch, match="reviewing.py"):
        prereg.build_bundle(runs)


def test_build_bundle_refuses_extra_files(tmp_path):
    prereg.build_bundle(tmp_path)
    (tmp_path / "bundle" / "horizon" / "scripts" / "__pycache__").mkdir()
    (tmp_path / "bundle" / "horizon" / "scripts" / "__pycache__" / "goal.cpython-312.pyc").write_bytes(b"x")
    with pytest.raises(prereg.BundleMismatch, match="pyc"):
        prereg.build_bundle(tmp_path)


def git(repo, *args):
    # every GIT_* variable is dropped: a git hook exports GIT_DIR, which would point these commits and the
    # evo-prereg tag at the real repository instead of the temporary one
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           *args], capture_output=True, text=True, check=True, env=env).stdout


def test_code_digests_hash_tracked_code_and_refuse_uncommitted_changes(tmp_path):
    repo = tmp_path / "repo with space "
    (repo / "bench" / "evo").mkdir(parents=True)
    (repo / "bench" / "tb4").mkdir()
    (repo / "bench" / "evo" / "a.py").write_text("A = 1\n")
    (repo / "bench" / "tb4" / "b.py").write_text("B = 2\n")
    (repo / "README.md").write_text("not code\n")
    git(tmp_path, "init", "-q", str(repo))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "code")
    assert prereg.code_digests(repo) == {"bench/evo/a.py": sha("A = 1\n"), "bench/tb4/b.py": sha("B = 2\n")}
    (repo / "README.md").write_text("changed, but not code\n")
    assert len(prereg.code_digests(repo)) == 2
    (repo / "bench" / "evo" / "new.py").write_text("")
    with pytest.raises(prereg.FreezeError, match="new.py"):
        prereg.code_digests(repo)
    (repo / "bench" / "evo" / "new.py").unlink()
    (repo / "bench" / "tb4" / "b.py").write_text("B = 3\n")
    with pytest.raises(prereg.FreezeError, match="b.py"):
        prereg.code_digests(repo)


def fake_git(tag="abc", prereg_at_tag=True, ancestor=True, diff_clean=True, dirty="", report_tracked=False):
    def fake(cmd, **kwargs):
        sub = cmd[3]
        if sub == "rev-parse":
            return cp(cmd, 0 if tag else 1, tag + "\n" if tag else "")
        if sub == "cat-file":
            return cp(cmd, 0 if prereg_at_tag else 128)
        if sub == "merge-base":
            return cp(cmd, 0 if ancestor else 1)
        if sub == "diff":
            return cp(cmd, 0 if diff_clean else 1)
        if sub == "status":
            return cp(cmd, 0, dirty)
        if sub == "ls-files":
            return cp(cmd, 0 if report_tracked else 1)
        raise AssertionError(cmd)
    return fake


def test_require_freeze_accepts_a_descendant_with_the_frozen_paths_unchanged():
    calls = []

    def recording(cmd, **kwargs):
        calls.append(cmd)
        return fake_git()(cmd, **kwargs)

    assert prereg.require_freeze(recording) == "abc"
    diff = next(c for c in calls if c[3] == "diff")
    # the code, the record, and what the post-run steps read: the judge rubric, the spec and prereg.md
    assert diff[4:] == ["--quiet", "abc", "HEAD", "--", "bench/evo", "bench/tb4",
                        "docs/evaluations/evocode-horizon/prereg.json",
                        "docs/evaluations/tb4-horizon-pilot/prompts/judge.md",
                        "docs/superpowers/specs/2026-10-09-evocode-horizon-design.md",
                        "docs/evaluations/evocode-horizon/prereg.md"]
    assert ["refs/tags/evo-prereg^{commit}"] == [c[-1] for c in calls if c[3] == "rev-parse"]


@pytest.mark.parametrize("kwargs", [
    {"tag": ""}, {"prereg_at_tag": False}, {"ancestor": False}, {"diff_clean": False},
    {"dirty": " M bench/evo/run.py\n"}, {"dirty": "?? bench/evo/extra.py\n"}, {"report_tracked": True}])
def test_require_freeze_refuses(kwargs):
    with pytest.raises(prereg.NotFrozen):
        prereg.require_freeze(fake_git(**kwargs))


def runs_dir(tmp_path, timing=TIMING_8):
    runs = tmp_path / "runs"
    order.write_order(runs / "order.json")
    (runs / "timing.json").write_text(json.dumps(timing))
    base = runs / "dataset" / config.DATASET_REVISION
    base.mkdir(parents=True)
    (base / "PIN.json").write_text(json.dumps(PIN))
    (runs / "validation").mkdir()
    for task in ORDER[:9]:
        (runs / "validation" / f"{task}.json").write_text(json.dumps(valid(task, ok=task != ORDER[4],
                                                                           reason="build failed")))
    (runs / "validation" / "summary.json").write_text(json.dumps({"selected": []}))
    findings = [(job, 1, None if job in prereg.RECORDED_ONLY else True)
                for job in prereg.PILOT_JOBS if job != "canary__dummy__horizon"]
    findings += [("canary__dummy__horizon", 1, False), ("canary__dummy__horizon", 2, False),
                 ("canary__dummy__horizon", 10, True)]
    for job, attempt, ok in findings:
        path = runs / "checks" / f"{job}__a{attempt}" / "findings.json"
        path.parent.mkdir(parents=True)
        data = {"job_name": f"{job}__a{attempt}", "ok": ok, "failures": [] if ok is not False else ["x"],
                "facts": {"pwd": "/app"}}
        if ok is None:
            data["recorded"] = {"round_2_started": True}
        path.write_text(json.dumps(data))
    (runs / "checks" / "check__dummy__oracle__a1" / "harbor.log").write_text("log\n")
    return runs


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(prereg.dataset, "list_tasks", lambda root: list(infos().values()))
    monkeypatch.setattr(prereg, "build_bundle", lambda runs: BUNDLE)
    monkeypatch.setattr(prereg, "observed_versions", lambda run=None: OBSERVED)
    monkeypatch.setattr(prereg, "code_digests", lambda repo=None, run=None: CODE)
    monkeypatch.setattr(prereg, "frozen_commit", lambda run=None, repo=None: None)


def test_main_write_collects_from_the_run_directory(tmp_path, offline, capsys):
    runs, docs = runs_dir(tmp_path), tmp_path / "docs"
    (runs / "validation" / f"{ORDER[9]}.json").write_text(json.dumps(valid(ORDER[9])))
    assert prereg.main(["write", "--runs", str(runs), "--docs", str(docs)]) == 0
    printed = json.loads(capsys.readouterr().out)
    expected = ORDER[:4] + ORDER[5:9]
    assert printed["n"] == 8 and printed["tasks"] == expected and printed["reserve"] == [ORDER[9]]
    assert printed["replaced"] == [{"task": ORDER[4], "reason": "build failed"}]
    saved = json.loads((docs / "prereg.json").read_text())
    assert saved["tasks"] == expected and saved["pilot"]["check__dummy-probe__control"]["recorded"]
    assert saved["pilot"]["canary__dummy__horizon"]["attempt"] == 10
    assert (docs / "prereg.md").is_file()


def test_main_write_refuses_a_failed_latest_check(tmp_path, offline, capsys):
    runs = runs_dir(tmp_path)
    assert prereg.main(["write", "--runs", str(runs), "--docs", str(tmp_path / "docs")]) == 0
    capsys.readouterr()
    path = runs / "checks" / "canary__dummy__horizon__a11" / "findings.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"job_name": "canary__dummy__horizon__a11", "ok": False, "failures": ["refused"]}))
    assert prereg.main(["write", "--runs", str(runs), "--docs", str(tmp_path / "docs")]) == 1
    assert "canary__dummy__horizon__a11" in capsys.readouterr().err


def test_main_write_stops_when_the_rule_does_not_fit(tmp_path, offline, capsys):
    runs = runs_dir(tmp_path, timing={"m_control": 45.0, "m_horizon": 50.0})
    assert prereg.main(["write", "--runs", str(runs), "--docs", str(tmp_path / "docs")]) == 1
    assert "even N = 6 does not fit" in capsys.readouterr().err
    assert not (tmp_path / "docs").exists()


def test_main_write_names_a_missing_input(tmp_path, offline, capsys):
    runs = runs_dir(tmp_path)
    (runs / "timing.json").unlink()
    assert prereg.main(["write", "--runs", str(runs), "--docs", str(tmp_path / "docs")]) == 1
    assert "timing.json" in capsys.readouterr().err


def test_main_write_refuses_after_the_tag(tmp_path, offline, monkeypatch, capsys):
    monkeypatch.setattr(prereg, "frozen_commit", lambda run=None, repo=None: "abc")
    assert prereg.main(["write", "--runs", str(runs_dir(tmp_path)), "--docs", str(tmp_path / "docs")]) == 1
    assert "already frozen at abc" in capsys.readouterr().err


def test_main_check_and_bundle(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(prereg, "require_freeze", lambda run=None: "abc")
    assert prereg.main(["check"]) == 0
    assert json.loads(capsys.readouterr().out) == {"frozen": "abc"}

    def refuse(run=None):
        raise prereg.NotFrozen("tag evo-prereg is missing")

    monkeypatch.setattr(prereg, "require_freeze", refuse)
    assert prereg.main(["check"]) == 1
    assert "tag evo-prereg is missing" in capsys.readouterr().err
    monkeypatch.setattr(prereg, "build_bundle", lambda runs: BUNDLE)
    assert prereg.main(["bundle", "--runs", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == {"commit": config.BUNDLE_COMMIT, "files": 2,
                                                   "skill": str(tmp_path / "bundle" / "horizon")}


# Freeze pins: they run once prereg.json exists or the evo-prereg tag does, and pin the record to the repository.
PREREG = config.DOCS / "prereg.json"
frozen = pytest.mark.skipif(not PREREG.exists() and prereg.frozen_commit() is None,
                            reason="before the freeze: no prereg.json and no evo-prereg tag")


def _repo_git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(config.REPO_ROOT), *args], capture_output=True)


def _blob(path: str) -> bytes:
    """A repository file as frozen: at the tag once it exists, else in the working tree."""
    tag = prereg.frozen_commit()
    if tag is None:
        return (config.REPO_ROOT / path).read_bytes()
    proc = _repo_git("show", f"{tag}:{path}")
    assert proc.returncode == 0, f"{path} is not in {config.FREEZE_TAG}"
    return proc.stdout


@pytest.fixture(scope="module")
def pinned():
    return json.loads(_blob(prereg.PREREG_JSON))


@frozen
def test_pinned_record_is_the_committed_one(pinned):
    assert json.loads(PREREG.read_text()) == pinned


@frozen
def test_pinned_task_count_and_n_rule(pinned):
    assert pinned["n"] in (6, 8, 10) and len(pinned["tasks"]) == pinned["n"] == len(set(pinned["tasks"]))
    assert pinned["n"] == order.n_rule(pinned["n_rule"]["m_control"], pinned["n_rule"]["m_horizon"])


@frozen
def test_pinned_tasks_are_the_first_ok_tasks_of_the_seeded_order(pinned):
    seeded = order.seeded_order(config.POOL, config.SEED, config.DOMAINS)
    assert pinned["draw"]["order"] == seeded
    walked = pinned["tasks"] + [r["task"] for r in pinned["replaced"]]
    assert sorted(walked, key=seeded.index) == seeded[:len(walked)]
    assert [t for t in seeded if t in pinned["tasks"]] == pinned["tasks"]
    assert not any(t.startswith(config.EXCLUDED_PREFIX) for t in pinned["tasks"])
    assert pinned["arm_orders"] == {t: list(order.arm_order(t, config.SEED)) for t in pinned["tasks"]}


@frozen
def test_pinned_prompts_match_the_configured_texts(pinned):
    prompts = pinned["prompts"]
    for key, text in prompts["texts"].items():
        arm, minutes = key.split("@")
        assert text == config.prompt_text(arm, int(minutes))
        assert prompts["text_sha256"][key] == sha(text)
        assert prompts["file_sha256"][key] == prereg.prompt_file_digest(arm, int(minutes))
    for task in pinned["tasks"]:
        minutes = pinned["task_details"][task]["minutes"]
        assert {f"{arm}@{minutes}" for arm in config.ARMS} <= set(prompts["texts"])


@frozen
def test_pinned_bundle_rebuilds_from_its_commit(pinned, tmp_path):
    files = bundle.build(config.REPO_ROOT, config.BUNDLE_COMMIT, tmp_path / "bundle", modules=config.BUNDLE_MODULES)
    assert pinned["bundle"] == {"commit": config.BUNDLE_COMMIT, "modules": list(config.BUNDLE_MODULES),
                                "files": files}


@frozen
def test_pinned_digests_match_the_repository(pinned):
    assert pinned["spec"] == {"path": prereg.SPEC, "sha256": sha(_blob(prereg.SPEC))}
    assert pinned["judge"]["sha256"] == sha(_blob(prereg.JUDGE_RUBRIC))
    for path, digest in pinned["code"].items():
        assert sha(_blob(path)) == digest, path
    assert any(p.startswith("bench/evo/") for p in pinned["code"])
    assert any(p.startswith("bench/tb4/") for p in pinned["code"])


@frozen
def test_pinned_settings_and_dataset(pinned):
    assert pinned["versions"] == prereg.versions() and pinned["observed"]["harbor"] == config.HARBOR_VERSION
    assert pinned["analysis"] == prereg.ANALYSIS and pinned["outcomes"] == prereg.OUTCOMES
    pin = pinned["dataset"]["pin"]
    assert pinned["dataset"]["revision"] == pin["revision"] == config.DATASET_REVISION
    assert pin["sha256"] == pin["lfs_oid"] and len(pin["sha256"]) == 64
    assert set(prereg.PILOT_JOBS) <= set(pinned["pilot"])
    assert all(pinned["pilot"][job]["ok"] is True for job in prereg.PILOT_JOBS if job not in prereg.RECORDED_ONLY)


@frozen
def test_pinned_markdown_is_the_rendering_of_the_record(pinned):
    assert prereg.render(pinned) == _blob(prereg.PREREG_MD).decode()


def test_collect_accepts_a_nop_chain_that_stopped_after_a_graded_first_round():
    # A step with min_reward aborts the chain after the nop's failed round 1; validate.failures accepts this.
    validations = {t: valid(t) for t in ORDER}
    validations[ORDER[0]] = valid(ORDER[0], nop=[0.0] + [None] * 9)
    assert make(validations=validations)["tasks"][0] == ORDER[0]


def test_collect_refuses_a_task_whose_rounds_have_different_agent_timeouts():
    task_infos = infos()
    task_infos[ORDER[0]] = dict(task_infos[ORDER[0]], uniform_agent_timeout=False)
    with pytest.raises(prereg.FreezeError, match="agent timeout"):
        make(task_infos=task_infos)


def test_collect_preregisters_the_ok_tasks_after_the_nth_as_reserves():
    validations = {t: valid(t) for t in ORDER}
    validations[ORDER[9]] = valid(ORDER[9], ok=False, reason="nop reward 1.0 in round-2")
    validations[ORDER[10]] = valid(ORDER[10], code="older")  # judged by other copy code
    validations[ORDER[11]] = valid(ORDER[11], nop=[0.0] * 9 + [1.0])  # says ok, but a nop round passes
    task_infos = infos(sixty={ORDER[12]})
    del validations[ORDER[8]]  # never validated: the walk stopped at the Nth ok task
    out = make(validations=validations, task_infos=task_infos)
    assert out["tasks"] == ORDER[:8] and out["reserve"] == [ORDER[12]]
    validations[ORDER[8]] = valid(ORDER[8])
    task_infos[ORDER[12]] = dict(task_infos[ORDER[12]], uniform_agent_timeout=False)
    out = make(validations=validations, task_infos=task_infos)
    assert out["tasks"] == ORDER[:8] and out["reserve"] == [ORDER[8]]
    assert set(out["task_details"]) == set(ORDER[:9])
    reserve = out["task_details"][ORDER[8]]
    assert (reserve["order"], reserve["arm_order"]) == (9, list(order.arm_order(ORDER[8], config.SEED)))
    assert reserve["image_id"] == validations[ORDER[8]]["image_id"]
    assert reserve["copy_digest"] == validations[ORDER[8]]["copy_digest"]
    with_60 = make(validations={t: valid(t) for t in ORDER}, task_infos=infos(sixty={ORDER[12]}))
    assert with_60["reserve"] == ORDER[8:] and "horizon@60" in with_60["prompts"]["texts"]
    text = prereg.render(with_60)
    assert "replaced by the next unused reserve in order" in text and "a drop stays a drop" in text
    assert all(f"`{task}`" in text for task in with_60["reserve"])
    assert "None" not in text.replace("None of", "")

def test_prereg_md_states_the_nop_rule_and_why_a_reserve_can_be_empty():
    validations = {t: valid(t) for t in ORDER[:8]}
    text = prereg.render(make(validations=validations))
    assert "nop reward below 1 on round 1 and on every later round it reached" in text
    assert "No reserve: validation stopped at the Nth passing task, or no later task passed it." in text

def verified_runs(tmp_path, tasks=(ORDER[0], ORDER[1])):
    """A RUNS holding the bundle, both prompt files and the agent copy of each task, and the record that pins them."""
    runs = tmp_path / "runs"
    record = {"bundle": prereg.build_bundle(runs), "prompts": {"file_sha256": {}}, "task_details": {}}
    for task in tasks:
        copy = runs / "copies" / "agent" / task
        (copy / "steps").mkdir(parents=True)
        (copy / "task.toml").write_text(f'name = "{task}"\n')
        record["task_details"][task] = {"minutes": 30, "copy_digest": tb4_copies.tree_digest(copy)}
        for arm in config.ARMS:
            path = copies.write_prompt(runs / "prompts" / f"{task}__{arm}.md", arm, 30)
            record["prompts"]["file_sha256"][f"{arm}@30"] = sha(path.read_bytes())
    return runs, record


def test_verify_runs_accepts_the_run_directory_the_record_pins(tmp_path):
    runs, record = verified_runs(tmp_path)
    assert prereg.verify_runs(record, runs, list(record["task_details"])) is None
    assert prereg.verify_runs(record, runs, [ORDER[1]]) is None


def test_verify_runs_skips_missing_prompt_files_but_refuses_a_missing_agent_copy(tmp_path):
    runs, record = verified_runs(tmp_path)
    shutil.rmtree(runs / "prompts")  # run.prepare writes them again from the pinned text
    assert prereg.verify_runs(record, runs, [ORDER[0], ORDER[1]]) is None
    shutil.rmtree(runs / "copies" / "agent" / ORDER[1])  # validation wrote it; prepare would rebuild an unpinned one
    assert prereg.verify_runs(record, runs, [ORDER[0]]) is None
    with pytest.raises(prereg.NotFrozen, match=f"{ORDER[1]}.*missing"):
        prereg.verify_runs(record, runs, [ORDER[0], ORDER[1]])


def test_verify_runs_refuses_a_bundle_that_differs_from_the_record(tmp_path):
    runs, record = verified_runs(tmp_path)
    other = dict(record["bundle"], files=dict(record["bundle"]["files"], **{"horizon/SKILL.md": "0" * 64}))
    with pytest.raises(prereg.NotFrozen, match="bundle"):
        prereg.verify_runs(dict(record, bundle=other), runs, [ORDER[0]])


def test_verify_runs_refuses_an_edited_bundle_directory(tmp_path):
    runs, record = verified_runs(tmp_path)
    (runs / "bundle" / "horizon" / "scripts" / "reviewing.py").write_text("# edited\n")
    with pytest.raises(prereg.NotFrozen, match="reviewing.py"):
        prereg.verify_runs(record, runs, [ORDER[0]])


def test_verify_runs_refuses_a_prompt_file_that_differs_from_the_record(tmp_path):
    runs, record = verified_runs(tmp_path)
    (runs / "prompts" / f"{ORDER[1]}__horizon.md").write_text("Take your time.\n")
    assert prereg.verify_runs(record, runs, [ORDER[0]]) is None  # only the tasks in play are held to the record
    with pytest.raises(prereg.NotFrozen, match=f"{ORDER[1]}__horizon.md"):
        prereg.verify_runs(record, runs, [ORDER[0], ORDER[1]])


def test_verify_runs_refuses_an_agent_copy_that_differs_from_the_record(tmp_path):
    runs, record = verified_runs(tmp_path)
    (runs / "copies" / "agent" / ORDER[1] / "extra.txt").write_text("not validated\n")
    assert prereg.verify_runs(record, runs, [ORDER[0]]) is None
    with pytest.raises(prereg.NotFrozen, match=ORDER[1]):
        prereg.verify_runs(record, runs, [ORDER[0], ORDER[1]])


def test_verify_runs_refuses_a_task_the_record_does_not_name(tmp_path):
    runs, record = verified_runs(tmp_path)
    with pytest.raises(prereg.NotFrozen, match=ORDER[5]):
        prereg.verify_runs(record, runs, [ORDER[0], ORDER[5]])


def tagged_repo(tmp_path, text=None):
    """A real repository holding docs/evaluations/evocode-horizon/prereg.json, tagged evo-prereg when text is given."""
    repo = tmp_path / "repo with space "
    path = repo / prereg.PREREG_JSON
    path.parent.mkdir(parents=True)
    path.write_text("{}\n")
    git(tmp_path, "init", "-q", str(repo))
    if text is not None:
        path.write_text(text)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "freeze")
    if text is not None:
        git(repo, "tag", "-a", config.FREEZE_TAG, "-m", "freeze")
    return repo, path


def test_require_frozen_record_returns_the_record_the_tag_holds(tmp_path):
    text = json.dumps({"tasks": ["t1"], "n": 1}, indent=2) + "\n"
    repo, path = tagged_repo(tmp_path, text)
    assert prereg.require_frozen_record(path, repo=repo) == {"tasks": ["t1"], "n": 1}
    assert prereg.require_frozen_record(str(path), subprocess.run, repo=repo) == {"tasks": ["t1"], "n": 1}


def test_require_frozen_record_refuses_a_file_that_is_not_the_tagged_one(tmp_path):
    repo, path = tagged_repo(tmp_path, json.dumps({"tasks": ["t1"]}) + "\n")
    elsewhere = tmp_path / "prereg.json"
    elsewhere.write_text(json.dumps({"tasks": ["t2"]}) + "\n")
    with pytest.raises(prereg.NotFrozen, match="differs"):
        prereg.require_frozen_record(elsewhere, repo=repo)
    path.write_text(json.dumps({"tasks": ["t1"]}) + " \n")  # even whitespace
    with pytest.raises(prereg.NotFrozen, match="differs"):
        prereg.require_frozen_record(path, repo=repo)
    with pytest.raises(prereg.NotFrozen, match="cannot read"):
        prereg.require_frozen_record(tmp_path / "nothing.json", repo=repo)


def test_require_frozen_record_refuses_without_a_tag_or_a_tagged_record(tmp_path):
    repo, path = tagged_repo(tmp_path)
    with pytest.raises(prereg.NotFrozen, match=config.FREEZE_TAG):
        prereg.require_frozen_record(path, repo=repo)
    git(repo, "rm", "-q", prereg.PREREG_JSON)
    git(repo, "commit", "-qm", "no record")
    git(repo, "tag", "-a", config.FREEZE_TAG, "-m", "freeze")
    with pytest.raises(prereg.NotFrozen, match=prereg.PREREG_JSON):
        prereg.require_frozen_record(path, repo=repo)


def test_collect_writes_a_public_reason_without_host_paths_or_test_names():
    docker = ("build failed twice: Command '['docker', 'build', '-t', 'evo-local/x:9fcae3e5539d', "
              "'/Users/x/Documents/evocode-horizon-runs/copies/validation/x']' returned non-zero exit status 1.")
    other = f"image ID changed during checks; see {config.RUNS}/logs/build__x.log and {Path.home()}/.cache/harbor"
    validations = {t: valid(t) for t in ORDER}
    validations[ORDER[0]] = valid(ORDER[0], ok=False, reason=docker)
    validations[ORDER[1]] = valid(ORDER[1], ok=False, reason="copy failed: steps/round-1/tests/x: not a regular file")
    validations[ORDER[2]] = valid(ORDER[2], ok=False, reason=other)
    validations[ORDER[3]] = valid(ORDER[3], ok=False, reason="nop reward 1.0 in round-3")
    out = make(validations=validations, task_infos=infos())
    assert out["replaced"] == [
        {"task": ORDER[0], "reason": "build failed twice"},
        {"task": ORDER[1], "reason": "copy failed"},
        {"task": ORDER[2], "reason": "image ID changed during checks; see $RUNS/logs/build__x.log and ~/.cache/harbor"},
        {"task": ORDER[3], "reason": "nop reward 1.0 in round-3"}]
    committed = json.dumps(out) + prereg.render(out)
    for private in ("/Users/x", "Command '", "tests/x", "round-1/", str(config.RUNS), str(Path.home())):
        assert private not in committed

def test_prereg_md_is_the_rendering_of_the_stored_json(tmp_path):
    # json.dumps(sort_keys=True) reorders the settings table; the freeze pin renders the stored record again
    json_path, md_path = prereg.write(make(), tmp_path)
    assert md_path.read_text() == prereg.render(json.loads(json_path.read_text()))

def test_the_secondary_outcomes_say_what_tokens_and_cost_cover_and_count_timed_out_rounds():
    cost = next(item for item in prereg.OUTCOMES["secondary"] if item.startswith("Cost:"))
    assert "median and mean agent minutes per round" in cost
    assert "rounds with a final result" in cost and "timed out" in cost and "per arm" in cost

@pytest.mark.parametrize("probe", [
    check("check__dummy-probe__control", attempt=2, ok=False, failures=["no trial directory with result.json"]),
    check("check__dummy-probe__control", attempt=2, ok=None,
          failures=["round-2: probe file round-2/procs.txt has no PID-1 line"], recorded={"round_2_started": True}),
], ids=["ok-false", "failures"])
def test_collect_refuses_a_timeout_probe_that_failed_and_asks_for_the_next_attempt(probe):
    with pytest.raises(prereg.FreezeError, match=r"check__dummy-probe__control__a2.*rerun the probe with the next "
                                                 r"--attempt"):
        make(pilot=dict(PILOT, **{"check__dummy-probe__control": probe}))
    assert make()["pilot"]["check__dummy-probe__control"]["ok"] is None  # a clean probe stays recorded only

def test_public_reason_cuts_every_copy_failure_to_what_failed():
    copies_dir = "/Users/x/evocode-horizon-runs/copies"
    listing = (f"planted copy failed: [('{copies_dir}/validation/x/steps/round-1/tests/test_a.py', "
               f"'{copies_dir}/planted/x/steps/round-1/tests/test_a.py', 'Permission denied')]")
    assert prereg.public_reason(listing) == "planted copy failed"
    assert prereg.public_reason("copy failed: steps/round-1/tests/x: not a regular file") == "copy failed"
    assert prereg.public_reason("build failed twice: Command '['docker']' returned 1.") == "build failed twice"
    assert prereg.public_reason("nop rewards [1.0, 0.0], expected below 1.0 with round 1 graded") == (
        "nop rewards [1.0, 0.0], expected below 1.0 with round 1 graded")

def test_the_git_helper_ignores_a_git_dir_that_a_hook_exports(tmp_path, monkeypatch):
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    def decoy_git(*args):
        return subprocess.run(["git", "-C", str(decoy), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                               *args], capture_output=True, text=True, env=clean)

    decoy = tmp_path / "decoy"  # stands in for the real repository a pre-commit hook runs the suite in
    decoy.mkdir()
    decoy_git("init", "-q")
    (decoy / "real.txt").write_text("real\n")
    decoy_git("add", ".")
    decoy_git("commit", "-qm", "real")
    head = decoy_git("rev-parse", "HEAD").stdout
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    repo, _ = tagged_repo(tmp_path / "scratch", "{}\n")
    assert decoy_git("rev-parse", "HEAD").stdout == head
    assert decoy_git("tag", "-l", config.FREEZE_TAG).stdout == ""
    assert prereg.frozen_commit(lambda cmd, **kw: subprocess.run(cmd, env=clean, **kw), repo) is not None
