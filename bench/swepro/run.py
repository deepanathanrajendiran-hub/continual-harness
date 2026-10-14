"""The test phase: for each test task in the frozen order, 3 attempts, each a concurrent plain/refined pair,
then a pristine re-grade of all 6 runs. Resumable: a task with all its records and re-grades is done.
"""
import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bench.swepro import config, dataset, jobs, prereg, probe, regrade
from bench.tb4 import run as tb4run

READ_FIELDS = ("reward", "exception", "cost_usd", "tokens_in", "tokens_out", "agent_sec", "verifier_sec",
               "claude_version", "model", "notes", "patch_bytes", "audit_tests")


def _record_path(runs: Path, job: str) -> Path:
    return runs / "records" / f"{job}.json"


def run_one(task: str, arm: str, attempt: int, *, runs: Path, token: str, freeze: str, run, pace) -> dict:
    name = config.job_name("test", task, arm, attempt)
    path = _record_path(runs, name)
    if path.exists():
        return json.loads(path.read_text())
    kwargs = {"tools_dir": runs / "tools"}
    if arm == "refined":
        kwargs["bundle_dir"] = runs / "bundle"
    task_dir = runs / "scale" / "v2" / "tasks" / task

    def make_cmd(n):
        return jobs.harbor_command(task_dir, n, runs / "jobs", jobs.ARM_AGENT, kwargs, claude=True)

    read, tries = jobs.run_with_reruns(name, make_cmd, jobs_dir=runs / "jobs", logs_dir=runs / "logs",
                                       env=jobs.job_env(token), run=run, before_rerun=lambda reason: pace())
    record = {"job": name, "final_job": tries[-1]["job"], "task": task, "arm": arm, "attempt": attempt,
              "tries": tries, "valid": tries[-1]["reason"] is None, "freeze": freeze,
              **{k: (read or {}).get(k) for k in READ_FIELDS}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def task_done(runs: Path, task: str) -> bool:
    names = [config.job_name(p, task, arm, a) for a in range(1, config.ATTEMPTS + 1) for arm in config.ARMS
             for p in ("test", "regrade")]
    return all((runs / ("records" if n.startswith("test") else "regrade") / f"{n}.json").exists() for n in names)


def run_task(task: str, *, runs: Path, token: str, freeze: str, run=subprocess.run, pace) -> list:
    image = dataset.docker_image(runs / "scale" / "v2" / "tasks" / task)
    jobs.pull_image(image, run=run)
    records = []
    try:
        for attempt in range(1, config.ATTEMPTS + 1):
            pace()
            with ThreadPoolExecutor(max_workers=len(config.ARMS)) as pool:
                records += list(pool.map(lambda arm: run_one(task, arm, attempt, runs=runs, token=token,
                                                             freeze=freeze, run=run, pace=pace), config.ARMS))
        for r in records:
            regrade.regrade(r["final_job"], task, r["arm"], r["attempt"], runs=runs, run=run)
    finally:
        jobs.remove_image(image, run=run)
    return records


def run_test(order, *, runs: Path, token: str, freeze: str, run=subprocess.run, pace) -> None:
    tasks_dir = runs / "scale" / "v2" / "tasks"
    ran = 0
    for index, task in enumerate(order):
        if task_done(runs, task):
            continue
        if ran == 0 or index % config.PROBE_EVERY == 0:  # every process start, then every PROBE_EVERY tasks
            probe.run_probe(runs, tasks_dir, "test start" if index == 0 else f"test after {index} tasks", run=run)
        run_task(task, runs=runs, token=token, freeze=freeze, run=run, pace=pace)
        ran += 1
        print(f"[{index + 1}/{len(order)}] {task} done", flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the frozen test phase.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--docs", type=Path, default=config.DOCS)
    args = parser.parse_args(argv)
    freeze = prereg.require_freeze()
    p = json.loads((args.docs / "prereg.json").read_text())
    prereg.check_runtime(p, args.runs)
    token = tb4run.read_token()

    def pace():
        return tb4run.wait_for_headroom(lambda: tb4run.probe_usage(token), config.FIVE_HOUR_CEILING,
                                        config.WEEKLY_CEILING)

    with tb4run.hold_lock(args.runs / "runner.lock"):
        run_test(p["split"]["test_order"], runs=args.runs, token=token, freeze=freeze, pace=pace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
