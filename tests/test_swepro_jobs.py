import json
import subprocess

import pytest

from bench.swepro import config, jobs

TASK = config.SMOKE_TASK


def trial(tmp_path, *, reward=1.0, exception=None, events=None, notes=None, patch=b"diff", verifier=True):
    job = tmp_path / "job"
    t = job / f"{TASK[:30]}__abc1234"
    (t / "agent").mkdir(parents=True)
    result = {
        "task_name": f"swebench-pro/{TASK}",
        "exception_info": {"exception_type": exception} if exception else None,
        "verifier_result": {"rewards": {"reward": reward}} if verifier else None,
        "agent_execution": {"started_at": "2026-10-14T05:25:36Z", "finished_at": "2026-10-14T05:26:06Z"},
        "verifier": {"started_at": "2026-10-14T05:26:06Z", "finished_at": "2026-10-14T05:29:46Z"},
    }
    (t / "result.json").write_text(json.dumps(result))
    lines = events if events is not None else [
        {"type": "system", "subtype": "init", "claude_code_version": "2.1.293", "model": "claude-sonnet-5-5"},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash",
                                                       "input": {"command": "pytest test/units"}}]}},
        {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.25,
         "modelUsage": {"claude-sonnet-5-5": {"inputTokens": 10, "cacheReadInputTokens": 5,
                                              "cacheCreationInputTokens": 1, "outputTokens": 7}}},
    ]
    (t / "agent" / "claude-code.txt").write_text("".join(json.dumps(e) + "\n" for e in lines))
    if notes is not None:
        (t / "agent" / "notes.json").write_text(json.dumps(notes))
    if patch is not None:
        (t / "agent" / "model.patch").write_bytes(patch)
    return job, t


def test_claude_command_pins_model_version_network_and_kwargs(tmp_path):
    cmd = jobs.harbor_command(tmp_path / "task", "test__t__plain__a1", tmp_path / "jobs", jobs.ARM_AGENT,
                              {"tools_dir": "/x/tools", "bundle_dir": "/x/b"}, claude=True)
    joined = " ".join(cmd)
    assert cmd[:4] == ["harbor", "run", "-p", str(tmp_path / "task")]
    for part in (f"-a {jobs.ARM_AGENT}", f"-m {config.MODEL}", f"--effort {config.EFFORT}",
                 f"--ak version={config.CLAUDE_CODE_VERSION}", "--ak disable_web_search=true",
                 "--ae CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}",
                 f"--ae CLAUDE_CODE_MAX_OUTPUT_TOKENS={config.MAX_OUTPUT_TOKENS}",
                 f"--allow-agent-host {config.ALLOW_HOST}", "--ak bundle_dir=/x/b", "--ak tools_dir=/x/tools",
                 "-n 1 -k 1 -r 0", "--job-name test__t__plain__a1", "-y"):
        assert part in joined, part


def test_oracle_command_has_no_model_or_token(tmp_path):
    cmd = jobs.harbor_command(tmp_path / "task", "validate__t__oracle__a1", tmp_path / "jobs", "oracle", {},
                              claude=False)
    assert "-m" not in cmd and not any("OAUTH" in c for c in cmd)


def test_job_env_strips_api_keys_and_adds_the_repo_to_pythonpath(tmp_path):
    env = jobs.job_env("tok", base={"ANTHROPIC_API_KEY": "k", "PATH": "/bin"}, extra_path=[tmp_path])
    assert "ANTHROPIC_API_KEY" not in env and env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"
    assert env["PYTHONPATH"].split(":") == [str(config.REPO_ROOT), str(tmp_path)]


def test_read_trial_collects_reward_cost_tokens_versions_and_timing(tmp_path):
    job, t = trial(tmp_path, notes={"hash": "abc", "claude_dir": True, "memory_files": 2})
    r = jobs.read_trial(job)
    assert r["trial_dir"] == str(t)
    assert (r["reward"], r["exception"], r["cost_usd"]) == (1.0, None, 0.25)
    assert (r["tokens_in"], r["tokens_out"]) == (16, 7)
    assert (r["claude_version"], r["model"]) == ("2.1.293", "claude-sonnet-5-5")
    assert (r["agent_sec"], r["verifier_sec"]) == (30.0, 220.0)
    assert r["notes"] == {"hash": "abc", "claude_dir": True, "memory_files": 2}
    assert r["patch_bytes"] == 4 and r["audit_tests"] is False


def test_read_trial_without_a_result_is_none(tmp_path):
    (tmp_path / "job").mkdir()
    assert jobs.read_trial(tmp_path / "job") is None


def test_a_timed_out_run_has_no_final_cost_but_keeps_its_reward(tmp_path):
    job, _ = trial(tmp_path, reward=0.0, exception="AgentTimeoutError")
    r = jobs.read_trial(job)
    assert r["cost_usd"] is None and r["reward"] == 0.0 and r["exception"] == "AgentTimeoutError"


def test_reading_a_test_or_solution_path_raises_the_audit_flag(tmp_path):
    events = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": "/tests/config.json"}}]}}]
    job, _ = trial(tmp_path, events=events)
    assert jobs.read_trial(job)["audit_tests"] is True


@pytest.mark.parametrize("exception,expected", [
    (None, None),
    ("AgentTimeoutError", None),
    ("NonZeroAgentExitCodeError", None),
    ("VerifierTimeoutError", None),
    ("ApiOverloadedError", "api_error"),
    ("ApiUsageLimitError", "usage_limit"),
    ("CancelledError", "interrupted"),
    ("RuntimeError", "infrastructure"),
    ("EnvironmentStartTimeoutError", "infrastructure"),
])
def test_classify_reruns_only_what_is_not_the_models_doing(tmp_path, exception, expected):
    job, _ = trial(tmp_path, exception=exception)
    assert jobs.classify(jobs.read_trial(job)) == expected


def test_classify_a_missing_result_as_infrastructure():
    assert jobs.classify(None) == "infrastructure"


def test_usage_limit_text_in_the_stream_is_a_usage_stop(tmp_path):
    events = [{"type": "result", "is_error": True, "result": "You've hit your usage limit"}]
    job, _ = trial(tmp_path, exception="NonZeroAgentExitCodeError", events=events)
    assert jobs.classify(jobs.read_trial(job)) == "usage_limit"


def test_pull_asks_for_amd64(tmp_path):
    calls = []
    jobs.pull_image("img:tag", run=lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0))
    assert calls == [["docker", "pull", "-q", "--platform", "linux/amd64", "img:tag"]]


def test_a_failed_pull_raises():
    with pytest.raises(jobs.JobError):
        jobs.pull_image("img:tag", run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "nope"))


def test_run_job_writes_the_log_and_returns_the_trial(tmp_path):
    made = []

    def run(cmd, **kw):
        kw["stdout"].write("harbor output\n")
        made.append(trial(tmp_path))
        return subprocess.CompletedProcess(cmd, 0)

    log = tmp_path / "logs" / "x.log"
    r = jobs.run_job(["harbor", "run"], tmp_path / "job", env={}, log_path=log, run=run)
    assert r["trial_dir"] == str(made[0][1]) and "harbor output" in log.read_text()


def test_run_job_refuses_to_reuse_a_job_directory(tmp_path):
    job, _ = trial(tmp_path)
    with pytest.raises(jobs.JobError, match="exists"):
        jobs.run_job(["harbor"], job, env={}, log_path=tmp_path / "l.log",
                     run=lambda *a, **k: pytest.fail("ran"), fresh=True)


def fake_harbor(tmp_path, exceptions):
    """A run() that leaves one trial per call, raising the next exception type in `exceptions`."""
    seq = list(exceptions)

    def run(cmd, **kw):
        name = cmd[cmd.index("--job-name") + 1]
        t = tmp_path / "jobs" / name / "trial__x"
        (t / "agent").mkdir(parents=True)
        exc = seq.pop(0)
        (t / "result.json").write_text(json.dumps({
            "task_name": TASK, "exception_info": {"exception_type": exc} if exc else None,
            "verifier_result": {"rewards": {"reward": 1.0}}}))
        return subprocess.CompletedProcess(cmd, 0)
    return run


def make_cmd(name):
    return ["harbor", "run", "--job-name", name]


def test_a_valid_first_try_is_not_rerun(tmp_path):
    read, tries = jobs.run_with_reruns("validate__t__oracle__a1", make_cmd, jobs_dir=tmp_path / "jobs",
                                       logs_dir=tmp_path / "logs", env={}, run=fake_harbor(tmp_path, [None]))
    assert tries == [{"job": "validate__t__oracle__a1", "reason": None}] and read["reward"] == 1.0


def test_infrastructure_errors_are_rerun_under_new_names(tmp_path):
    waits = []
    read, tries = jobs.run_with_reruns("j", make_cmd, jobs_dir=tmp_path / "jobs", logs_dir=tmp_path / "logs",
                                       env={}, run=fake_harbor(tmp_path, ["RuntimeError", "ApiUsageLimitError", None]),
                                       before_rerun=waits.append)
    assert [t["job"] for t in tries] == ["j", "j-rerun1", "j-rerun2"]
    assert [t["reason"] for t in tries] == ["infrastructure", "usage_limit", None]
    assert waits == ["infrastructure", "usage_limit"]


def test_reruns_stop_after_the_limit(tmp_path):
    read, tries = jobs.run_with_reruns("j", make_cmd, jobs_dir=tmp_path / "jobs", logs_dir=tmp_path / "logs",
                                       env={}, run=fake_harbor(tmp_path, ["RuntimeError"] * 3))
    assert len(tries) == 3 and tries[-1]["reason"] == "infrastructure"


def test_a_model_outcome_is_never_rerun(tmp_path):
    read, tries = jobs.run_with_reruns("j", make_cmd, jobs_dir=tmp_path / "jobs", logs_dir=tmp_path / "logs",
                                       env={}, run=fake_harbor(tmp_path, ["AgentTimeoutError"]))
    assert tries == [{"job": "j", "reason": None}]


def test_a_probe_opens_the_model_endpoint_without_claude(tmp_path):
    cmd = jobs.harbor_command(tmp_path / "t", "probe__t__probe__a1", tmp_path / "jobs", "oracle", {},
                              claude=False, allow_host=True)
    assert "--allow-agent-host" in cmd and "-m" not in cmd


def test_an_existing_job_directory_is_read_not_run(tmp_path):
    fake = fake_harbor(tmp_path, [None])
    fake(make_cmd("j"))
    read, tries = jobs.run_with_reruns("j", make_cmd, jobs_dir=tmp_path / "jobs", logs_dir=tmp_path / "logs",
                                       env={}, run=lambda *a, **k: pytest.fail("ran again"))
    assert tries == [{"job": "j", "reason": None}] and read["reward"] == 1.0
