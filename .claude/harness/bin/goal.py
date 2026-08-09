"""Goal state for horizon (spec §5.1, §5.5).

Checkpointing after every increment is the mechanism behind "long
horizon" — it is what lets work survive context loss, session restart, or
a /loop firing. Nothing here trusts in-memory state.
"""

import json
import re
from datetime import datetime, timezone

import paths

MAX_GATE_OUTPUT = 4000
SLUG_MAX = 60


class GateRequired(Exception):
    """Raised when a goal is created without a termination criterion."""


class GoalStateError(Exception):
    """Raised when goal state is missing or unreadable. Never guess."""


class GateNotPassed(Exception):
    """Raised when completion is attempted without a passing gate."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:SLUG_MAX].strip("-")


def _path(slug: str):
    return paths.goals_dir() / f"{slug}.json"


def _save(state: dict) -> dict:
    _path(state["slug"]).write_text(json.dumps(state, indent=2) + "\n")
    return state


def create(goal, cwd, gate_kind, gate_value,
           max_turns=20, max_minutes=None, watch_paths=None) -> dict:
    if not gate_value or not str(gate_value).strip():
        raise GateRequired(
            "horizon requires a gate. A loop with no termination criterion "
            "is an infinite loop. Pass --gate '<command>' or a coverage criterion."
        )
    if gate_kind not in ("command", "coverage"):
        raise GateRequired(f"gate_kind must be 'command' or 'coverage', got {gate_kind!r}")

    state = {
        "slug": slugify(goal),
        "goal": goal,
        "cwd": str(cwd),
        "gate": {"kind": gate_kind, "value": gate_value},
        "watch_paths": [str(p) for p in (watch_paths or [cwd])],
        "budget": {"max_turns": max_turns, "max_minutes": max_minutes},
        "used": {"turns": 0, "started": _now()},
        "status": "active",
        "subagents": [],
        "checkpoints": [],
    }
    return _save(state)


def load(slug: str) -> dict:
    p = _path(slug)
    if not p.exists():
        raise GoalStateError(f"no goal state at {p}")
    try:
        state = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise GoalStateError(f"goal state at {p} is unreadable: {e}") from e
    if "slug" not in state or "gate" not in state:
        raise GoalStateError(f"goal state at {p} is missing required fields")
    return state


def checkpoint(slug, did, next_action, tree_hash_value,
               gate_result, gate_output="") -> dict:
    if gate_result not in ("pass", "fail", "skipped"):
        raise ValueError(f"gate_result must be pass|fail|skipped, got {gate_result!r}")
    state = load(slug)
    if len(gate_output) > MAX_GATE_OUTPUT:
        gate_output = gate_output[:MAX_GATE_OUTPUT] + "\n...[truncated]"
    state["checkpoints"].append({
        "turn": state["used"]["turns"] + 1,
        "at": _now(),
        "did": did,
        "next": next_action,
        "tree_hash": tree_hash_value,
        "gate": gate_result,
        "gate_output": gate_output,
    })
    state["used"]["turns"] += 1
    return _save(state)


def budget_exhausted(state: dict) -> bool:
    max_turns = state["budget"].get("max_turns")
    if max_turns is not None and state["used"]["turns"] >= max_turns:
        return True
    max_minutes = state["budget"].get("max_minutes")
    if max_minutes is not None:
        started = datetime.fromisoformat(state["used"]["started"])
        elapsed = (datetime.now(timezone.utc) - started).total_seconds() / 60
        if elapsed >= max_minutes:
            return True
    return False


def complete(slug: str, gate_output: str) -> dict:
    state = load(slug)
    last = state["checkpoints"][-1] if state["checkpoints"] else None
    if last is None or last["gate"] != "pass":
        raise GateNotPassed(
            "cannot complete: the last gate did not pass. Budget exhaustion "
            "is reported as a partial result, never as success."
        )
    state["status"] = "complete"
    state["gate_evidence"] = gate_output
    state["completed_at"] = _now()
    return _save(state)


def abandon(slug: str, reason: str) -> dict:
    state = load(slug)
    state["status"] = "abandoned"
    state["abandoned_reason"] = reason
    state["abandoned_at"] = _now()
    return _save(state)
