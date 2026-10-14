"""One row per test run in RUNS/rows.jsonl: the run record joined to its re-grade."""
import argparse
import json
from pathlib import Path

from bench.swepro import config

ROW_FIELDS = ("task", "arm", "attempt", "job", "final_job", "reruns", "valid", "reward_sandbox", "regrade_valid",
              "reward_regrade", "score", "exception", "cost_usd", "tokens_in", "tokens_out", "agent_sec",
              "claude_version", "model", "notes_hash", "claude_dir", "audit_tests", "patch_bytes",
              "graded_failed", "graded_total", "freeze")


def row(record: dict, regrade) -> dict:
    notes = record.get("notes") or {}
    regrade = regrade or {}
    reward_regrade = regrade.get("reward") if regrade.get("valid") else None
    return {
        "task": record["task"], "arm": record["arm"], "attempt": record["attempt"], "job": record["job"],
        "final_job": record["final_job"], "reruns": len(record["tries"]) - 1, "valid": record["valid"],
        "reward_sandbox": record.get("reward"), "regrade_valid": bool(regrade.get("valid")),
        "reward_regrade": reward_regrade, "score": 1 if reward_regrade == 1.0 else 0,
        "exception": record.get("exception"), "cost_usd": record.get("cost_usd"),
        "tokens_in": record.get("tokens_in"), "tokens_out": record.get("tokens_out"),
        "agent_sec": record.get("agent_sec"), "claude_version": record.get("claude_version"),
        "model": record.get("model"), "notes_hash": notes.get("hash") or None,
        "claude_dir": notes.get("claude_dir"), "audit_tests": record.get("audit_tests"),
        "patch_bytes": record.get("patch_bytes"), "graded_failed": regrade.get("graded_failed"),
        "graded_total": regrade.get("graded_total"), "freeze": record.get("freeze"),
    }


def build_rows(runs: Path = config.RUNS) -> list:
    rows = []
    for path in sorted((runs / "records").glob("test__*.json")):
        record = json.loads(path.read_text())
        name = config.job_name("regrade", record["task"], record["arm"], record["attempt"])
        regrade_path = runs / "regrade" / f"{name}.json"
        rows.append(row(record, json.loads(regrade_path.read_text()) if regrade_path.exists() else None))
    return rows


def write_rows(rows, path: Path) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def read_rows(path: Path) -> list:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write RUNS/rows.jsonl from the test records and re-grades.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    args = parser.parse_args(argv)
    rows = build_rows(args.runs)
    write_rows(rows, args.runs / "rows.jsonl")
    print(f"{len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
