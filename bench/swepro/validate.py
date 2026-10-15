"""Local validation: on Colima, the oracle must score 1 and the empty patch (nop) must score 0."""
import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bench.swepro import config, dataset, jobs
from bench.tb4.run import hold_lock


class ValidationIncomplete(RuntimeError):
    pass


def _record_path(runs: Path, task: str) -> Path:
    return runs / "validation" / f"{task}.json"


LAYOUT = "test -d /app/.git && test ! -e /app/.claude"
LAYOUT_REASON = "repo layout: /app/.git missing or /app/.claude present"


def layout_ok(image: str, run=subprocess.run) -> bool:
    """The refined arm installs notes at /app/.claude and Harbor seeds memory for /app; both need this."""
    proc = run(["docker", "run", "--rm", "--platform", "linux/amd64", "--entrypoint", "sh", image, "-c", LAYOUT],
               capture_output=True, text=True)
    return proc.returncode == 0


def validate_task(task: str, tasks_dir: Path, runs: Path = config.RUNS, *, run=subprocess.run) -> dict:
    path = _record_path(runs, task)
    if path.exists():
        return json.loads(path.read_text())
    image = dataset.docker_image(tasks_dir / task)
    jobs.pull_image(image, run=run)
    record = {"task": task, "image": image, "tries": {}}
    try:
        if not layout_ok(image, run=run):
            record["reason"] = LAYOUT_REASON
        for agent in () if "reason" in record else ("oracle", "nop"):
            name = config.job_name("validate", task, agent, 1)
            read, tries = jobs.run_with_reruns(
                name, lambda n, a=agent: jobs.harbor_command(tasks_dir / task, n, runs / "jobs", a, {}, claude=False),
                jobs_dir=runs / "jobs", logs_dir=runs / "logs", env=jobs.job_env(None), run=run, grading=True)
            record["tries"][agent] = tries
            reason = tries[-1]["reason"]
            record[agent] = None if reason else read["reward"]
            if reason:
                record["reason"] = f"{agent}: {reason} after {len(tries)} tries"
                break
    finally:
        jobs.remove_image(image, run=run)
    if "reason" not in record:
        if record["oracle"] != 1.0:
            record["reason"] = f"oracle scored {record['oracle']}"
        elif record["nop"] != 0.0:
            record["reason"] = f"nop scored {record['nop']}"
    record["valid"] = "reason" not in record
    record.setdefault("reason", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def summarize(runs: Path, pool) -> dict:
    missing = [t for t in pool if not _record_path(runs, t).exists()]
    if missing:
        raise ValidationIncomplete(f"{len(missing)} tasks not validated yet, e.g. {missing[0]}")
    records = [json.loads(_record_path(runs, t).read_text()) for t in pool]
    return {"valid": sorted(r["task"] for r in records if r["valid"]),
            "invalid": {r["task"]: r["reason"] for r in records if not r["valid"]}}


def main(argv=None) -> int:
    jobs.install_stop_handlers()
    parser = argparse.ArgumentParser(description="Validate the study pool with oracle and nop on Colima.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--only", nargs="*", help="validate just these tasks")
    parser.add_argument("--parallel", type=int, default=2, help="tasks validated at once (Colima has 10 GB)")
    args = parser.parse_args(argv)
    jobs.require_no_harbor(args.runs / "jobs")  # other studies' runs may go on beside it
    tasks_dir = args.runs / "scale" / "v2" / "tasks"
    pool = dataset.study_pool(tasks_dir)
    todo = args.only or pool

    def one(task):
        record = validate_task(task, tasks_dir, args.runs)
        print(f"{task}: {'valid' if record['valid'] else record['reason']}", flush=True)

    with hold_lock(args.runs / "runner.lock"), ThreadPoolExecutor(max_workers=args.parallel) as pool_exec:
        list(pool_exec.map(one, todo))
    if not args.only:
        summary = summarize(args.runs, pool)
        (args.runs / "valid.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        print(f"{len(summary['valid'])} valid, {len(summary['invalid'])} invalid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
