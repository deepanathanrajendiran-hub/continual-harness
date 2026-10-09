import json
from pathlib import Path

import pytest

from bench.evo import steps

# The CASE_SUMMARY line exactly as EvoCode's README (f8fcfaa, "Metrics") documents it:
#   CASE_SUMMARY total_cases=… success_count=…
README_LINE = "CASE_SUMMARY total_cases=45 success_count=44"


def timing(start, end):
    return {"started_at": start, "finished_at": end}


def step_result(name, reward=None, exception=None, agent=None):
    """One StepResult as Harbor 0.24.0 dumps it (harbor/models/trial/result.py)."""
    return {
        "step_name": name,
        "agent_result": {"n_input_tokens": 1000, "n_cache_tokens": 800, "n_output_tokens": 50, "cost_usd": 0.01,
                         "model_usage": None, "rollout_details": None, "metadata": None},
        "verifier_result": None if reward is None else {"rewards": {"reward": reward}},
        "exception_info": None if exception is None else {
            "exception_type": exception, "exception_message": "synthetic", "exception_traceback": "synthetic",
            "occurred_at": "2026-10-09T10:30:00Z"},
        "agent_execution": agent,
        "verifier": timing("2026-10-09T10:30:01Z", "2026-10-09T10:31:00Z"),
    }


def make_trial(root: Path, results, trial_exception=None, files=None) -> Path:
    """A multi-step trial dir: result.json plus steps/<name>/{agent,verifier,artifacts} (harbor/trial/multi_step.py)."""
    trial = root / "demo__AbCdEfG"
    trial.mkdir(parents=True)
    for result in results or []:
        for sub in ("agent", "verifier", "artifacts"):
            (trial / "steps" / result["step_name"] / sub).mkdir(parents=True, exist_ok=True)
    for rel, text in (files or {}).items():
        path = trial / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (trial / "result.json").write_text(json.dumps({
        "id": "00000000-0000-0000-0000-000000000000", "task_name": "demo", "trial_name": trial.name,
        "trial_uri": trial.as_uri(), "task_id": {"path": "/copies/agent/demo"}, "source": None,
        "task_checksum": "x", "config": {}, "agent_info": {"name": "claude-code", "version": "2.1.293"},
        "agent_result": None, "verifier_result": {"rewards": {"reward": 0.5}}, "verifier_environment_mode": None,
        "exception_info": None if trial_exception is None else {
            "exception_type": trial_exception, "exception_message": "synthetic", "exception_traceback": "synthetic",
            "occurred_at": "2026-10-09T11:00:00Z"},
        "started_at": "2026-10-09T09:59:00Z", "finished_at": "2026-10-09T11:00:00Z",
        "environment_setup": None, "agent_setup": None, "agent_execution": None, "verifier": None,
        "step_results": results,
    }, indent=4))
    return trial


def write(step_dir: Path, name: str, text: str) -> None:
    (step_dir / "verifier").mkdir(parents=True, exist_ok=True)
    (step_dir / "verifier" / name).write_text(text)


def test_read_trial_returns_each_step_in_order(tmp_path):
    trial = make_trial(tmp_path, [
        step_result("round-1", 1.0, agent=timing("2026-10-09T10:00:00.250000Z", "2026-10-09T10:20:00.250000Z")),
        step_result("round-2", 0.0, "AgentTimeoutError", agent=timing("2026-10-09T10:21:00Z", "2026-10-09T10:51:00Z")),
    ])
    out = steps.read_trial(trial)
    assert out["trial_exception"] is None
    first, second = out["steps"]
    assert first == {
        "name": "round-1", "index": 1, "reward": 1.0, "exception": None,
        "agent_started": "2026-10-09T10:00:00.250000Z", "agent_finished": "2026-10-09T10:20:00.250000Z",
        "agent_sec": 1200.0,
        "agent_dir": trial / "steps" / "round-1" / "agent",
        "verifier_dir": trial / "steps" / "round-1" / "verifier",
        "artifacts_dir": trial / "steps" / "round-1" / "artifacts",
    }
    assert (second["name"], second["index"], second["reward"], second["exception"], second["agent_sec"]) == (
        "round-2", 2, 0.0, "AgentTimeoutError", 1800.0)


def test_a_step_without_a_verifier_result_falls_back_to_its_reward_file(tmp_path):
    trial = make_trial(tmp_path, [step_result("round-1", None, agent=timing("2026-10-09T10:00:00Z", None))],
                       files={"steps/round-1/verifier/reward.txt": "1\n"})
    (only,) = steps.read_trial(trial)["steps"]
    assert only["reward"] == 1.0 and only["agent_finished"] is None and only["agent_sec"] is None


def test_an_ungraded_step_has_no_reward(tmp_path):
    trial = make_trial(tmp_path, [step_result("round-1", None, "RuntimeError", agent=None)])
    (only,) = steps.read_trial(trial)["steps"]
    assert (only["reward"], only["exception"], only["agent_started"], only["agent_sec"]) == (
        None, "RuntimeError", None, None)


def test_a_chain_that_stopped_early_lists_only_the_steps_harbor_ran(tmp_path):
    trial = make_trial(tmp_path, [step_result("round-1", 0.0, "NonZeroAgentExitCodeError")],
                       trial_exception="CancelledError")
    out = steps.read_trial(trial)
    assert [s["name"] for s in out["steps"]] == ["round-1"]
    assert out["trial_exception"] == "CancelledError"


def test_a_trial_without_step_results_has_no_steps(tmp_path):
    out = steps.read_trial(make_trial(tmp_path, None))
    assert out == {"steps": [], "trial_exception": None}


def test_a_step_name_that_leaves_the_trial_dir_is_refused(tmp_path):
    trial = make_trial(tmp_path, [])
    data = json.loads((trial / "result.json").read_text())
    data["step_results"] = [step_result("../escape", 1.0)]
    (trial / "result.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        steps.read_trial(trial)


def test_read_trial_reward_matches_the_reward_files(tmp_path):
    trial = make_trial(tmp_path, [step_result("round-1", 1.0), step_result("round-2", 0.0)],
                       files={"steps/round-1/verifier/reward.txt": "1\n",
                              "steps/round-2/verifier/reward.txt": "0\n"})
    for step in steps.read_trial(trial)["steps"]:
        assert step["reward"] == steps.step_reward(trial / "steps" / step["name"])


def test_step_reward_reads_reward_txt(tmp_path):
    write(tmp_path, "reward.txt", "1\n")
    assert steps.step_reward(tmp_path) == 1.0


def test_step_reward_prefers_reward_json_like_harbor(tmp_path):
    write(tmp_path, "reward.txt", "1\n")
    write(tmp_path, "reward.json", json.dumps({"reward": 0}))
    assert steps.step_reward(tmp_path) == 0.0


@pytest.mark.parametrize("name,text", [("reward.txt", ""), ("reward.txt", "pass\n"), ("reward.txt", "nan\n"),
                                       ("reward.json", "{"), ("reward.json", json.dumps({"score": 1})),
                                       ("reward.json", json.dumps([1]))])
def test_step_reward_is_none_for_an_unusable_file(tmp_path, name, text):
    write(tmp_path, name, text)
    assert steps.step_reward(tmp_path) is None


def test_step_reward_is_none_without_files(tmp_path):
    assert steps.step_reward(tmp_path) is None


def test_case_counts_reads_the_readme_line(tmp_path):
    write(tmp_path, "test-stdout.txt", f"collected 45 items\n{README_LINE}\n")
    assert steps.case_counts(tmp_path) == (44, 45)


def test_case_counts_takes_the_last_summary_line(tmp_path):
    write(tmp_path, "test-stdout.txt",
          "CASE_SUMMARY total_cases=10 success_count=3\nrerun\nCASE_SUMMARY total_cases=12 success_count=12\n")
    assert steps.case_counts(tmp_path) == (12, 12)


def test_case_counts_tolerates_prefixes_colour_and_key_order(tmp_path):
    write(tmp_path, "test-stdout.txt", "[verifier] \x1b[32mCASE_SUMMARY success_count=7, total_cases=9\x1b[0m\n")
    assert steps.case_counts(tmp_path) == (7, 9)


@pytest.mark.parametrize("text", ["no summary here\n", "NO_CASE_SUMMARY total_cases=4 success_count=4\n",
                                  "CASE_SUMMARY total_cases=4\n", "CASE_SUMMARY total_cases=4 success_count=5\n",
                                  "CASE_SUMMARY total_cases=4 success_count=4\nCASE_SUMMARY broken\n"])
def test_case_counts_is_none_without_a_well_formed_last_line(tmp_path, text):
    write(tmp_path, "test-stdout.txt", text)
    assert steps.case_counts(tmp_path) is None


def test_case_counts_is_none_without_test_stdout(tmp_path):
    assert steps.case_counts(tmp_path) is None
