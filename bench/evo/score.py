"""Score finished EvoCode multi-step jobs into one row per (job, round), read from disk.

Contamination rule: per round this reads only the reward (steps.read_trial / steps.case_counts: reward
files and the CASE_SUMMARY counts), the agent's own stream and session files, and the Horizon ledger copy
the collect hook saved. It never opens tests/, solution/ or instructions, and it prints only counts.
"""
import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from bench.evo import config, steps
from bench.tb4 import stream
from bench.tb4.score import parse_time

ROW_FIELDS = ("job_name", "phase", "task", "arm", "attempt", "round", "round_index", "reward", "passed",
              "cases_passed", "cases_total", "agent_sec", "tokens_in", "tokens_out", "cost_usd",
              "result_records", "horizon_calls", "horizon_started", "goal_slugs", "goal_status", "end_reason",
              "final_message", "label", "audit_flags", "leftovers")
INPUT_FIELDS = ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")
TIMEOUT = "AgentTimeoutError"
NOT_REACHED = "not reached"
END_STATUSES = ("complete", "abandoned", "active")
MUTATING = ("start", "check", "review", "complete", "abandon", "reopen")
AUDIT = {
    "verifier-files": re.compile(r"(?<![\w.-])/(?:tests|solution|logs/verifier)(?![\w.-])"),
    "benchmark-source": re.compile(r"EvoCodeBench|UniPat-?AI", re.I),
}


def round_names(task_dir: Path) -> list:
    """The task's step names in order, from its task.toml only."""
    data = tomllib.loads((Path(task_dir) / "task.toml").read_text())
    return [step["name"] for step in data.get("steps") or []]


def ledger_goals(artifacts_dir: Path, round_name: str):
    """slug -> goal from the ledger copy the collect hook saved for this round; None when no copy was collected.

    A copy counts as collected when the round's audit folder holds killed.txt (the hook always writes it) or a
    harness/ folder; a collected copy with no goals is {}.
    Docker bind-mounts /logs/artifacts at <step>/artifacts/logs/artifacts; the second layout also
    accepts an artifacts_dir that already points at the convention dir."""
    base = Path(artifacts_dir)
    for out in (base / "logs" / "artifacts" / round_name, base / round_name):
        if (out / "killed.txt").is_file() or (out / "harness").is_dir():
            goals = {}
            for path in sorted((out / "harness" / "goals").glob("*.json")):
                try:
                    item = json.loads(path.read_text(errors="replace"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(item, dict) and isinstance(item.get("slug"), str) and "status" in item:
                    goals[item["slug"]] = item
            return goals
    return None


def _reported(calls) -> tuple:
    """(slug -> status, last slug) from this round's ledger-changing Horizon calls, in call order."""
    status, last = {}, None
    for call in calls:
        if any(sub in MUTATING for sub in call["subcommands"]):
            for summary in call["summaries"]:
                status[summary["slug"]] = summary["status"]
                last = summary["slug"]
    return status, last


def goal_fields(previous: dict, current, calls) -> dict:
    """Goals this round created or changed, their status at the end of the round, and the end reason.

    A goal belongs to a round when its ledger file is new or different from the previous collected copy.
    The ledger copy is authoritative; the round's own start/check/... output fills in only slugs the
    copy lacks. `current` is None when no copy was collected for the round: then the calls are the only
    evidence. The goal started last decides the end reason."""
    current = current or {}
    touched = {slug: item for slug, item in current.items() if previous.get(slug) != item}
    reported, last = _reported(calls)
    status = {slug: current[slug]["status"] if slug in current else value for slug, value in reported.items()}
    status.update({slug: item["status"] for slug, item in touched.items()})
    if touched:
        latest = max(touched.values(), key=lambda g: ((g.get("used") or {}).get("started") or "", g["slug"]))
        final = latest["status"]
    else:
        final = status.get(last)
    created = any(slug not in previous for slug in touched)
    started = created or any("start" in c["subcommands"] and c["summaries"] for c in calls)
    end = "no goal" if not status else final if final in END_STATUSES else "unknown"
    return {"horizon_started": bool(started), "goal_slugs": sorted(status),
            "goal_status": dict(sorted(status.items())), "end_reason": end}


def leftovers(artifacts_dir: Path, round_name: str):
    """Counts from the collect hook's audit files for this round: processes it killed, other processes still
    running, and /tmp entries left; None when no audit was collected. Counts only, never names."""
    base = Path(artifacts_dir)
    for out in (base / "logs" / "artifacts" / round_name, base / round_name):
        if (out / "killed.txt").is_file():
            def lines(name):
                path = out / name
                return [x for x in path.read_text(errors="replace").splitlines() if x.strip()] if path.is_file() else None

            tmp = lines("tmp-ls.txt")
            return {"killed": len(lines("killed.txt")),
                    "survivors": None if lines("survivors.txt") is None else len(lines("survivors.txt")),
                    "tmp_entries": None if tmp is None else sum(
                        1 for x in tmp if not x.startswith("total ") and x.split()[-1] not in (".", ".."))}
    return None


def audit_flags(events) -> list:
    """Which audit patterns any tool input matched: verifier files or the benchmark's own source."""
    flags = set()
    for _, block in stream.tool_uses(events):
        text = " ".join(str(v) for v in (block.get("input") or {}).values())
        flags.update(name for name, pattern in AUDIT.items() if pattern.search(text))
    return sorted(flags)


def session_events(agent_dir: Path) -> list:
    events = []
    for path in sorted((Path(agent_dir) / "sessions" / "projects").rglob("*.jsonl")):
        events.extend(stream.read_events(path))
    return events


def _exception_type(value):
    return value.get("exception_type") if isinstance(value, dict) else value


def _base(record, name, index) -> dict:
    row = dict.fromkeys(ROW_FIELDS)
    row.update(job_name=record["job_name"], phase=record["phase"], task=record["task"], arm=record["arm"],
               attempt=record["attempt"], round=name, round_index=index, reward=0.0, passed=False,
               result_records=0, horizon_calls=0, horizon_started=False, goal_slugs=[], goal_status={},
               end_reason=NOT_REACHED, audit_flags=[])
    return row


def step_values(step: dict, step_dir: Path, previous: dict) -> tuple:
    """(row values, this round's ledger goals or None when no copy was collected) for one step that ran."""
    events = stream.read_events(Path(step["agent_dir"]) / "claude-code.txt")
    excepted = _exception_type(step.get("exception"))
    # TB4 rule: after a timeout, a result line written before the collect hook killed claude is not an answer
    final = None if excepted == TIMEOUT else stream.final_result(events)
    usage = (final or {}).get("modelUsage") or {}
    calls = stream.horizon_calls(events)
    current = ledger_goals(step["artifacts_dir"], step["name"])
    counts = steps.case_counts(step_dir)
    started, finished = parse_time(step.get("agent_started")), parse_time(step.get("agent_finished"))
    # a round with any Harbor exception is failed, whatever reward the verifier still recorded for it
    reward = float(step["reward"]) if step.get("reward") is not None and excepted is None else 0.0
    values = {
        "reward": reward, "passed": reward >= 1.0,
        "cases_passed": counts[0] if counts else None, "cases_total": counts[1] if counts else None,
        "agent_sec": (finished - started).total_seconds() if started and finished else None,
        "tokens_in": sum(int(m.get(k) or 0) for m in usage.values() for k in INPUT_FIELDS) if final else None,
        "tokens_out": sum(int(m.get("outputTokens") or 0) for m in usage.values()) if final else None,
        "cost_usd": (final or {}).get("total_cost_usd"),
        "result_records": sum(1 for e in events if e.get("type") == "result"),
        "horizon_calls": len(calls),
        **goal_fields(previous, current, calls),
        "final_message": (final or {}).get("result") or None,
        "audit_flags": audit_flags(events + session_events(step["agent_dir"])),
        "leftovers": leftovers(step["artifacts_dir"], step["name"]),
    }
    return values, current


def round_rows(record: dict, *, runs: Path = config.RUNS) -> list:
    """One row per round of the task, in task order; rounds the trial never reached fail as 'not reached'."""
    names = round_names(Path(runs) / "copies" / "agent" / record["task"])
    trial_dir = Path(record["trial_dir"]) if record.get("trial_dir") else None
    ran = steps.read_trial(trial_dir)["steps"] if trial_dir and (trial_dir / "result.json").is_file() else []
    by_name = {step["name"]: step for step in ran}
    unknown = sorted(set(by_name) - set(names))
    if unknown:
        raise ValueError(f"{record['job_name']}: trial steps {unknown} are not in the task's task.toml")
    rows, previous = [], {}
    for index, name in enumerate(names, start=1):
        row = _base(record, name, index)
        if name in by_name:
            values, current = step_values(by_name[name], trial_dir / "steps" / name, previous)
            row.update(values)
            if current is not None:
                previous = current
        rows.append(row)
    return rows


def load_records(runs: Path, phase: str) -> list:
    records = [json.loads(p.read_text()) for p in sorted((Path(runs) / "records").glob("*.json"))]
    return [r for r in records if r.get("phase") == phase and r.get("valid") is True]


def _key(row) -> tuple:
    return row["phase"], row["task"], row["arm"], row["attempt"], row["round_index"]


def score_phase(phase: str, *, runs: Path = config.RUNS) -> int:
    """Write or refresh rows.jsonl for the valid records of one phase; other phases' rows are kept.

    A judge label is kept while the final message it judged is unchanged. Returns the phase's row count."""
    runs = Path(runs)
    rows = [row for record in load_records(runs, phase) for row in round_rows(record, runs=runs)]
    path = runs / "rows.jsonl"
    kept, old = [], {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                item = json.loads(line)
                if item.get("phase") == phase:
                    old[(item.get("job_name"), item.get("round"))] = item
                else:
                    kept.append(item)
    for row in rows:
        previous = old.get((row["job_name"], row["round"]))
        if previous and previous.get("label") is not None and previous.get("final_message") == row["final_message"]:
            row["label"] = previous["label"]
    out = sorted(kept + rows, key=_key)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in out))
    tmp.replace(path)
    return len(rows)


def main(argv=None, *, require_freeze=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--phase", choices=("dry", "main"), required=True)
    args = parser.parse_args(argv)
    if args.phase == "main":  # the dry run happens before the freeze; scoring the main run needs it intact
        if require_freeze is None:
            from bench.evo.prereg import require_freeze  # imported late so this module stands alone
        require_freeze(subprocess.run)
    count = score_phase(args.phase, runs=args.runs)
    print(json.dumps({"phase": args.phase, "rows": count, "out": str(args.runs / "rows.jsonl")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
