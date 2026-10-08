import json
import subprocess
from pathlib import Path

from bench.tb4 import run, validate

INSTRUCTION = "Do it.\n\nYou have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.\n"
TOML = '[metadata]\ncategory = "ML"\nexpert_time_estimate_hours = 4\n\n[verifier]\nenvironment_mode = "separate"\n\n[environment]\ncpus = 2\nmemory_mb = 4096\n'
META = {"name": "demo", "category": "ML", "estimate_h": 4.0}


def cp(cmd, code=0, out=""):
    return subprocess.CompletedProcess(cmd, code, out, "")


class FakeHost:
    def __init__(self, rewards=None, python_ok=True, build_ok=True):
        self.calls = []
        self.rewards = rewards or {"oracle": 1, "nop": 0, "ledger": 1}
        self.python_ok, self.build_ok = python_ok, build_ok

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        if cmd[:2] == ["docker", "build"]:
            if not self.build_ok:
                raise subprocess.CalledProcessError(1, cmd)
            return cp(cmd)
        if cmd[:3] == ["docker", "image", "inspect"]:
            image_id = "sha256:v" if "-verifier" in cmd[3] else "sha256:a"
            return cp(cmd, 0, json.dumps([{"Id": image_id, "Architecture": "arm64",
                                           "Config": {"WorkingDir": "/app", "User": ""}}]))
        if cmd[:2] == ["docker", "run"]:
            if "sys.version_info" in cmd[-1]:
                return cp(cmd, 0 if self.python_ok else 1, "3.12.4\n")
            return cp(cmd, 0, "ok\n")
        if cmd[:2] == ["harbor", "run"]:
            job = cmd[cmd.index("--job-name") + 1]
            trial = Path(cmd[cmd.index("-o") + 1]) / job / "x__1234567"
            trial.mkdir(parents=True)
            reward = self.rewards[job.split("__")[0]]
            (trial / "result.json").write_text(json.dumps({"verifier_result": {"rewards": {"reward": reward}}}))
            return cp(cmd)
        return cp(cmd)


def setup(tmp_path):
    task = tmp_path / "tb4" / "tasks" / "demo"
    for sub in ("environment", "tests", "solution"):
        (task / sub).mkdir(parents=True)
    (task / "task.toml").write_text(TOML)
    (task / "instruction.md").write_text(INSTRUCTION)
    (task / "environment" / "Dockerfile").write_text("FROM python:3.12-slim\n")
    (task / "tests" / "Dockerfile").write_text("FROM python:3.12-slim\n")
    (task / "solution" / "solve.sh").write_text("#!/bin/bash\ntrue\n")
    ledger = tmp_path / "ledger"
    (ledger / "goals").mkdir(parents=True)
    (ledger / "goals" / "g.json").write_text("{}")
    return run.Paths(tmp_path).ensure(), ledger


def test_happy_path(tmp_path):
    paths, ledger = setup(tmp_path)
    out = validate.validate_task(META, paths, ledger, run_cmd=FakeHost(), log=None)
    assert out["ok"], out["failures"]
    assert out["checks"] == {"oracle": 1.0, "nop": 0.0, "ledger": 1.0}
    assert (out["workdir"], out["agent_image_id"], out["verifier_image_id"]) == ("/app", "sha256:a", "sha256:v")
    assert len(out["copy_digest"]) == 64 and (paths.check_copies / "demo" / "solution" / "solve.orig.sh").is_file()


def test_a_passing_nop_is_a_failure(tmp_path):
    paths, ledger = setup(tmp_path)
    out = validate.validate_task(META, paths, ledger, run_cmd=FakeHost(rewards={"oracle": 1, "nop": 1, "ledger": 1}), log=None)
    assert not out["ok"] and "nop reward 1.0, expected 0.0" in out["failures"]


def test_missing_python_stops_before_any_harbor_run(tmp_path):
    paths, ledger = setup(tmp_path)
    host = FakeHost(python_ok=False)
    out = validate.validate_task(META, paths, ledger, run_cmd=host, log=None)
    assert out["failures"] == ["python3 >= 3.10 missing"]
    assert not any(c[:2] == ["harbor", "run"] for c in host.calls)


def test_build_failure_is_recorded(tmp_path):
    paths, ledger = setup(tmp_path)
    out = validate.validate_task(META, paths, ledger, run_cmd=FakeHost(build_ok=False), log=None)
    assert not out["ok"] and out["failures"][0].startswith("build failed")


def test_validate_all_resumes_and_removes_failed_images(tmp_path):
    paths, ledger = setup(tmp_path)
    (paths.root / "validation").mkdir()
    (paths.root / "validation" / "done.json").write_text(json.dumps({"task": "done", "ok": True}))
    host = FakeHost(python_ok=False)
    result = validate.validate_all([META, {"name": "done", "category": "ML", "estimate_h": 2.0}],
                                   paths, ledger, tmp_path / "validation.json", run_cmd=host, log=lambda m: None)
    assert [t["task"] for t in result["tasks"]] == ["demo", "done"]
    assert result["summary"] == {"candidates": 2, "ok": 1, "failed": 1}
    assert ["docker", "image", "rm", "-f", "tb4-local/demo:v4.0.0", "tb4-local/demo-verifier:v4.0.0"] in host.calls
    assert not any("done" in " ".join(c) for c in host.calls)


def test_retry_after_a_crash_starts_clean(tmp_path):
    paths, ledger = setup(tmp_path)
    (paths.copies / "demo").mkdir()
    (paths.checks / "oracle__demo").mkdir()
    out = validate.validate_task(META, paths, ledger, run_cmd=FakeHost(), log=None)
    assert out["ok"], out["failures"]
