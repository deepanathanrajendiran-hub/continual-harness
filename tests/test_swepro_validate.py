import json
import subprocess

import pytest

from bench.swepro import config, split, validate

A = [f"instance_ansible__ansible-{i:040d}-v0" for i in range(80)]


def harbor(tmp_path, rewards, layout_rc=0):
    """Fake harbor: reward by (task, agent) from `rewards`, default oracle 1 and nop 0."""
    calls = []

    def run(cmd, **kw):
        if cmd[0] == "docker":
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, layout_rc if cmd[1] == "run" else 0, "", "")
        name = cmd[cmd.index("--job-name") + 1]
        agent = cmd[cmd.index("-a") + 1]
        task = cmd[cmd.index("-p") + 1].rsplit("/", 1)[-1]
        calls.append((task, agent))
        value = rewards.get((task, agent), 1.0 if agent == "oracle" else 0.0)
        t = tmp_path / "runs" / "jobs" / name / "trial__x"
        (t / "agent").mkdir(parents=True)
        exc = value if isinstance(value, str) else None
        (t / "result.json").write_text(json.dumps({
            "task_name": task, "exception_info": {"exception_type": exc} if exc else None,
            "verifier_result": None if exc else {"rewards": {"reward": value}}}))
        return subprocess.CompletedProcess(cmd, 0)
    return run, calls


@pytest.fixture
def tasks(tmp_path):
    d = tmp_path / "tasks"
    for name in A[:3]:
        (d / name).mkdir(parents=True)
        (d / name / "task.toml").write_text(f'[environment]\ndocker_image = "img:{name}"\n')
    return d


def test_a_task_is_valid_when_oracle_passes_and_nop_fails(tmp_path, tasks):
    run, calls = harbor(tmp_path, {})
    rec = validate.validate_task(A[0], tasks, tmp_path / "runs", run=run)
    assert rec["valid"] is True and (rec["oracle"], rec["nop"]) == (1.0, 0.0)
    assert json.loads((tmp_path / "runs" / "validation" / f"{A[0]}.json").read_text()) == rec
    assert ["docker", "pull", "-q", "--platform", "linux/amd64", f"img:{A[0]}"] in calls


@pytest.mark.parametrize("rewards,reason", [
    ({(A[0], "oracle"): 0.0}, "oracle scored 0.0"),
    ({(A[0], "nop"): 1.0}, "nop scored 1.0"),
    ({(A[0], "oracle"): "RuntimeError"}, "oracle: infrastructure after 3 tries"),
])
def test_a_task_is_invalid_with_a_reason(tmp_path, tasks, rewards, reason):
    run, _ = harbor(tmp_path, rewards)
    rec = validate.validate_task(A[0], tasks, tmp_path / "runs", run=run)
    assert rec["valid"] is False and rec["reason"] == reason


def test_a_saved_record_is_not_run_again(tmp_path, tasks):
    run, calls = harbor(tmp_path, {})
    validate.validate_task(A[0], tasks, tmp_path / "runs", run=run)
    n = len(calls)
    validate.validate_task(A[0], tasks, tmp_path / "runs", run=run)
    assert len(calls) == n


def test_summary_lists_valid_and_invalid(tmp_path, tasks):
    run, _ = harbor(tmp_path, {(A[1], "nop"): 1.0})
    for name in A[:3]:
        validate.validate_task(name, tasks, tmp_path / "runs", run=run)
    s = validate.summarize(tmp_path / "runs", A[:3])
    assert s["valid"] == [A[0], A[2]] and s["invalid"] == {A[1]: "nop scored 1.0"}


def test_summary_refuses_unvalidated_tasks(tmp_path):
    with pytest.raises(validate.ValidationIncomplete):
        validate.summarize(tmp_path / "runs", A[:1])


def test_split_is_seeded_and_keeps_thirty_for_practice():
    s = split.split(A)
    assert len(s["practice"]) == 30 and len(s["test"]) == 50
    assert sorted(s["practice"] + s["test"]) == sorted(A)
    assert s == split.split(list(reversed(A)))
    assert s["seed"] == config.SPLIT_SEED


def test_split_refuses_fewer_than_forty_test_tasks():
    with pytest.raises(split.SplitTooSmall):
        split.split(A[:69])
    assert len(split.split(A[:70])["test"]) == 40


def test_test_order_is_seeded_and_covers_every_test_task():
    s = split.split(A)
    order = split.test_order(s["test"])
    assert sorted(order) == sorted(s["test"]) and order == split.test_order(list(reversed(s["test"])))
    assert order != sorted(s["test"])


def test_a_task_whose_image_has_its_own_claude_dir_or_no_app_repo_is_invalid(tmp_path, tasks):
    """The refined arm's install refuses such a repo, which would score only that arm 0."""
    run, calls = harbor(tmp_path, {}, layout_rc=1)
    rec = validate.validate_task(A[0], tasks, tmp_path / "runs", run=run)
    assert rec["valid"] is False and rec["reason"] == "repo layout: /app/.git missing or /app/.claude present"
    layout = [c for c in calls if isinstance(c, list) and c[1] == "run"]
    assert layout and "--platform" in layout[0] and f"img:{A[0]}" in layout[0]

def test_a_crashed_oracle_verifier_is_rerun_not_a_drop(tmp_path, tasks):
    seen = []
    run, _ = harbor(tmp_path, {})

    def flaky(cmd, **kw):
        if cmd[0] == "harbor" and "oracle" in cmd and not seen:
            seen.append(1)
            return harbor(tmp_path, {(A[0], "oracle"): "VerifierTimeoutError"})[0](cmd, **kw)
        return run(cmd, **kw)

    rec = validate.validate_task(A[0], tasks, tmp_path / "runs", run=flaky)
    assert rec["valid"] is True and [t["reason"] for t in rec["tries"]["oracle"]] == ["infrastructure", None]
