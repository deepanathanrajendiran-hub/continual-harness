import json

import pytest

from bench.swepro import feedback


def task_dir(tmp_path, f2p, p2p, *, literal=False):
    d = tmp_path / "task"
    (d / "tests").mkdir(parents=True)
    enc = repr if literal else json.dumps
    (d / "tests" / "config.json").write_text(json.dumps(
        {"fail_to_pass": enc(f2p), "pass_to_pass": enc(p2p), "selected_test_files_to_run": "[]"}))
    return d


def trial_dir(tmp_path, statuses, reward):
    t = tmp_path / "trial"
    (t / "verifier").mkdir(parents=True)
    (t / "verifier" / "output.json").write_text(json.dumps(
        {"tests": [{"name": n, "status": s} for n, s in statuses.items()]}))
    if reward is not None:
        (t / "verifier" / "reward.txt").write_text(f"{reward}\n")
    return t


def test_a_pass_is_just_passed(tmp_path):
    t = trial_dir(tmp_path, {"a": "PASSED", "b": "PASSED"}, 1)
    assert feedback.line(t, task_dir(tmp_path, ["a"], ["b"]), None) == "passed"


def test_a_fail_counts_graded_tests_that_did_not_pass_including_missing_ones(tmp_path):
    t = trial_dir(tmp_path, {"a": "FAILED", "b": "PASSED", "extra": "FAILED"}, 0)
    d = task_dir(tmp_path, ["a", "c"], ["b", "d"])
    assert feedback.line(t, d, None) == "failed: 3 of 4 graded tests failed"


def test_python_literal_lists_are_read_too(tmp_path):
    t = trial_dir(tmp_path, {"a": "PASSED", "b": "ERROR"}, 0)
    assert feedback.line(t, task_dir(tmp_path, ["a"], ["b"], literal=True), None) == \
        "failed: 1 of 2 graded tests failed"


def test_duplicates_across_lists_count_once(tmp_path):
    t = trial_dir(tmp_path, {"a": "FAILED"}, 0)
    assert feedback.line(t, task_dir(tmp_path, ["a"], ["a"]), None) == "failed: 1 of 1 graded tests failed"


def test_a_failed_reward_with_no_failing_graded_test_says_the_count_is_unavailable(tmp_path):
    t = trial_dir(tmp_path, {"a": "PASSED"}, 0)
    assert feedback.line(t, task_dir(tmp_path, ["a"], []), None) == "failed: graded test count unavailable"


def test_missing_output_json_says_the_count_is_unavailable(tmp_path):
    t = trial_dir(tmp_path, {}, 0)
    (t / "verifier" / "output.json").unlink()
    assert feedback.line(t, task_dir(tmp_path, ["a"], []), None) == "failed: graded test count unavailable"


@pytest.mark.parametrize("exception,text", [("AgentTimeoutError", "timeout"), ("RuntimeError", "error")])
def test_no_reward_names_the_reason(tmp_path, exception, text):
    t = trial_dir(tmp_path, {}, None)
    assert feedback.line(t, task_dir(tmp_path, ["a"], []), exception) == f"failed: no result ({text})"


def test_counts_never_include_a_test_name(tmp_path):
    t = trial_dir(tmp_path, {"test_secret_name": "FAILED"}, 0)
    out = feedback.line(t, task_dir(tmp_path, ["test_secret_name"], []), None)
    assert "secret" not in out


def test_counts_are_failed_and_graded(tmp_path):
    t = trial_dir(tmp_path, {"a": "FAILED", "b": "PASSED"}, 0)
    assert feedback.counts(t, task_dir(tmp_path, ["a"], ["b"])) == (1, 2)


def test_counts_without_output_are_none(tmp_path):
    assert feedback.counts(tmp_path / "nothing", tmp_path / "nothing") is None
