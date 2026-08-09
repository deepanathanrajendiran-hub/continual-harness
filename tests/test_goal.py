import sys
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[1] / ".claude" / "harness" / "bin"
sys.path.insert(0, str(BIN))

import goal  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_goals(tmp_path, monkeypatch):
    d = tmp_path / "goals"
    d.mkdir()
    monkeypatch.setattr(goal.paths, "goals_dir", lambda: d)
    return d


def _make(**kw):
    args = dict(
        goal="Refactor the auth module",
        cwd="/tmp/proj",
        gate_kind="command",
        gate_value="pytest -q",
        max_turns=3,
    )
    args.update(kw)
    return goal.create(**args)


def test_slugify_is_filesystem_safe():
    assert goal.slugify("Refactor the AUTH module!") == "refactor-the-auth-module"
    assert goal.slugify("a" * 100) == "a" * 60


def test_create_writes_state(isolated_goals):
    state = _make()
    assert (isolated_goals / f"{state['slug']}.json").exists()
    assert state["status"] == "active"
    assert state["used"]["turns"] == 0
    assert state["subagents"] == []


def test_create_refuses_without_gate():
    """Spec 6: a long-horizon loop with no termination criterion is an
    infinite loop."""
    with pytest.raises(goal.GateRequired):
        _make(gate_value="")


def test_checkpoint_increments_turns():
    state = _make()
    goal.checkpoint(state["slug"], "did a thing", "do next thing", "hash1", "fail", "boom")
    reloaded = goal.load(state["slug"])
    assert reloaded["used"]["turns"] == 1
    assert reloaded["checkpoints"][0]["gate"] == "fail"
    assert reloaded["checkpoints"][0]["tree_hash"] == "hash1"


def test_budget_exhausted_at_max_turns():
    state = _make(max_turns=2)
    assert goal.budget_exhausted(state) is False
    for i in range(2):
        goal.checkpoint(state["slug"], f"turn {i}", "next", f"h{i}", "fail")
    assert goal.budget_exhausted(goal.load(state["slug"])) is True


def test_complete_requires_passing_gate():
    """Spec 5.5: budget exhaustion is never reported as success."""
    state = _make()
    goal.checkpoint(state["slug"], "tried", "retry", "h1", "fail", "2 failed")
    with pytest.raises(goal.GateNotPassed):
        goal.complete(state["slug"], "2 failed")


def test_complete_succeeds_after_passing_gate():
    state = _make()
    goal.checkpoint(state["slug"], "fixed it", "none", "h1", "pass", "ok")
    done = goal.complete(state["slug"], "ok")
    assert done["status"] == "complete"
    assert done["gate_evidence"] == "ok"


def test_load_missing_raises():
    with pytest.raises(goal.GoalStateError):
        goal.load("no-such-goal")


def test_load_malformed_raises(isolated_goals):
    """Spec 6: never silently continue under a guessed goal."""
    (isolated_goals / "broken.json").write_text("{not json")
    with pytest.raises(goal.GoalStateError):
        goal.load("broken")


def test_gate_output_is_bounded():
    state = _make()
    goal.checkpoint(state["slug"], "x", "y", "h", "fail", "E" * 10000)
    stored = goal.load(state["slug"])["checkpoints"][0]["gate_output"]
    assert len(stored) <= goal.MAX_GATE_OUTPUT + 32
    assert "truncated" in stored
