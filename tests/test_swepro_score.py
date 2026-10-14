import json

from bench.swepro import config, score

TASK = "instance_ansible__ansible-0000000000000000000000000000000000000001-v"


def record(arm="refined", attempt=1, **extra):
    base = {"job": config.job_name("test", TASK, arm, attempt), "final_job": config.job_name("test", TASK, arm, attempt),
            "task": TASK, "arm": arm, "attempt": attempt, "tries": [{"job": "x", "reason": None}], "valid": True,
            "reward": 1.0, "exception": None, "cost_usd": 0.5, "tokens_in": 100, "tokens_out": 10, "agent_sec": 60.0,
            "claude_version": "2.1.293", "model": "claude-sonnet-5-5", "notes": {"hash": "h", "claude_dir": True},
            "patch_bytes": 10, "audit_tests": False, "freeze": "abc"}
    base.update(extra)
    return base


def test_the_score_is_the_regrade_not_the_sandbox_reward():
    r = score.row(record(reward=1.0), {"valid": True, "reward": 0.0, "graded_failed": 2, "graded_total": 9})
    assert (r["reward_sandbox"], r["reward_regrade"], r["score"]) == (1.0, 0.0, 0)
    assert (r["graded_failed"], r["graded_total"]) == (2, 9)


def test_a_missing_or_invalid_regrade_scores_zero():
    assert score.row(record(), None)["score"] == 0
    assert score.row(record(), {"valid": False, "reward": None})["score"] == 0


def test_plain_notes_are_read_as_no_hash():
    r = score.row(record(arm="plain", notes={"hash": "", "claude_dir": False}), {"valid": True, "reward": 1.0})
    assert r["notes_hash"] is None and r["claude_dir"] is False and r["score"] == 1


def test_reruns_count_the_extra_tries():
    r = score.row(record(tries=[{"reason": "infrastructure"}, {"reason": None}]), None)
    assert r["reruns"] == 1


def test_build_rows_joins_records_to_regrades(tmp_path):
    (tmp_path / "records").mkdir()
    (tmp_path / "regrade").mkdir()
    rec = record()
    (tmp_path / "records" / f"{rec['job']}.json").write_text(json.dumps(rec))
    name = config.job_name("regrade", TASK, "refined", 1)
    (tmp_path / "regrade" / f"{name}.json").write_text(json.dumps({"valid": True, "reward": 1.0}))
    rows = score.build_rows(tmp_path)
    assert len(rows) == 1 and rows[0]["score"] == 1 and set(rows[0]) == set(score.ROW_FIELDS)
    score.write_rows(rows, tmp_path / "rows.jsonl")
    assert score.read_rows(tmp_path / "rows.jsonl") == rows
