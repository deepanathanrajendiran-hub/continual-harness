import json
import subprocess
import tomllib
from pathlib import Path

import pytest

from bench.swepro import config, refine

TASK = "instance_ansible__ansible-1111111111111111111111111111111111111111-vaaaa"


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_refine_task_is_offline_with_a_dummy_verifier(tmp_path):
    d = refine.build_task(tmp_path / "task")
    toml = tomllib.loads((d / "task.toml").read_text())
    assert toml["agent"]["network_mode"] == "no-network"
    assert (d / "environment" / "Dockerfile").read_text().startswith(f"FROM {config.REFINE_BASE_IMAGE}\n")
    assert "reward.txt" in (d / "tests" / "test.sh").read_text()
    assert (d / "instruction.md").read_text() == refine.PROMPT


def test_the_prompt_authorises_one_approved_apply_and_forbids_outcomes_and_copying():
    p = refine.PROMPT
    for needle in ("/refine", "--approved", "--override-cap", "at most one", "refine-outcome",
                   "/inputs/result.txt", "/inputs/transcript.jsonl", "/inputs/task.md", "PROJECT=/app"):
        assert needle in p, needle


def test_inputs_hold_statement_transcript_and_result_only(tmp_path):
    task = write(tmp_path / "task" / "instruction.md", "Fix the vars merge.").parent
    write(tmp_path / "task" / "tests" / "config.json", "{}")
    trial = tmp_path / "trial"
    write(trial / "agent" / "sessions" / "projects" / "-app" / "s1.jsonl", '{"a": 1}\n')
    write(trial / "agent" / "sessions" / "projects" / "-app" / "s2.jsonl", '{"b": 2}\n')
    d = refine.make_inputs(task, trial, "failed: 2 of 16 graded tests failed", tmp_path / "inputs")
    assert sorted(p.name for p in d.iterdir()) == ["result.txt", "task.md", "transcript.jsonl"]
    assert (d / "transcript.jsonl").read_text() == '{"a": 1}\n{"b": 2}\n'
    assert (d / "result.txt").read_text() == "failed: 2 of 16 graded tests failed\n"


def out_dir(out, *, claude_md="rule", memory=None, skill=True):
    write(out / "app" / "CLAUDE.md", claude_md)
    write(out / "app" / ".claude" / "harness" / "refine-log.jsonl", "{}")
    if skill:
        write(out / "app" / ".claude" / "skills" / "refine" / "SKILL.md", "snapshot")
    for rel, text in (memory or {}).items():
        write(out / "memory" / rel, text)
    return out


def test_absorb_replaces_the_state_without_the_snapshot_and_archives_the_old_one(tmp_path):
    state = tmp_path / "state"
    write(state / "app" / "CLAUDE.md", "old rule")
    out = out_dir(tmp_path / "out", memory={"MEMORY.md": "- [u](u.md)", "u.md": "units"})
    changed = refine.absorb(out, state, tmp_path / "history" / "001")
    assert (state / "app" / "CLAUDE.md").read_text() == "rule"
    assert not (state / "app" / ".claude" / "skills" / "refine").exists()
    assert (state / "memory" / "u.md").read_text() == "units"
    assert (tmp_path / "history" / "001" / "app" / "CLAUDE.md").read_text() == "old rule"
    assert changed == [".claude/CLAUDE.md", "memory/MEMORY.md", "memory/u.md"]


def test_absorb_with_no_change_reports_none(tmp_path):
    state = tmp_path / "state"
    write(state / "app" / "CLAUDE.md", "rule")
    write(state / "app" / ".claude" / "harness" / "refine-log.jsonl", "{}")
    assert refine.absorb(out_dir(tmp_path / "out"), state, tmp_path / "h" / "001") == []


def test_history_entries_and_skill_use_are_read_from_disk(tmp_path):
    agent = tmp_path / "trial" / "agent"
    write(agent / "refine-history.json", json.dumps({"entries": [{"id": "e1"}, {"id": "e2"}]}))
    write(agent / "claude-code.txt", json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": "refine"}}]}}) + "\n")
    assert refine.history_ids(tmp_path / "trial") == ["e1", "e2"]
    assert refine.skill_used(tmp_path / "trial") is True
    write(agent / "claude-code.txt", "")
    assert refine.skill_used(tmp_path / "trial") is False
    assert refine.history_ids(tmp_path / "missing") is None


def fake_session(tmp_path, *, exception=None, entries=("e1",), memory=None):
    def run(cmd, **kw):
        name = cmd[cmd.index("--job-name") + 1]
        args = dict(a.split("=", 1) for a in cmd[1:] if "=" in a and not a.startswith("CLAUDE_"))
        t = tmp_path / "runs" / "jobs" / name / "trial__x"
        write(t / "result.json", json.dumps({"task_name": "refine", "exception_info":
                                             {"exception_type": exception} if exception else None,
                                             "verifier_result": {"rewards": {"reward": 1.0}}}))
        write(t / "agent" / "refine-history.json", json.dumps({"entries": [{"id": e} for e in entries]}))
        write(t / "agent" / "claude-code.txt", json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "refine"}}]}}) + "\n")
        out_dir(Path(args["out_dir"]), memory=memory or {"MEMORY.md": "m"})
        return subprocess.CompletedProcess(cmd, 0)
    return run


@pytest.fixture
def practice(tmp_path):
    task = write(tmp_path / "tasks" / TASK / "instruction.md", "do it").parent
    trial = tmp_path / "trial"
    write(trial / "agent" / "sessions" / "projects" / "-app" / "s.jsonl", "{}\n")
    (tmp_path / "skill").mkdir()
    write(tmp_path / "skill" / "SKILL.md")
    return task, trial


def test_a_session_absorbs_its_state_and_records_what_changed(tmp_path, practice):
    task, trial = practice
    rec = refine.run_session(1, TASK, task, trial, "passed", runs=tmp_path / "runs", skill=tmp_path / "skill",
                             token="tok", run=fake_session(tmp_path))
    assert rec["valid"] and rec["entries_added"] == ["e1"] and rec["skill_used"]
    assert ".claude/CLAUDE.md" in rec["changed"]
    state = tmp_path / "runs" / "refine" / "state"
    assert (state / "memory" / "MEMORY.md").read_text() == "m"
    saved = json.loads((tmp_path / "runs" / "refine" / "records" / "001.json").read_text())
    assert saved == rec


def test_an_invalid_session_leaves_the_state_alone(tmp_path, practice):
    task, trial = practice
    rec = refine.run_session(1, TASK, task, trial, "passed", runs=tmp_path / "runs", skill=tmp_path / "skill",
                             token="tok", run=fake_session(tmp_path, exception="RuntimeError"))
    assert rec["valid"] is False and rec["changed"] == []
    assert not (tmp_path / "runs" / "refine" / "state" / "app").exists()


def test_more_than_one_new_entry_is_flagged(tmp_path, practice):
    task, trial = practice
    rec = refine.run_session(1, TASK, task, trial, "passed", runs=tmp_path / "runs", skill=tmp_path / "skill",
                             token="tok", run=fake_session(tmp_path, entries=("e1", "e2")))
    assert rec["entries_added"] == ["e1", "e2"] and rec["over_one_edit"] is True


def test_running_the_snapshot_cli_counts_as_using_the_skill(tmp_path):
    """`/refine` at the top of the prompt expands the skill without a Skill tool call."""
    write(tmp_path / "trial" / "agent" / "claude-code.txt", json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command":
            "python3 /app/.claude/skills/refine/scripts/harness.py --runtime claude --project /app doctor"}}]}}) + "\n")
    assert refine.skill_used(tmp_path / "trial") is True
