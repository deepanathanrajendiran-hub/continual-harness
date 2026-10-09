"""Read a finished Harbor 0.24.0 multi-step trial: per-step reward, exception, timing and output directories.

Harbor writes result.json (TrialResult) with step_results[], one StepResult per step it ran:
step_name, agent_result, verifier_result.rewards, exception_info.exception_type,
agent_execution.{started_at,finished_at} and verifier.{started_at,finished_at}. After each step it moves
the step's outputs to steps/<step_name>/{agent,verifier,artifacts}. A chain that stops early has fewer entries.
Contamination rule: nothing here reads verifier output beyond the reward files and the CASE_SUMMARY counts.
"""
import json
import math
import re
from datetime import datetime
from pathlib import Path

CASE_SUMMARY = re.compile(r"\bCASE_SUMMARY\b")
_CASE_FIELD = re.compile(r"\b(total_cases|success_count)=(\d+)\b")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def step_reward(step_dir):
    """The step's reward from steps/<name>/verifier, with Harbor's precedence: reward.json "reward", else reward.txt."""
    verifier = Path(step_dir) / "verifier"
    try:
        if (verifier / "reward.json").is_file():
            data = json.loads((verifier / "reward.json").read_text())
            return _finite(data.get("reward")) if isinstance(data, dict) else None
        if (verifier / "reward.txt").is_file():
            return _finite(float((verifier / "reward.txt").read_text().strip()))
    except (ValueError, OSError):
        return None
    return None


def case_counts(step_dir):
    """(passed, total) from the last CASE_SUMMARY line of verifier/test-stdout.txt, else None.

    EvoCode's README documents the line as `CASE_SUMMARY total_cases=… success_count=…`. Only lines that carry
    the marker are kept; every other line is skipped unread past the marker test.
    """
    path = Path(step_dir) / "verifier" / "test-stdout.txt"
    if not path.is_file():
        return None
    last = None
    with open(path, errors="replace") as handle:
        for line in handle:
            line = _ANSI.sub("", line)
            if CASE_SUMMARY.search(line):
                last = line
    if last is None:
        return None
    fields = dict(_CASE_FIELD.findall(last))
    if set(fields) != {"total_cases", "success_count"}:
        return None
    passed, total = int(fields["success_count"]), int(fields["total_cases"])
    return (passed, total) if passed <= total else None


def _stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _seconds(started, finished):
    if not started or not finished:
        return None
    try:
        return (_stamp(finished) - _stamp(started)).total_seconds()
    except ValueError:
        return None


def _exception_type(record):
    return (record.get("exception_info") or {}).get("exception_type")


def read_trial(trial_dir) -> dict:
    """Every step Harbor ran, in order, from <trial_dir>/result.json and <trial_dir>/steps/<name>/."""
    trial_dir = Path(trial_dir)
    result = json.loads((trial_dir / "result.json").read_text())
    out = []
    for index, step in enumerate(result.get("step_results") or [], start=1):
        name = step["step_name"]
        if not name or "/" in name or "\\" in name or name in (".", ".."):
            raise ValueError(f"unsafe step name in result.json: {name!r}")
        step_dir = trial_dir / "steps" / name
        reward = _finite(((step.get("verifier_result") or {}).get("rewards") or {}).get("reward"))
        if reward is None:
            reward = step_reward(step_dir)
        execution = step.get("agent_execution") or {}
        started, finished = execution.get("started_at"), execution.get("finished_at")
        out.append({"name": name, "index": index, "reward": reward, "exception": _exception_type(step),
                    "agent_started": started, "agent_finished": finished, "agent_sec": _seconds(started, finished),
                    "agent_dir": step_dir / "agent", "verifier_dir": step_dir / "verifier",
                    "artifacts_dir": step_dir / "artifacts"})
    return {"steps": out, "trial_exception": _exception_type(result)}
