"""The one line refine is told about a practice run: `passed` or `failed: K of N graded tests failed`.

Reads the verifier's reward and per-test statuses and the task's graded lists, and returns only counts.
No test name ever leaves this module.
"""
import ast
import json
from pathlib import Path

PASSED = "PASSED"
UNAVAILABLE = "failed: graded test count unavailable"


def _names(value) -> list:
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except ValueError:
        return ast.literal_eval(value)  # Scale stores some lists as Python literals


def _reward(trial: Path):
    try:
        return float((trial / "verifier" / "reward.txt").read_text().strip())
    except (OSError, ValueError):
        return None


def counts(trial: Path, task: Path):
    """(failed, graded) for a run whose verifier wrote per-test statuses, else None."""
    try:
        config = json.loads((task / "tests" / "config.json").read_text())
        graded = set(_names(config.get("fail_to_pass", "[]"))) | set(_names(config.get("pass_to_pass", "[]")))
        statuses = {t["name"]: t["status"]
                    for t in json.loads((trial / "verifier" / "output.json").read_text())["tests"]}
    except (OSError, ValueError, KeyError, TypeError, SyntaxError):
        return None
    if not graded:
        return None
    return sum(1 for name in graded if statuses.get(name) != PASSED), len(graded)


def line(trial: Path, task: Path, exception) -> str:
    reward = _reward(trial)
    if reward is None:
        return f"failed: no result ({'timeout' if exception == 'AgentTimeoutError' else 'error'})"
    if reward >= 1.0:
        return "passed"
    found = counts(trial, task)
    if found is None or found[0] == 0:
        return UNAVAILABLE
    return f"failed: {found[0]} of {found[1]} graded tests failed"
