"""Pilot: pick the next study after ansible stopped at the gate's ceiling.

Plain Claude Code runs once on each candidate study's 8 pinned pilot tasks (config.STUDIES[...]["pilot"]),
and each task is validated (oracle 1, nop 0). Only rewards are read. The study whose pass rate is closest
to half, inside the gate's bounds, is chosen. The model is config.MODEL, so the candidates are the
repository studies by default, or with --this-study just SWEPRO_STUDY's own pilot.
"""
import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bench.swepro import config, dataset, jobs, probe, validate
from bench.tb4 import run as tb4run

RUNS = Path.home() / "swepro-runs-pilot"
CANDIDATES = ("openlibrary", "flipt")
MIN_COUNTED = 4
READ_FIELDS = ("reward", "exception", "cost_usd", "tokens_in", "tokens_out", "agent_sec", "model")


def _repo(task: str, candidates) -> str:
    return next(c for c in candidates if task in config.STUDIES[c]["pilot"])


def pilot_task(task: str, *, runs: Path, token: str, run=subprocess.run, pace, candidates=CANDIDATES) -> dict:
    path = runs / "pilot" / f"{task}.json"
    if path.exists():
        return json.loads(path.read_text())
    tasks_dir = runs / "scale" / "v2" / "tasks"
    jobs.pull_image(dataset.docker_image(tasks_dir / task), run=run)
    name = config.job_name("pilot", task, "plain", 1)
    read, tries = jobs.run_with_reruns(
        name, lambda n: jobs.harbor_command(tasks_dir / task, n, runs / "jobs", jobs.ARM_AGENT,
                                            {"tools_dir": runs / "tools"}, claude=True),
        jobs_dir=runs / "jobs", logs_dir=runs / "logs", env=jobs.job_env(token), run=run,
        before_rerun=lambda reason: pace())
    check = validate.validate_task(task, tasks_dir, runs, run=run)  # also removes the image
    record = {"task": task, "repo": _repo(task, candidates), "tries": tries, "agent_reason": tries[-1]["reason"],
              "valid": check["valid"], "validation_reason": check["reason"],
              **{k: (read or {}).get(k) for k in READ_FIELDS}}
    record["counted"] = record["valid"] and record["agent_reason"] is None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def summarize(records) -> dict:
    out = {}
    for r in records:
        s = out.setdefault(r["repo"], {"tasks": 0, "counted": 0, "passes": 0})
        s["tasks"] += 1
        if r["counted"]:
            s["counted"] += 1
            s["passes"] += r["reward"] == 1.0
    for s in out.values():
        s["rate"] = s["passes"] / s["counted"] if s["counted"] else None
    return out


def choose(summary: dict, candidates=CANDIDATES):
    """The candidate closest to a 50% pass rate, strictly inside the gate's bounds; None if none is."""
    high, low = config.GATE_HIGH / config.N_PRACTICE, config.GATE_LOW / config.N_PRACTICE
    fit = [c for c in candidates if c in summary and summary[c]["counted"] >= MIN_COUNTED
           and low < summary[c]["rate"] < high]
    return min(fit, key=lambda c: abs(summary[c]["rate"] - 0.5), default=None)


def main(argv=None) -> int:
    jobs.install_stop_handlers()
    parser = argparse.ArgumentParser(description="Pilot plain Claude Code on each candidate repository.")
    parser.add_argument("--runs", type=Path, default=RUNS)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--this-study", action="store_true", help="pilot only SWEPRO_STUDY's own tasks")
    args = parser.parse_args(argv)
    jobs.require_no_harbor(args.runs / "jobs")  # pilots in other run directories may go on beside it
    token = tb4run.read_token()

    def pace():
        return tb4run.wait_for_headroom(lambda: tb4run.probe_usage(token), config.FIVE_HOUR_CEILING,
                                        config.WEEKLY_CEILING)

    candidates = (config.STUDY,) if args.this_study else CANDIDATES
    tasks = [t for group in zip(*(config.STUDIES[c]["pilot"] for c in candidates)) for t in group]

    def one(task):
        pace()
        r = pilot_task(task, runs=args.runs, token=token, pace=pace, candidates=candidates)
        print(f"{r['repo']} {task}: {'counted' if r['counted'] else 'not counted'}", flush=True)
        return r

    with tb4run.hold_lock(args.runs / "runner.lock"):
        probe.run_probe(args.runs, args.runs / "scale" / "v2" / "tasks", "pilot start")
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            records = list(pool.map(one, tasks))
    summary = summarize(records)
    result = {"model": config.MODEL, "summary": summary, "choice": choose(summary, candidates)}
    (args.runs / "pilot.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
