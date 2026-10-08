import dataclasses
import json
import os
import subprocess
from pathlib import Path

import pytest

from bench.tb4 import config, run


def cp(cmd, code=0, out=""):
    return subprocess.CompletedProcess(cmd, code, out, "")


TRIAL = run.Trial(task="demo", arm="horizon", attempt=1, phase="measured", workdir="/app",
                  agent_image_id="sha256:a", verifier_image_id="sha256:v")


def box(cid, image, project):
    return {"Id": cid, "Image": image, "Config": {"Labels": {
        "com.docker.compose.project": project, "com.docker.compose.service": "main"}}}


class FakeHost:
    """Answers docker, harbor, sysctl and git calls the way the real tools do."""

    def __init__(self, image_ids=("sha256:a", "sha256:v"), trial_name="demo__AbC1234", sleeps=("s0",),
                 running="", agent_ran=True, exception=None):
        self.calls, self.image_ids, self.trial_name = [], image_ids, trial_name
        self.sleeps, self.running, self.agent_ran, self.exception = list(sleeps), running, agent_ran, exception

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        if cmd[:1] == ["sysctl"]:
            return cp(cmd, 0, self.sleeps.pop(0) if len(self.sleeps) > 1 else self.sleeps[0])
        if cmd[:3] == ["docker", "image", "inspect"]:
            image_id = self.image_ids[1] if "-verifier" in cmd[3] else self.image_ids[0]
            return cp(cmd, 0, json.dumps([{"Id": image_id, "Architecture": "arm64",
                                           "Config": {"WorkingDir": "/app", "User": ""}}]))
        if cmd[:2] == ["harbor", "run"]:
            trial_dir = Path(cmd[cmd.index("-o") + 1]) / cmd[cmd.index("--job-name") + 1] / self.trial_name
            (trial_dir / "agent").mkdir(parents=True)
            execution = {"started_at": "2026-10-07T12:00:00Z"} if self.agent_ran else None
            info = {"exception_type": self.exception} if self.exception else None
            (trial_dir / "result.json").write_text(json.dumps({"trial_name": self.trial_name,
                                                               "agent_execution": execution,
                                                               "exception_info": info}))
            (trial_dir / "agent" / "claude-code.txt").write_text("")
            return cp(cmd)
        if cmd[:3] == ["docker", "ps", "-q"]:
            return cp(cmd, 0, self.running)
        if cmd[:3] == ["docker", "ps", "-aq"]:
            return cp(cmd, 0, "c1\nc2\nc3\n")
        if cmd[:2] == ["docker", "inspect"]:
            if cmd[2:] == ["r1"]:
                return cp(cmd, 0, json.dumps([box("r1", "sha256:a", "other__xyz9876__env")]))
            return cp(cmd, 0, json.dumps([box("c1", "sha256:a", "demo__abc1234__env"),
                                          box("c2", "sha256:v", "demo__abc1234__verifier__trial"),
                                          box("c3", "sha256:z", "other__xyz9876__env")]))
        if cmd[:2] == ["docker", "cp"]:
            (Path(cmd[3]) / "goals").mkdir(parents=True)
            return cp(cmd)
        return cp(cmd)


def _without(cmd, *flags):
    cmd = list(cmd)
    for flag in flags:
        if flag in cmd:
            i = cmd.index(flag)
            del cmd[i:i + 2]
    return cmd


def test_arms_differ_only_in_prompt_job_name_and_skill(tmp_path):
    paths = run.Paths(tmp_path)
    control = run.harbor_command(dataclasses.replace(TRIAL, arm="control"), paths)
    horizon = run.harbor_command(TRIAL, paths)
    assert horizon[-2:] == ["--skill", str(paths.skill)] and "--skill" not in control
    assert control[control.index("--extra-instruction-path") + 1] == str(config.PROMPTS / "control.md")
    assert horizon[horizon.index("--extra-instruction-path") + 1] == str(config.PROMPTS / "horizon.md")
    flags = ("--extra-instruction-path", "--job-name", "--skill")
    assert _without(control, *flags) == _without(horizon, *flags)


def test_secrets_and_fixed_flags(tmp_path):
    cmd = run.harbor_command(TRIAL, run.Paths(tmp_path))
    assert [cmd[i + 1] for i, x in enumerate(cmd) if x == "--ae"] == [
        "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}", "CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000"]
    assert not any("FORCE_OAUTH" in x for x in cmd)
    assert "--force-build" not in cmd and "--no-force-build" in cmd
    for flag, value in (("-n", "1"), ("-k", "1"), ("-r", "0"), ("--effort", "high"), ("-a", "claude-code"),
                        ("--ek", "keep_containers=true"), ("--agent-timeout-multiplier", "0.25"),
                        ("--agent-setup-timeout-multiplier", "2.0"), ("-m", config.MODEL)):
        assert cmd[cmd.index(flag) + 1] == value
    assert "version=2.1.293" in cmd and "disable_web_search=true" in cmd


def test_agent_env_strips_competing_credentials():
    env = run.agent_env("tok", base={"ANTHROPIC_API_KEY": "k", "CLAUDE_CODE_EFFORT_LEVEL": "max", "PATH": "/bin"})
    assert env == {"PATH": "/bin", "CLAUDE_CODE_OAUTH_TOKEN": "tok", "CLAUDE_FORCE_OAUTH": "1"}


def test_read_token():
    assert run.read_token(run=lambda c, **k: cp(c, 0, "secret-token\n")) == "secret-token"
    with pytest.raises(RuntimeError):
        run.read_token(run=lambda c, **k: cp(c, 44, ""))


def test_wait_seconds():
    assert run.wait_seconds(None, 0, 0.5, 0.9) == 0
    assert run.wait_seconds({"status": "allowed", "five_hour": 0.2, "seven_day": 0.1}, 0, 0.5, 0.9) == 0
    assert run.wait_seconds({"status": "allowed", "five_hour": 0.6, "five_hour_resets_at": 1000,
                             "seven_day": 0.1}, 100, 0.5, 0.9) == 960
    assert run.wait_seconds({"status": "rejected", "five_hour": 0.1, "five_hour_resets_at": 1000}, 100, 0.5, 0.9) == 960
    assert run.wait_seconds({"status": "allowed", "five_hour": 0.1, "seven_day": 0.95,
                             "seven_day_resets_at": 5000}, 100, 0.5, 0.9) == 4960
    assert run.wait_seconds({"status": "allowed", "five_hour": 0.9, "five_hour_resets_at": 50}, 100, 0.5, 0.9) == 60


def test_a_zero_limit_still_starts_in_a_fresh_window_and_weekly_can_be_skipped():
    fresh = {"status": "allowed", "five_hour": 0.0, "five_hour_resets_at": 1000, "seven_day": 0.95}
    assert run.wait_seconds(fresh, 0, 0.0, None) == 0
    assert run.wait_seconds(fresh, 0, 0.0, 0.9) > 0


def test_pace_limits_reserve_weekly_room_only_before_the_first_arm():
    pace = run.Pace(first=0.5, second=0.8, weekly=0.9, weekly_step=0.05)
    assert pace.limits(0) == (0.5, 0.8) and pace.limits(1) == (0.8, None)


def test_wait_for_headroom_sleeps_until_the_probe_clears_and_retries_failed_probes():
    results = iter([run.ProbeError("offline"), {"status": "allowed", "five_hour": 0.9, "five_hour_resets_at": 200},
                    {"status": "allowed", "five_hour": 0.1}])

    def probe():
        item = next(results)
        if isinstance(item, Exception):
            raise item
        return item

    slept = []
    info = run.wait_for_headroom(probe, 0.5, 0.9, sleep=slept.append, now=lambda: 100, log=lambda message: None)
    assert slept == [600, 160] and info["five_hour"] == 0.1


def test_probe_usage_is_isolated_tool_free_and_strict():
    lines = "\n".join(json.dumps(e) for e in (
        {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "unifiedWindows": {
            "five_hour": {"utilization": 0.5, "resetsAt": 1}, "seven_day": {"utilization": 0.23, "resetsAt": 2}}}},
        {"type": "result", "is_error": False, "result": "ok"}))
    seen = {}

    def fake(cmd, **kwargs):
        seen.update(kwargs, cmd=cmd)
        return cp(cmd, 0, lines + "\n")

    assert run.probe_usage("tok", run=fake)["five_hour"] == 0.5
    assert seen["env"]["CLAUDE_CONFIG_DIR"] == seen["env"]["HOME"] == seen["cwd"]
    assert seen["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "tok" and "ANTHROPIC_API_KEY" not in seen["env"]
    assert seen["cmd"][seen["cmd"].index("--tools") + 1] == ""
    for bad in (cp([], 1, lines), cp([], 0, ""), cp([], 0, json.dumps({"type": "result", "is_error": True}))):
        with pytest.raises(run.ProbeError):
            run.probe_usage("tok", run=lambda c, **k: bad)


def test_probe_returns_a_rejected_window_and_wraps_timeouts():
    rejected = json.dumps({"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "unifiedWindows": {
        "five_hour": {"utilization": 1.0, "resetsAt": 5000}}}}) + "\n" + json.dumps({"type": "result", "is_error": True})
    info = run.probe_usage("tok", run=lambda c, **k: cp(c, 1, rejected))
    assert info["status"] == "rejected" and info["five_hour_resets_at"] == 5000

    def hang(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 300)

    with pytest.raises(run.ProbeError):
        run.probe_usage("tok", run=hang)


def test_compose_containers_match_only_this_trial():
    found = run.compose_containers("demo__AbC1234", run=FakeHost())
    assert {c["id"]: c["role"] for c in found} == {"c1": "agent", "c2": "verifier"}


def test_run_trial_records_images_ledger_and_cleans_up(tmp_path):
    paths = run.Paths(tmp_path).ensure()
    host = FakeHost()
    record = run.run_trial(TRIAL, paths, "secret-token", "abc123", run=host,
                           now=iter([10.0, 20.0]).__next__, usage={"five_hour": 0.1})
    assert record["harbor_exit"] == 0 and record["agent_ran"] is True and record["protocol_deviations"] == []
    assert record["container_images"] == record["image_ids_expected"] == {"agent": "sha256:a", "verifier": "sha256:v"}
    assert record["ledger"]["copied"] == {"/app/.claude/harness": str(paths.ledgers / "demo__horizon__a1" / "0")}
    assert ["docker", "rm", "-f", "c1", "c2"] in host.calls
    assert record["freeze_commit"] == "abc123" and (record["started_at"], record["finished_at"]) == (10.0, 20.0)
    assert "secret-token" not in (paths.records / "demo__horizon__a1.json").read_text()


def test_a_usage_limited_trial_is_marked(tmp_path):
    paths = run.Paths(tmp_path).ensure()
    record = run.run_trial(TRIAL, paths, "t", "f", run=FakeHost(exception="ApiUsageLimitError"))
    assert record["usage_limit"] is True and record["agent_ran"] is True


def test_copy_ledger_refuses_an_existing_destination(tmp_path):
    (tmp_path / "ledger").mkdir()
    with pytest.raises(FileExistsError):
        run.copy_ledger([{"id": "c1", "role": "agent", "service": "main"}], ["/app/.claude/harness"],
                        tmp_path / "ledger", run=FakeHost())


def test_a_host_sleep_during_the_trial_is_recorded(tmp_path):
    paths = run.Paths(tmp_path).ensure()
    record = run.run_trial(TRIAL, paths, "t", "f", run=FakeHost(sleeps=("before", "after")))
    assert config.HOST_SLEPT in record["protocol_deviations"]


def test_existing_record_is_returned_without_running(tmp_path):
    paths = run.Paths(tmp_path).ensure()
    (paths.records / f"{TRIAL.job_name}.json").write_text(json.dumps({"job_name": TRIAL.job_name, "done": True}))
    host = FakeHost()
    assert run.run_trial(TRIAL, paths, "t", "f", run=host)["done"] is True
    assert host.calls == []


def test_half_finished_job_is_cleaned_and_recorded_as_interrupted(tmp_path):
    paths = run.Paths(tmp_path).ensure()
    (paths.jobs / TRIAL.job_name / "demo__AbC1234").mkdir(parents=True)
    host = FakeHost()
    with pytest.raises(run.Interrupted):
        run.run_trial(TRIAL, paths, "t", "f", run=host)
    assert json.loads((paths.records / f"{TRIAL.job_name}.json").read_text())["interrupted"] is True
    assert ["docker", "rm", "-f", "c1", "c2"] in host.calls


def test_running_trial_containers_block_a_new_trial(tmp_path):
    paths = run.Paths(tmp_path).ensure()
    host = FakeHost(running="r1\n")
    with pytest.raises(run.RunnerBusy):
        run.run_trial(TRIAL, paths, "t", "f", run=host)
    assert not any(c[:2] == ["harbor", "run"] for c in host.calls)


def test_changed_image_stops_before_harbor(tmp_path):
    paths = run.Paths(tmp_path).ensure()
    host = FakeHost(image_ids=("sha256:rebuilt", "sha256:v"))
    with pytest.raises(run.ImageChanged):
        run.run_trial(TRIAL, paths, "t", "f", run=host)
    assert not any(c[:2] == ["harbor", "run"] for c in host.calls)


def test_lock_admits_one_runner(tmp_path):
    with run.hold_lock(tmp_path / "runner.lock"):
        assert (tmp_path / "runner.lock").read_text().strip() == str(os.getpid())
        with pytest.raises(run.RunnerBusy):
            with run.hold_lock(tmp_path / "runner.lock"):
                pass
    with run.hold_lock(tmp_path / "runner.lock"):
        pass


ROWS = [
    {"order": 0, "task": "s", "first_arm": "setup", "workdir": "/app", "agent_image_id": "a", "verifier_image_id": "v"},
    {"order": 1, "task": "t1", "first_arm": "horizon", "workdir": "/app", "agent_image_id": "a", "verifier_image_id": "v"},
    {"order": 2, "task": "t2", "first_arm": "control", "workdir": "/w", "agent_image_id": "a", "verifier_image_id": "v"},
]


def test_trials_for_ordering():
    assert [t.job_name for t in run.trials_for(ROWS, "setup", 1)] == ["setup__s__control__a1", "setup__s__horizon__a1"]
    assert [t.job_name for t in run.trials_for(ROWS, "measured", 2, only={"t2"})] == ["t2__control__a2", "t2__horizon__a2"]
    assert [t.arm for t in run.trials_for(ROWS, "measured", 1)] == ["horizon", "control", "control", "horizon"]


def test_run_all_paces_first_and_second_arm(tmp_path, monkeypatch):
    paths = run.Paths(tmp_path).ensure()
    limits = []
    monkeypatch.setattr(run, "run_trial", lambda trial, *a, **k: {"job_name": trial.job_name, "agent_ran": True})
    monkeypatch.setattr(run, "wait_for_headroom", lambda probe, five, weekly, **k: limits.append((five, weekly)) or {})
    records = run.run_all(run.trials_for(ROWS, "measured", 1), paths, "t", "f", probe=lambda: None,
                          pace=run.Pace(first=0.5, second=0.8, weekly=0.9, weekly_step=0.05))
    assert limits == [(0.5, 0.8), (0.8, None), (0.5, 0.8), (0.8, None)] and len(records) == 4


@pytest.mark.parametrize("partner,reason", [
    ({"interrupted": True}, "partner interrupted"),
    ({"agent_ran": False}, "partner never started"),
    ({"agent_ran": True, "protocol_deviations": ["host slept during trial"]}, "partner host slept"),
    ({"agent_ran": True, "usage_limit": True}, "partner hit a usage limit"),
    ({"agent_ran": True}, None),
])
def test_skip_reason(tmp_path, partner, reason):
    path = tmp_path / "partner.json"
    path.write_text(json.dumps(partner))
    assert run.skip_reason(path) == reason
    assert run.skip_reason(tmp_path / "missing.json") is None


def test_run_all_waits_for_the_reset_after_a_usage_limited_trial(tmp_path, monkeypatch):
    paths = run.Paths(tmp_path).ensure()
    limited = {"agent_ran": True, "usage_limit": True,
               "trial_rate_limit": {"status": "rejected", "five_hour_resets_at": 1000}}
    monkeypatch.setattr(run, "run_trial", lambda trial, *a, **k: dict(limited, job_name=trial.job_name))
    monkeypatch.setattr(run, "wait_for_headroom", lambda *a, **k: {})
    slept = []
    run.run_all(run.trials_for(ROWS, "measured", 1, only={"t2"})[:1], paths, "t", "f", probe=lambda: None,
                sleep=slept.append, now=lambda: 100)
    assert slept == [960]


def test_run_all_does_not_wait_before_recording_an_interruption(tmp_path, monkeypatch):
    paths = run.Paths(tmp_path).ensure()
    (paths.jobs / "t2__control__a1").mkdir()
    waits = []

    def interrupted(trial, *a, **k):
        raise run.Interrupted(trial.job_name)

    monkeypatch.setattr(run, "run_trial", interrupted)
    monkeypatch.setattr(run, "wait_for_headroom", lambda *a, **k: waits.append(1))
    with pytest.raises(run.Interrupted):
        run.run_all(run.trials_for(ROWS, "measured", 1, only={"t2"}), paths, "t", "f", probe=lambda: None)
    assert waits == []


def test_run_all_skips_the_partner_of_an_interrupted_arm(tmp_path, monkeypatch):
    paths = run.Paths(tmp_path).ensure()
    (paths.records / "t1__horizon__a1.json").write_text(json.dumps({"job_name": "t1__horizon__a1", "interrupted": True}))
    ran = []
    monkeypatch.setattr(run, "run_trial", lambda trial, *a, **k: ran.append(trial.job_name) or {"agent_ran": True})
    monkeypatch.setattr(run, "wait_for_headroom", lambda *a, **k: {})
    run.run_all(run.trials_for(ROWS, "measured", 1, only={"t1"}), paths, "t", "f", probe=lambda: None)
    assert ran == []
    assert json.loads((paths.records / "t1__control__a1.json").read_text())["skipped"] == "partner interrupted"


def test_run_all_stops_when_the_agent_never_ran(tmp_path, monkeypatch):
    paths = run.Paths(tmp_path).ensure()
    monkeypatch.setattr(run, "run_trial", lambda trial, *a, **k: {"job_name": trial.job_name, "agent_ran": False})
    monkeypatch.setattr(run, "wait_for_headroom", lambda *a, **k: {})
    with pytest.raises(run.InfrastructureFailure):
        run.run_all(run.trials_for(ROWS, "measured", 1), paths, "t", "f", probe=lambda: None)


def test_require_freeze_accepts_descendants_with_unchanged_frozen_files():
    def git(tag="abc", ancestor=True, diff_clean=True, dirty="", results_tracked=False):
        def fake(cmd, **kwargs):
            sub = cmd[3]
            if sub == "rev-parse":
                return cp(cmd, 0 if tag else 128, tag + "\n")
            if sub == "merge-base":
                return cp(cmd, 0 if ancestor else 1)
            if sub == "diff":
                return cp(cmd, 0 if diff_clean else 1)
            if sub == "status":
                return cp(cmd, 0, dirty)
            if sub == "ls-files":
                return cp(cmd, 0 if results_tracked else 1)
            return cp(cmd)
        return fake

    assert run.require_freeze(run=git()) == "abc"
    for kwargs in (dict(tag=""), dict(ancestor=False), dict(diff_clean=False),
                   dict(dirty=" M bench/tb4/run.py\n"), dict(results_tracked=True)):
        with pytest.raises(run.NotFrozen):
            run.require_freeze(run=git(**kwargs))
