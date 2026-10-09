import dataclasses
import json
import subprocess
from pathlib import Path

import pytest

from bench.evo import config, copies, images, order, run

TASK = "theme_d1_w2_code_build_brownfield_modification"
TRIAL_NAME = "theme_d1_w2_code_build_brownfiel__AbC1234"  # Harbor: task_name[:32] + "__" + 7 random chars
PROJECT = "theme_d1_w2_code_build_brownfiel__abc1234__env"
IMAGE = "sha256:" + "a" * 64
INFO = {"task": TASK, "dir": "/nonexistent/original", "rounds": 10,
        "step_names": [f"round-{i}" for i in range(1, 11)], "agent_timeout_sec": 1800.0,
        "verifier_timeout_sec": 1800.0, "reward_strategy": "mean"}
TRIAL = run.EvoTrial(phase="main", task=TASK, arm="horizon", attempt=1)
RECORD_KEYS = {"job_name", "phase", "task", "arm", "attempt", "started", "finished", "exit_code", "job_dir",
               "trial_dir", "valid", "invalid_reason", "image_id", "freeze", "harbor_version",
               "claude_code_version", "command"}

INIT = {"type": "system", "subtype": "init", "cwd": "/app", "model": "claude-sonnet-5-5",
        "claude_code_version": "2.1.293"}
ALLOWED = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "unifiedWindows": {
    "five_hour": {"utilization": 0.2, "resetsAt": 5000}, "seven_day": {"utilization": 0.3, "resetsAt": 9000}}}}
REJECTED = {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "rateLimitType": "five_hour",
                                                            "resetsAt": 5000}}
SPOKE = {"type": "assistant", "parent_tool_use_id": None, "message": {"model": "claude-sonnet-5-5",
                                                                     "content": [{"type": "text", "text": "Working."}]}}
DONE = {"type": "result", "subtype": "success", "is_error": False, "result": "Done."}
API_500 = {"type": "result", "subtype": "success", "is_error": True, "api_error_status": 500,
           "result": "API Error: 500 Internal server error"}
OVERLOADED = {"type": "assistant", "parent_tool_use_id": None, "error": "overloaded",
              "message": {"model": "<synthetic>", "content": [{"type": "text", "text": "API Error: overloaded"}]}}
CLEAN = (ALLOWED, INIT, SPOKE, DONE)
HEADROOM = {"status": "allowed", "five_hour": 0.1, "seven_day": 0.2}


def cp(cmd, code=0, out=""):
    return subprocess.CompletedProcess(cmd, code, out, "")


def lines(*events):
    return "".join(json.dumps(e) + "\n" for e in events)


def step(name, events=CLEAN, exception=None, started=True):
    return {"name": name, "events": events, "exception": exception, "started": started}


def ready(tmp_path, image=IMAGE, ok=True, skill=True):
    paths = run.Paths(tmp_path / "runs").ensure()
    paths.copy(TASK).mkdir(parents=True)
    for arm in config.ARMS:
        paths.prompt(TASK, arm).write_text(config.prompt_text(arm, 30) + "\n")
    if skill:
        paths.skill.mkdir(parents=True)
        (paths.skill / "SKILL.md").write_text("---\nname: horizon\n---\n")
    (paths.validation / f"{TASK}.json").write_text(json.dumps(
        {"task": TASK, "image_id": image, "arch": "arm64", "ok": ok, "reason": None if ok else "nop passed"}))
    return paths


@pytest.fixture(autouse=True)
def pinned_image(monkeypatch):
    """images.inspect (Task 6) asks Docker; here every tag resolves to IMAGE, and the asked tags are kept."""
    asked = []
    monkeypatch.setattr(images, "inspect", lambda tag, run=None: asked.append(tag) or {"id": IMAGE, "arch": "arm64"})
    return asked


def box(cid, image, project, service="main"):
    return {"Id": cid, "Image": image, "Config": {"Labels": {
        "com.docker.compose.project": project, "com.docker.compose.service": service}}}


class FakeHost:
    """Answers docker, sysctl and harbor calls; `harbor run` writes a multi-step trial as Harbor 0.24.0 does."""

    def __init__(self, steps=None, trial_exception=None, sleeps=("s0",), running="", container_image=IMAGE,
                 write_result=True, exit_code=0, create_job=True):
        self.calls, self.harbor_kwargs = [], None
        self.steps = steps if steps is not None else [step("round-1"), step("round-2")]
        self.trial_exception, self.sleeps, self.running = trial_exception, list(sleeps), running
        self.container_image = container_image
        self.write_result, self.exit_code, self.create_job = write_result, exit_code, create_job

    def harbor(self, cmd, kwargs):
        self.harbor_kwargs = kwargs
        if not self.create_job:
            return
        job_dir = Path(cmd[cmd.index("-o") + 1]) / cmd[cmd.index("--job-name") + 1]
        trial_dir = job_dir / TRIAL_NAME
        trial_dir.mkdir(parents=True)
        (job_dir / "lock.json").write_text(json.dumps({"schema_version": 3, "harbor": {"version": "0.24.0"}}))
        if not self.write_result:
            return
        results = []
        for item in self.steps:
            step_dir = trial_dir / "steps" / item["name"]
            for sub in ("agent", "verifier", "artifacts"):
                (step_dir / sub).mkdir(parents=True)
            if item["started"]:
                (step_dir / "agent" / "claude-code.txt").write_text(lines(*item["events"]))
                (step_dir / "verifier" / "reward.txt").write_text("1\n")
            exception = None
            if item["exception"]:
                exception = {"exception_type": item["exception"], "exception_message": "",
                             "exception_traceback": "", "occurred_at": "2026-10-09T12:30:00Z"}
            results.append({
                "step_name": item["name"], "agent_result": None, "exception_info": exception,
                "verifier_result": {"rewards": {"reward": 1.0}} if item["started"] else None,
                "agent_execution": ({"started_at": "2026-10-09T12:00:00Z", "finished_at": "2026-10-09T12:20:00Z"}
                                    if item["started"] else None),
                "verifier": None})
        trial_exception = None
        if self.trial_exception:
            trial_exception = {"exception_type": self.trial_exception, "exception_message": "",
                               "exception_traceback": "", "occurred_at": "2026-10-09T12:00:00Z"}
        (trial_dir / "result.json").write_text(json.dumps({
            "task_name": TASK, "trial_name": TRIAL_NAME, "agent_info": {"name": "claude-code", "version": "2.1.293"},
            "exception_info": trial_exception, "step_results": results}))

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        if cmd[:1] == ["sysctl"]:
            return cp(cmd, 0, self.sleeps.pop(0) if len(self.sleeps) > 1 else self.sleeps[0])
        if cmd[:2] == ["harbor", "run"]:
            self.harbor(cmd, kwargs)
            return cp(cmd, self.exit_code)
        if cmd[:3] == ["docker", "ps", "-q"]:
            return cp(cmd, 0, self.running)
        if cmd[:3] == ["docker", "ps", "-aq"]:
            return cp(cmd, 0, "c1\nc9\n")
        if cmd[:2] == ["docker", "inspect"]:
            if cmd[2:] == ["r1"]:
                return cp(cmd, 0, json.dumps([box("r1", IMAGE, "other_task__xyz9876__env")]))
            return cp(cmd, 0, json.dumps([box("c1", self.container_image, PROJECT),
                                          box("c9", IMAGE, "other_task__xyz9876__env")]))
        if cmd[:2] == ["docker", "cp"]:
            (Path(cmd[3]) / "goals").mkdir(parents=True)
            return cp(cmd)
        return cp(cmd)


def ran_harbor(host):
    return any(c[:2] == ["harbor", "run"] for c in host.calls)


def go(paths, host, trial=TRIAL, probe=lambda: HEADROOM, now=None, slept=None):
    return run.run_trial(trial, paths, "secret-token", "abc123", run=host, now=now or iter([5.0, 10.0, 20.0]).__next__,
                         probe=probe, info=INFO, sleep=(slept if slept is not None else []).append,
                         log=lambda message: None)


def _without(cmd, *flags):
    cmd = list(cmd)
    for flag in flags:
        if flag in cmd:
            i = cmd.index(flag)
            del cmd[i:i + 2]
    return cmd


def test_both_arms_share_every_flag_but_prompt_job_name_and_skill(tmp_path):
    paths = run.Paths(tmp_path)
    control = run.harbor_command(dataclasses.replace(TRIAL, arm="control"), paths)
    horizon = run.harbor_command(TRIAL, paths)
    assert horizon[-2:] == ["--skill", str(tmp_path / "bundle" / "horizon")] and "--skill" not in control
    assert control[control.index("--extra-instruction-path") + 1] == str(tmp_path / "prompts" / f"{TASK}__control.md")
    assert horizon[horizon.index("--extra-instruction-path") + 1] == str(tmp_path / "prompts" / f"{TASK}__horizon.md")
    assert horizon[horizon.index("--job-name") + 1] == f"main__{TASK}__horizon__a1" == TRIAL.job_name
    flags = ("--extra-instruction-path", "--job-name", "--skill")
    assert _without(control, *flags) == _without(horizon, *flags)


def test_fixed_flags_secret_by_reference_and_no_resume(tmp_path):
    cmd = run.harbor_command(TRIAL, run.Paths(tmp_path))
    assert cmd[:2] == ["harbor", "run"] and "-y" in cmd
    assert [cmd[i + 1] for i, x in enumerate(cmd) if x == "--ae"] == [
        "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}", "CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000"]
    assert [cmd[i + 1] for i, x in enumerate(cmd) if x == "--ak"] == ["version=2.1.293", "disable_web_search=true"]
    for flag, value in (("-p", str(tmp_path / "copies" / "agent" / TASK)), ("-a", "claude-code"),
                        ("-m", "anthropic/claude-sonnet-5-5"), ("--effort", "high"),
                        ("--agent-timeout-multiplier", "1.0"), ("--agent-setup-timeout-multiplier", "2.0"),
                        ("--ek", "keep_containers=true"), ("-n", "1"), ("-k", "1"), ("-r", "0"),
                        ("-o", str(tmp_path / "jobs"))):
        assert cmd[cmd.index(flag) + 1] == value
    assert "--no-force-build" in cmd and "--force-build" not in cmd
    assert not any("resume" in x for x in cmd) and not any("FORCE_OAUTH" in x for x in cmd)


def test_worst_case_hours_and_weekly_need():
    assert run.worst_case_hours(INFO) == 5.0
    assert run.worst_case_hours(dict(INFO, rounds=5, agent_timeout_sec=3600.0)) == 5.0
    assert run.needed_weekly(5.0) == pytest.approx(0.0635)
    assert run.needed_weekly(0) == 0


def test_headroom_limits_leave_room_for_the_worst_case():
    assert run.headroom_limits(INFO) == (0.41, 0.8365)
    assert run.headroom_limits(dict(INFO, agent_timeout_sec=3600.0)) == (0.41, 0.773)
    assert run.headroom_limits(dict(INFO, rounds=2)) == (0.802, 0.8873)


@pytest.mark.parametrize("busy,seconds", [
    ({"status": "allowed", "five_hour": 0.1, "seven_day": 0.85, "seven_day_resets_at": 5000}, 4960),
    ({"status": "allowed", "five_hour": 0.45, "five_hour_resets_at": 3000, "seven_day": 0.2}, 2960),
])
def test_run_trial_waits_until_both_windows_have_room(tmp_path, busy, seconds):
    paths, host, slept = ready(tmp_path), FakeHost(), []
    probes = iter([busy, {"status": "allowed", "five_hour": 0.1, "seven_day": 0.8}])
    record = go(paths, host, probe=lambda: next(probes), now=lambda: 100.0, slept=slept)
    assert slept == [seconds] and ran_harbor(host)
    assert record["usage_before"]["seven_day"] == 0.8 and record["valid"] is True


def test_a_valid_job_is_recorded_with_versions_ledger_and_cleanup(tmp_path, pinned_image):
    paths, host = ready(tmp_path), FakeHost()
    record = go(paths, host)
    assert pinned_image == [config.image_tag(TASK)]
    assert RECORD_KEYS <= set(record)
    assert record["valid"] is True and record["invalid_reason"] is None
    assert (record["job_name"], record["phase"], record["task"], record["arm"], record["attempt"]) == (
        f"main__{TASK}__horizon__a1", "main", TASK, "horizon", 1)
    assert (record["started"], record["finished"], record["exit_code"]) == (10.0, 20.0, 0)
    assert record["image_id"] == record["container_image"] == IMAGE and record["freeze"] == "abc123"
    assert (record["harbor_version"], record["claude_code_version"]) == ("0.24.0", "2.1.293")
    assert record["job_dir"] == str(paths.jobs / TRIAL.job_name)
    assert record["trial_dir"] == str(paths.jobs / TRIAL.job_name / TRIAL_NAME)
    assert record["command"] == run.harbor_command(TRIAL, paths)
    assert record["ledger"]["copied"] == {"/app/.claude/harness": str(paths.ledgers / TRIAL.job_name / "0")}
    assert record["usage_after"]["seven_day"] == 0.3
    assert ["docker", "rm", "-f", "c1"] in host.calls
    assert host.harbor_kwargs["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "secret-token"
    saved = (paths.records / f"{TRIAL.job_name}.json").read_text()
    assert json.loads(saved) == record and "secret-token" not in saved
    assert (paths.logs / f"{TRIAL.job_name}.log").exists()


def started(tmp_path, name, *events, exception=None, tail=""):
    agent = tmp_path / name / "agent"
    agent.mkdir(parents=True)
    (agent / "claude-code.txt").write_text(lines(*events) + tail)
    return {"name": name, "exception": exception, "agent_started": "2026-10-09T12:00:00Z", "agent_dir": str(agent)}


def not_started(name, exception=None):
    return {"name": name, "exception": exception, "agent_started": None, "agent_dir": None}


def test_classify_fixture_streams(tmp_path):
    ok = started(tmp_path, "round-1", *CLEAN)

    def read(*steps, trial_exception=None):
        return {"steps": list(steps), "trial_exception": trial_exception}

    assert run.classify(None, False) == "infrastructure"
    assert run.classify(read(ok), False) is None
    assert run.classify(read(ok), True) == "host_slept"
    assert run.classify(read(ok, started(tmp_path, "round-2", ALLOWED, INIT, REJECTED, DONE)), False) == "usage_limit"
    assert run.classify(read(ok, started(tmp_path, "round-3", *CLEAN, exception="ApiUsageLimitError")),
                        False) == "usage_limit"
    assert run.classify(read(ok, started(tmp_path, "round-4", ALLOWED, INIT, SPOKE, API_500)), False) == "api_error"
    assert run.classify(read(ok, started(tmp_path, "round-5", ALLOWED, INIT, OVERLOADED, SPOKE, DONE)), False) is None
    assert run.classify(read(not_started("round-1", "RuntimeError")), False) == "infrastructure"
    assert run.classify(read(ok, not_started("round-2", "RuntimeError")), False) == "infrastructure"
    assert run.classify(read(trial_exception="EnvironmentStartTimeoutError"), False) == "infrastructure"
    assert run.classify(read(ok, trial_exception={"exception_type": "CancelledError"}), False) == "interrupted"
    timed_out = started(tmp_path, "round-6", ALLOWED, INIT, SPOKE, exception="AgentTimeoutError")
    assert run.classify(read(ok, timed_out, not_started("round-7")), False) is None
    cut = started(tmp_path, "round-8", ALLOWED, INIT, SPOKE, exception="AgentTimeoutError",
                  tail='{"type": "rate_limit_event", "rate_limit_info": {"status": "allo')
    assert run.classify(read(ok, cut), False) is None
    said = started(tmp_path, "round-9", ALLOWED, INIT, SPOKE, tail="API Error: Repeated 529 Overloaded errors\n")
    assert run.classify(read(ok, said), False) == "api_error"


@pytest.mark.parametrize("events", [(), CLEAN], ids=["empty-stream", "ordinary-stream"])
@pytest.mark.parametrize("exception,expected", [
    ("NonZeroAgentExitCodeError", "infrastructure"),
    ("RuntimeError", "infrastructure"),
    ({"exception_type": "RuntimeError", "exception_message": ""}, "infrastructure"),
    ("AgentAuthenticationError", "api_error"),
    ("ApiInternalServerError", "api_error"),
    ("NetworkConnectionError", "api_error"),
    ("VerifierTimeoutError", None),
    ("ContextWindowExceededError", None),
    ("AgentTimeoutError", None),
])
def test_an_exception_on_a_started_step_is_classified_by_its_harbor_type(tmp_path, exception, expected, events):
    failing = started(tmp_path, "round-2", *events, exception=exception)
    read = {"steps": [started(tmp_path, "round-1", *CLEAN), failing], "trial_exception": None}
    assert run.classify(read, False) == expected


def test_every_listed_exception_type_is_classified_as_listed(tmp_path):
    for name in run.API_EXCEPTIONS:
        read = {"steps": [started(tmp_path, f"api-{name}", *CLEAN, exception=name)], "trial_exception": None}
        assert run.classify(read, False) == "api_error", name
    for name in run.MODEL_OUTCOMES:
        read = {"steps": [started(tmp_path, f"model-{name}", *CLEAN, exception=name)], "trial_exception": None}
        assert run.classify(read, False) is None, name


def test_usage_limit_in_a_later_round_invalidates_the_job(tmp_path):
    host = FakeHost(steps=[step("round-1"), step("round-2", (ALLOWED, INIT, REJECTED, DONE),
                                                     "NonZeroAgentExitCodeError")])
    record = go(ready(tmp_path), host)
    assert (record["valid"], record["invalid_reason"]) == (False, "usage_limit")


@pytest.mark.parametrize("exception,reason", [
    ("RuntimeError", "infrastructure"),
    ("NonZeroAgentExitCodeError", "infrastructure"),
    ("AgentAuthenticationError", "api_error"),
    ("AgentTimeoutError", None),
    ("VerifierTimeoutError", None),
])
def test_the_harbor_exception_on_a_started_round_decides_whether_the_job_is_valid(tmp_path, exception, reason):
    host = FakeHost(steps=[step("round-1"), step("round-2", exception=exception)])
    record = go(ready(tmp_path), host)
    assert (record["valid"], record["invalid_reason"]) == (reason is None, reason)


def test_a_job_without_a_trial_result_is_infrastructure_and_cleaned(tmp_path):
    host = FakeHost(write_result=False, exit_code=1)
    record = go(ready(tmp_path), host)
    assert (record["valid"], record["invalid_reason"], record["exit_code"]) == (False, "infrastructure", 1)
    assert ["docker", "rm", "-f", "c1"] in host.calls and record["ledger"] is None


def test_harbor_failing_before_the_job_exists_stops_without_spending_the_attempt(tmp_path):
    paths = ready(tmp_path)
    with pytest.raises(run.InfrastructureFailure):
        go(paths, FakeHost(create_job=False, exit_code=2))
    assert not (paths.records / f"{TRIAL.job_name}.json").exists()


def test_setup_failure_before_any_agent_is_infrastructure(tmp_path):
    record = go(ready(tmp_path), FakeHost(steps=[step("round-1", exception="RuntimeError", started=False)]))
    assert (record["invalid_reason"], record["ledger"]) == ("infrastructure", None)


def test_a_host_sleep_during_the_job_invalidates_it(tmp_path):
    record = go(ready(tmp_path), FakeHost(sleeps=("before", "after")))
    assert record["invalid_reason"] == "host_slept"


def test_a_container_on_another_image_is_infrastructure(tmp_path):
    record = go(ready(tmp_path), FakeHost(container_image="sha256:" + "b" * 64))
    assert record["invalid_reason"] == "infrastructure"


def test_an_existing_record_is_returned_without_running(tmp_path):
    paths, host = ready(tmp_path), FakeHost()
    (paths.records / f"{TRIAL.job_name}.json").write_text(json.dumps({"job_name": TRIAL.job_name, "valid": True}))
    assert go(paths, host)["valid"] is True and host.calls == []


def test_a_job_directory_without_a_record_is_recorded_as_interrupted(tmp_path):
    paths, host = ready(tmp_path), FakeHost()
    (paths.jobs / TRIAL.job_name / TRIAL_NAME).mkdir(parents=True)
    record = go(paths, host, probe=lambda: pytest.fail("an interruption is recorded without waiting"))
    assert (record["valid"], record["invalid_reason"]) == (False, "interrupted")
    assert ["docker", "rm", "-f", "c1"] in host.calls and not ran_harbor(host)
    assert json.loads((paths.records / f"{TRIAL.job_name}.json").read_text()) == record


def test_running_trial_containers_block_a_new_job(tmp_path):
    host = FakeHost(running="r1\n")
    with pytest.raises(run.RunnerBusy):
        go(ready(tmp_path), host)
    assert not ran_harbor(host)


@pytest.mark.parametrize("kwargs,error", [
    (dict(image="sha256:" + "c" * 64), run.ImageChanged),
    (dict(ok=False), run.NotValidated),
    (dict(skill=False), run.MissingInput),
])
def test_bad_inputs_stop_before_harbor(tmp_path, kwargs, error):
    host = FakeHost()
    with pytest.raises(error):
        go(ready(tmp_path, **kwargs), host)
    assert not ran_harbor(host)
    assert not (tmp_path / "runs" / "records" / f"{TRIAL.job_name}.json").exists()


def test_control_needs_no_skill_and_a_missing_prompt_stops(tmp_path):
    paths = ready(tmp_path, skill=False)
    assert go(paths, FakeHost(), trial=dataclasses.replace(TRIAL, arm="control"))["valid"] is True
    paths.prompt(TASK, "horizon").unlink()
    paths.skill.mkdir(parents=True)
    (paths.skill / "SKILL.md").write_text("---\nname: horizon\n---\n")
    with pytest.raises(run.MissingInput):
        go(paths, FakeHost())


def fake_runs(monkeypatch, outcomes):
    """Patch run_trial: outcomes maps (arm, attempt) to an invalid_reason; anything missing is valid."""
    calls = []

    def fake(trial, paths, token, freeze, **kwargs):
        calls.append((trial.task, trial.arm, trial.attempt))
        reason = outcomes.get((trial.arm, trial.attempt))
        return {"job_name": trial.job_name, "valid": reason is None, "invalid_reason": reason}

    monkeypatch.setattr(run, "run_trial", fake)
    monkeypatch.setattr(run, "prepare", lambda info, paths: paths.copy(info["task"]))
    return calls


def phase(tmp_path, tasks=(TASK,)):
    infos = {task: dict(INFO, task=task) for task in tasks}
    return run.run_phase("main", list(tasks), paths=run.Paths(tmp_path).ensure(), token="t", freeze="f",
                         probe=lambda: HEADROOM, infos=infos, log=lambda message: None)


def test_run_phase_runs_each_task_in_its_seeded_arm_order(tmp_path, monkeypatch):
    calls = fake_runs(monkeypatch, {})
    other = "theme_d5_w1_data_engineering_greenfield_implementation"
    result = phase(tmp_path, tasks=(TASK, other))
    expected = [(t, arm, 1) for t in (TASK, other) for arm in order.arm_order(t, config.SEED)]
    assert calls == expected and result["dropped"] == [] and len(result["records"]) == 4


def test_run_phase_refuses_a_task_missing_from_the_dataset(tmp_path, monkeypatch):
    calls = fake_runs(monkeypatch, {})
    with pytest.raises(run.MissingInput):
        run.run_phase("main", [TASK, "theme_d0_w0_unknown"], paths=run.Paths(tmp_path).ensure(), token="t",
                      freeze="f", probe=lambda: HEADROOM, infos={TASK: INFO}, log=lambda message: None)
    assert calls == []


def test_an_invalid_run_is_retried_once_with_the_next_attempt(tmp_path, monkeypatch):
    first, second = order.arm_order(TASK, config.SEED)
    calls = fake_runs(monkeypatch, {(first, 1): "api_error"})
    result = phase(tmp_path)
    assert calls == [(TASK, first, 1), (TASK, first, 2), (TASK, second, 1)]
    assert result["dropped"] == [] and not (tmp_path / "deviations.md").exists()


def test_two_invalid_runs_drop_the_task_once_and_stop_the_phase(tmp_path, monkeypatch):
    first, second = order.arm_order(TASK, config.SEED)
    calls = fake_runs(monkeypatch, {(first, 1): "usage_limit", (first, 2): "infrastructure"})
    with pytest.raises(run.TaskDropped):
        phase(tmp_path)
    assert calls == [(TASK, first, 1), (TASK, first, 2)]
    text = (tmp_path / "deviations.md").read_text()
    assert text == (f"- main {TASK}: dropped after two invalid runs of the {first} arm "
                    f"(a1: usage_limit; a2: infrastructure)\n")
    assert run.dropped_tasks(run.Paths(tmp_path), "main") == [TASK]
    assert run.dropped_tasks(run.Paths(tmp_path), "dry") == []
    calls.clear()
    assert phase(tmp_path)["dropped"] == [TASK]
    assert calls == [] and (tmp_path / "deviations.md").read_text() == text


def test_a_second_arm_that_fails_twice_drops_the_task(tmp_path, monkeypatch):
    first, second = order.arm_order(TASK, config.SEED)
    calls = fake_runs(monkeypatch, {(second, 1): "interrupted", (second, 2): "api_error"})
    with pytest.raises(run.TaskDropped):
        phase(tmp_path)
    assert calls == [(TASK, first, 1), (TASK, second, 1), (TASK, second, 2)]
    assert run.dropped_tasks(run.Paths(tmp_path), "main") == [TASK]


def test_a_later_attempt_never_reruns_an_arm_that_already_has_a_valid_record(tmp_path):
    paths, host, messages = ready(tmp_path), FakeHost(), []
    first, second = order.arm_order(TASK, config.SEED)
    for arm, valid in ((first, True), (second, False)):
        name = config.job_name("main", TASK, arm, 1)
        (paths.records / f"{name}.json").write_text(json.dumps(
            {"job_name": name, "phase": "main", "task": TASK, "arm": arm, "attempt": 1, "valid": valid,
             "invalid_reason": None if valid else "api_error"}))

    def relaunch(attempt):
        return run.run_phase("main", [TASK], attempt=attempt, paths=paths, token="t", freeze="f",
                             probe=lambda: HEADROOM, infos={TASK: INFO}, run=host, now=lambda: 100.0,
                             sleep=lambda seconds: None, log=messages.append)

    result = relaunch(3)
    harbor_jobs = [c[c.index("--job-name") + 1] for c in host.calls if c[:2] == ["harbor", "run"]]
    assert harbor_jobs == [config.job_name("main", TASK, second, 3)]
    assert [r["job_name"] for r in result["records"]] == [config.job_name("main", TASK, first, 1),
                                                           config.job_name("main", TASK, second, 3)]
    assert [m for m in messages if "valid record" in m] == [
        f"{TASK} {first}: a valid record exists ({config.job_name('main', TASK, first, 1)}); not run again"]
    host.calls.clear()
    relaunch(5)
    assert host.calls == []


def test_prepare_makes_the_agent_copy_and_prompts_once(tmp_path, monkeypatch):
    paths = run.Paths(tmp_path).ensure()
    made = []

    def make_copy(src, dest, *, kind, image_tag):
        made.append((Path(src), Path(dest).name, kind, image_tag))
        Path(dest).mkdir(parents=True)
        (Path(dest) / "task.toml").write_text("")
        return "digest"

    monkeypatch.setattr(copies, "make_copy", make_copy)
    stale = paths.copy(TASK).with_name(TASK + ".tmp")
    stale.mkdir(parents=True)
    info = dict(INFO, agent_timeout_sec=3600.0)
    assert run.prepare(info, paths) == paths.copy(TASK)
    assert made == [(Path(INFO["dir"]), TASK + ".tmp", "agent", config.image_tag(TASK))]
    assert (paths.copy(TASK) / "task.toml").exists() and not stale.exists()
    for arm in config.ARMS:
        assert paths.prompt(TASK, arm).read_text().strip() == config.prompt_text(arm, 60)
    paths.prompt(TASK, "control").write_text("kept")
    run.prepare(info, paths)
    assert len(made) == 1 and paths.prompt(TASK, "control").read_text() == "kept"


def test_phase_tasks(tmp_path):
    prereg = tmp_path / "prereg.json"
    prereg.write_text(json.dumps({"tasks": [TASK, "theme_d5_w1_data_engineering_greenfield_implementation"]}))
    assert run.phase_tasks("dry", prereg) == [config.WALKTHROUGH]
    assert run.phase_tasks("main", prereg) == [TASK, "theme_d5_w1_data_engineering_greenfield_implementation"]
    assert run.phase_tasks("main", prereg, only=TASK) == [TASK]
    with pytest.raises(SystemExit):
        run.phase_tasks("main", prereg, only=config.WALKTHROUGH)


OTHER = "theme_d5_w1_data_engineering_greenfield_implementation"
RESERVE = ["theme_d8_w5_cloud_devops_integration_e2e_wiring", "theme_d9_w11_security_automation_scripting"]


def drop(paths, task):
    run.note_drop(paths, "main", task, "control", [(1, "infrastructure"), (2, "infrastructure")])


def test_one_dropped_main_task_brings_in_the_first_reserve(tmp_path):
    paths = run.Paths(tmp_path)
    prereg = tmp_path / "prereg.json"
    prereg.write_text(json.dumps({"tasks": [TASK, OTHER], "reserve": RESERVE}))
    assert run.phase_tasks("main", prereg, paths=paths) == [TASK, OTHER]
    drop(paths, TASK)
    assert run.phase_tasks("main", prereg, paths=paths) == [TASK, OTHER, RESERVE[0]]
    assert run.phase_tasks("main", prereg, only=RESERVE[0], paths=paths) == [RESERVE[0]]
    with pytest.raises(SystemExit):
        run.phase_tasks("main", prereg, only=RESERVE[1], paths=paths)
    assert run.phase_tasks("dry", prereg, paths=paths) == [config.WALKTHROUGH]
    assert run.main_tasks({"tasks": [TASK], "reserve": RESERVE}, [TASK]) == [TASK, RESERVE[0]]


def test_two_drops_with_one_reserve_bring_in_only_that_reserve(tmp_path):
    paths = run.Paths(tmp_path)
    prereg = tmp_path / "prereg.json"
    prereg.write_text(json.dumps({"tasks": [TASK, OTHER], "reserve": RESERVE[:1]}))
    drop(paths, TASK)
    drop(paths, OTHER)
    assert run.phase_tasks("main", prereg, paths=paths) == [TASK, OTHER, RESERVE[0]]
    no_reserve = tmp_path / "old.json"
    no_reserve.write_text(json.dumps({"tasks": [TASK, OTHER]}))
    assert run.phase_tasks("main", no_reserve, paths=paths) == [TASK, OTHER]


def test_main_prints_both_arms_in_seeded_order(tmp_path, capsys):
    assert run.main(["--phase", "dry", "--runs", str(tmp_path), "--print-commands"]) == 0
    printed = capsys.readouterr().out.splitlines()
    arms = order.arm_order(config.WALKTHROUGH, config.SEED)
    assert len(printed) == 2
    for line, arm in zip(printed, arms):
        assert f"--job-name dry__{config.WALKTHROUGH}__{arm}__a1 " in line
        assert ("--skill" in line) == (arm == "horizon")
    assert not (tmp_path / "records").exists()


def test_main_checks_the_freeze_before_reading_the_token(tmp_path, monkeypatch):
    prereg = tmp_path / "prereg.json"
    prereg.write_text(json.dumps({"tasks": [TASK]}))
    monkeypatch.setattr(run, "read_token", lambda *a, **k: pytest.fail("token read before the freeze check"))

    class Unfrozen(RuntimeError):
        pass

    def require_freeze(git):
        raise Unfrozen("tag evo-prereg is missing")

    with pytest.raises(Unfrozen):
        run.main(["--phase", "main", "--runs", str(tmp_path / "runs"), "--prereg", str(prereg)],
                 require_freeze=require_freeze)


class TokenRead(Exception):
    """Raised by the patched read_token: main got past every check that comes before the token."""


def frozen_main(paths, prereg, monkeypatch, **fakes):
    def token(*args, **kwargs):
        raise TokenRead

    monkeypatch.setattr(run, "read_token", token)
    # by default the prereg file is the frozen record and the run directory matches it; a test overrides either
    fakes = {"require_frozen_record": lambda path, git: json.loads(Path(path).read_text()),
             "verify_runs": lambda record, runs, tasks: None, **fakes}
    return run.main(["--phase", "main", "--runs", str(paths.root), "--prereg", str(prereg)],
                    require_freeze=lambda git: "abc", **fakes)


def test_main_refuses_a_validated_image_that_differs_from_the_preregistered_one(tmp_path, monkeypatch):
    paths = ready(tmp_path)
    prereg = tmp_path / "prereg.json"
    prereg.write_text(json.dumps({"tasks": [TASK], "task_details": {TASK: {"image_id": "sha256:" + "d" * 64}}}))
    with pytest.raises(run.ImageChanged, match=TASK):
        frozen_main(paths, prereg, monkeypatch)
    prereg.write_text(json.dumps({"tasks": [TASK], "task_details": {TASK: {"image_id": IMAGE}}}))
    with pytest.raises(TokenRead):
        frozen_main(paths, prereg, monkeypatch)


def test_main_checks_the_preregistered_image_of_a_reserve_once_it_is_in_play(tmp_path, monkeypatch):
    paths = ready(tmp_path)
    (paths.validation / f"{RESERVE[0]}.json").write_text(json.dumps(
        {"task": RESERVE[0], "image_id": IMAGE, "arch": "arm64", "ok": True, "reason": None}))
    prereg = tmp_path / "prereg.json"
    details = {TASK: {"image_id": IMAGE}, RESERVE[0]: {"image_id": "sha256:" + "e" * 64}}
    prereg.write_text(json.dumps({"tasks": [TASK], "reserve": RESERVE[:1], "task_details": details}))
    with pytest.raises(TokenRead):  # the reserve is not in play yet
        frozen_main(paths, prereg, monkeypatch)
    drop(paths, TASK)
    with pytest.raises(run.ImageChanged, match=RESERVE[0]):
        frozen_main(paths, prereg, monkeypatch)

class Unfrozen(RuntimeError):
    """Raised by a fake freeze check."""


def test_main_takes_its_tasks_and_image_pins_from_the_frozen_record_not_the_prereg_file(tmp_path, monkeypatch):
    paths = ready(tmp_path)
    prereg = tmp_path / "prereg.json"
    prereg.write_text(json.dumps({"tasks": [OTHER], "task_details": {OTHER: {"image_id": "sha256:" + "f" * 64}}}))
    frozen = {"tasks": [TASK], "task_details": {TASK: {"image_id": IMAGE}}}
    asked = []

    def require_frozen_record(path, git):
        asked.append(Path(path))
        return frozen

    with pytest.raises(TokenRead):  # OTHER was never validated: the file's list would stop the run first
        frozen_main(paths, prereg, monkeypatch, require_frozen_record=require_frozen_record)
    assert asked == [prereg]


def test_main_stops_when_the_prereg_file_is_not_the_frozen_record(tmp_path, monkeypatch):
    paths = ready(tmp_path)
    prereg = tmp_path / "prereg.json"
    prereg.write_text(json.dumps({"tasks": [TASK], "task_details": {TASK: {"image_id": IMAGE}}}))

    def refuse(path, git):
        raise Unfrozen("prereg.json differs from the tagged one")

    with pytest.raises(Unfrozen):  # not TokenRead: the token is not read
        frozen_main(paths, prereg, monkeypatch, require_frozen_record=refuse)


def test_main_verifies_the_run_directory_against_the_record_after_the_image_pins_and_before_the_token(
        tmp_path, monkeypatch):
    paths = ready(tmp_path)
    (paths.validation / f"{RESERVE[0]}.json").write_text(json.dumps(
        {"task": RESERVE[0], "image_id": IMAGE, "arch": "arm64", "ok": True, "reason": None}))
    prereg = tmp_path / "prereg.json"
    frozen = {"tasks": [TASK], "reserve": RESERVE[:1], "task_details": {TASK: {"image_id": IMAGE}}}
    prereg.write_text(json.dumps(frozen))
    calls = []

    def verify_runs(record, runs, tasks):
        calls.append((record, Path(runs), list(tasks)))
        raise Unfrozen("the bundle differs")

    with pytest.raises(Unfrozen):  # not TokenRead: the token is not read
        frozen_main(paths, prereg, monkeypatch, verify_runs=verify_runs)
    assert calls == [(frozen, paths.root, [TASK])]
    drop(paths, TASK)  # a drop brings the reserve into the list that is verified
    frozen["task_details"][RESERVE[0]] = {"image_id": "sha256:" + "e" * 64}
    prereg.write_text(json.dumps(frozen))
    with pytest.raises(run.ImageChanged, match=RESERVE[0]):  # the image pins come first
        frozen_main(paths, prereg, monkeypatch, verify_runs=verify_runs)
    assert len(calls) == 1
    frozen["task_details"][RESERVE[0]] = {"image_id": IMAGE}
    prereg.write_text(json.dumps(frozen))
    with pytest.raises(Unfrozen):
        frozen_main(paths, prereg, monkeypatch, verify_runs=verify_runs)
    assert calls[-1][2] == [TASK, RESERVE[0]]

# Harbor 0.24.0 raises these three from claude's terminal is_error result line, the line the stream's API-error
# rule reads
MODEL_ERROR_LINES = {
    "AgentSafetyRefusalError": {
        "type": "result", "subtype": "success", "is_error": True,
        "result": "API Error: Claude Code is unable to respond to this request, which appears to violate our Usage "
                  "Policy (https://www.anthropic.com/legal/aup). Please double press esc to edit your last message "
                  "or start a new session for Claude Code to assist with a different task."},
    "ContextWindowExceededError": {
        "type": "result", "subtype": "success", "is_error": True, "api_error_status": 400,
        "result": 'API Error: 400 {"type":"error","error":{"type":"invalid_request_error","message":"prompt is too '
                  'long: 210000 tokens > 200000 maximum"}}'},
    "OutputTokenExceededError": {
        "type": "result", "subtype": "success", "is_error": True,
        "result": "API Error: Claude's response exceeded the 128000 output token maximum. To configure this behavior, "
                  "set the CLAUDE_CODE_MAX_OUTPUT_TOKENS environment variable."},
}


@pytest.mark.parametrize("exception", sorted(MODEL_ERROR_LINES))
def test_a_model_outcome_harbor_read_from_the_terminal_error_line_keeps_the_job_valid(tmp_path, exception):
    events = (ALLOWED, INIT, SPOKE, MODEL_ERROR_LINES[exception])
    typed = started(tmp_path, "round-2", *events, exception=exception)
    assert run.classify({"steps": [started(tmp_path, "round-1", *CLEAN), typed], "trial_exception": None},
                        False) is None
    # the same line on a step Harbor recorded no exception for is still an API error
    plain = started(tmp_path, "round-3", *events)
    assert run.classify({"steps": [plain], "trial_exception": None}, False) == "api_error"


@pytest.mark.parametrize("exception", run.MODEL_OUTCOMES)
def test_usage_limit_evidence_in_the_stream_beats_a_model_outcome_type(tmp_path, exception):
    limited = started(tmp_path, "round-1", ALLOWED, INIT, SPOKE, REJECTED, DONE, exception=exception)
    assert run.classify({"steps": [limited], "trial_exception": None}, False) == "usage_limit"

@pytest.mark.parametrize("info", [None, {}, {"status": "allowed", "five_hour": None, "seven_day": 0.2},
                                  {"status": "allowed", "five_hour": 0.1, "seven_day": None}],
                         ids=["no-info", "empty", "no-five-hour", "no-seven-day"])
@pytest.mark.parametrize("phase", run.PHASES)
def test_a_usage_probe_without_rate_limit_data_starts_no_job_and_spends_no_attempt(tmp_path, info, phase):
    paths, host = ready(tmp_path), FakeHost()
    trial = dataclasses.replace(TRIAL, phase=phase)
    with pytest.raises(run.InfrastructureFailure, match="usage probe returned no rate-limit data"):
        go(paths, host, trial=trial, probe=lambda: info)
    assert not ran_harbor(host) and not (paths.jobs / trial.job_name).exists()
    assert not (paths.records / f"{trial.job_name}.json").exists()

def test_a_dry_drop_goes_to_findings_and_a_dry_relaunch_runs_the_walkthrough_again(tmp_path, monkeypatch):
    walk = config.WALKTHROUGH
    first, second = order.arm_order(walk, config.SEED)
    calls = fake_runs(monkeypatch, {(first, 1): "api_error", (first, 2): "api_error"})
    paths = run.Paths(tmp_path).ensure()

    def dry(attempt):
        return run.run_phase("dry", [walk], attempt=attempt, paths=paths, token="t", freeze="pre-freeze",
                             probe=lambda: HEADROOM, infos={walk: dict(INFO, task=walk)}, log=lambda message: None)

    with pytest.raises(run.TaskDropped):
        dry(1)
    # the pre-freeze log, never the post-freeze deviations.md that the report copies
    assert (tmp_path / "findings.md").read_text() == (
        f"- dry {walk}: dropped after two invalid runs of the {first} arm (a1: api_error; a2: api_error)\n")
    assert not (tmp_path / "deviations.md").exists()
    calls.clear()
    assert dry(3)["dropped"] == []
    assert calls == [(walk, first, 3), (walk, second, 3)]


def test_a_main_drop_still_goes_to_deviations_and_is_skipped_on_relaunch(tmp_path, monkeypatch):
    first, _ = order.arm_order(TASK, config.SEED)
    calls = fake_runs(monkeypatch, {(first, 1): "infrastructure", (first, 2): "infrastructure"})
    with pytest.raises(run.TaskDropped):
        phase(tmp_path)
    assert run.dropped_tasks(run.Paths(tmp_path), "main") == [TASK]
    assert not (tmp_path / "findings.md").exists()
    calls.clear()
    assert phase(tmp_path)["dropped"] == [TASK] and calls == []
