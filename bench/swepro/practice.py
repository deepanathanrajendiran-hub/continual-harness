"""The practice phase: each practice task runs with the notes so far, then refine learns from it.

Resumable: a task whose record exists is done. Records live at RUNS/practice/records/<index>.json.
"""
import argparse
import json
import subprocess
from pathlib import Path

from bench.swepro import bundle, config, dataset, feedback, jobs, probe, refine
from bench.tb4 import run as tb4run


class PracticeError(RuntimeError):
    pass


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def _load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def practice_task(index: int, task: str, *, runs: Path, skill: Path, token: str, run, pace) -> dict:
    tasks_dir = runs / "scale" / "v2" / "tasks"
    task_dir = tasks_dir / task
    notes = runs / "practice" / "bundles" / f"{index:03d}"
    # exported once: after a crash the state may already hold this task's lesson, which the run never saw
    digest = bundle.verify(notes) if notes.exists() else bundle.export(runs / "refine" / "state", notes)["hash"]
    image = dataset.docker_image(task_dir)
    jobs.pull_image(image, run=run)
    try:
        pace()

        def make_cmd(name):
            return jobs.harbor_command(task_dir, name, runs / "jobs", jobs.ARM_AGENT,
                                       {"tools_dir": runs / "tools", "bundle_dir": notes}, claude=True)

        read, tries = jobs.run_with_reruns(config.job_name("practice", task, "refined", 1), make_cmd,
                                           jobs_dir=runs / "jobs", logs_dir=runs / "logs", env=jobs.job_env(token),
                                           run=run, before_rerun=lambda reason: pace())
    finally:
        jobs.remove_image(image, run=run)
    valid = tries[-1]["reason"] is None
    trial = Path(read["trial_dir"]) if read else None
    line = feedback.line(trial, task_dir, read["exception"]) if valid else "failed: no result (error)"
    record = {"index": index, "task": task, "job": tries[-1]["job"], "tries": tries, "valid": valid,
              "bundle_hash": digest, "feedback": line,
              **{k: (read or {}).get(k) for k in ("reward", "exception", "cost_usd", "tokens_in", "tokens_out",
                                                  "agent_sec", "notes", "claude_version", "model")}}
    if valid:
        record["refine"] = refine.run_session(index, task, task_dir, trial, line, runs=runs, skill=skill,
                                              token=token, run=run, before_rerun=lambda reason: pace())
    else:
        record["refine"] = None
    _write(runs / "practice" / "records" / f"{index:03d}.json", record)
    return record


def run_practice(order, *, runs: Path, skill: Path, token: str, run=subprocess.run, pace) -> list:
    records, ran = [], 0
    tasks_dir = runs / "scale" / "v2" / "tasks"
    start = runs / "practice" / "usage_start.json"
    for index, task in enumerate(order, 1):
        saved = _load(runs / "practice" / "records" / f"{index:03d}.json")
        if saved is not None:
            if saved["task"] != task:
                raise PracticeError(f"record {index} is {saved['task']}, but the practice order has {task}")
            records.append(saved)
            continue
        if not start.exists():
            _write(start, pace())
        done = index - 1
        if ran == 0 or done % config.PROBE_EVERY == 0:  # every process start, then every PROBE_EVERY tasks
            probe.run_probe(runs, tasks_dir, "practice start" if done == 0 else f"practice after {done} tasks",
                            run=run)
        records.append(practice_task(index, task, runs=runs, skill=skill, token=token, run=run, pace=pace))
        ran += 1
    return records


def layer(rel: str) -> str:
    """Which refine layer a bundle path belongs to: M memory, G skill, K subagent, rho CLAUDE.md."""
    if rel.startswith("memory/"):
        return "M"
    if rel.startswith(".claude/skills/"):
        return "G"
    if rel.startswith(".claude/agents/"):
        return "K"
    return "rho"


def gate(records, *, usage_start: dict, usage_end: dict) -> dict:
    if len(records) != config.N_PRACTICE:
        raise PracticeError(f"{len(records)} practice records; the gate needs {config.N_PRACTICE}")
    passes = sum(1 for r in records if r.get("valid") and (r.get("reward") or 0) >= 1.0)
    if passes >= config.GATE_HIGH:
        decision = "stop_high"
    elif passes <= config.GATE_LOW:
        decision = "stop_low"
    else:
        decision = "ask_user"
    agent_cost = [r["cost_usd"] for r in records if r.get("cost_usd") is not None]
    refine_cost = [r["refine"]["cost_usd"] for r in records if (r.get("refine") or {}).get("cost_usd") is not None]
    mean = lambda xs: sum(xs) / len(xs) if xs else None  # noqa: E731
    used = None
    if usage_start.get("seven_day") is not None and usage_end.get("seven_day") is not None:
        used = usage_end["seven_day"] - usage_start["seven_day"]
    share = sum(agent_cost) / (sum(agent_cost) + sum(refine_cost)) if agent_cost and refine_cost else 1.0
    test_runs = 2 * config.ATTEMPTS * 50
    by_layer = {}
    for r in records:  # a session that changed several files of one layer is one edit of that layer
        for name in sorted({layer(rel) for rel in (r.get("refine") or {}).get("changed", [])}):
            by_layer[name] = by_layer.get(name, 0) + 1
    return {"runs": len(records), "passes": passes, "decision": decision,
            "mean_agent_cost_usd": mean(agent_cost), "mean_refine_cost_usd": mean(refine_cost),
            "mean_tokens": mean([(r.get("tokens_in") or 0) + (r.get("tokens_out") or 0) for r in records]),
            "seven_day_used": used,
            "projected_test_seven_day": None if used is None else used / len(records) * share * test_runs,
            "edits": sum(len((r.get("refine") or {}).get("entries_added", [])) for r in records),
            "edits_by_layer": by_layer,
            "sessions_without_change": sum(1 for r in records if not (r.get("refine") or {}).get("changed"))}


def main(argv=None) -> int:
    jobs.require_no_harbor()
    jobs.install_stop_handlers()
    parser = argparse.ArgumentParser(description="Run the practice phase, then print the go/no-go numbers.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--docs", type=Path, default=config.DOCS)
    args = parser.parse_args(argv)
    order = json.loads((args.docs / "split.json").read_text())["practice"]
    token = tb4run.read_token()

    def pace():
        return tb4run.wait_for_headroom(lambda: tb4run.probe_usage(token), config.FIVE_HOUR_CEILING,
                                        config.WEEKLY_CEILING)

    with tb4run.hold_lock(args.runs / "runner.lock"):
        records = run_practice(order, runs=args.runs, skill=args.runs / "refine" / "skill", token=token, pace=pace)
    _write(args.runs / "practice" / "usage_end.json", pace())
    result = gate(records, usage_start=_load(args.runs / "practice" / "usage_start.json") or {},
                  usage_end=_load(args.runs / "practice" / "usage_end.json") or {})
    _write(args.runs / "practice" / "gate.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
