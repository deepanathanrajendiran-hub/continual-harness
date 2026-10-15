"""Re-grade a run's captured model.patch on a pristine image with Scale's PatchReplayAgent.

The re-graded reward is the run's score. Records live at RUNS/regrade/<job>.json.
"""
import argparse
import json
import subprocess
from pathlib import Path

from bench.swepro import config, dataset, feedback, jobs


def regrade(source_job: str, task: str, arm: str, attempt: int, *, runs: Path, run=subprocess.run) -> dict:
    name = config.job_name("regrade", task, arm, attempt)
    path = runs / "regrade" / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    task_dir = runs / "scale" / "v2" / "tasks" / task

    def make_cmd(n):
        return jobs.harbor_command(task_dir, n, runs / "jobs", jobs.REPLAY_AGENT,
                                   {"source_job": runs / "jobs" / source_job}, claude=False, model="replay")

    read, tries = jobs.run_with_reruns(name, make_cmd, jobs_dir=runs / "jobs", logs_dir=runs / "logs",
                                       env=jobs.job_env(None, extra_path=[runs / "tools"]), run=run, grading=True)
    valid = tries[-1]["reason"] is None
    graded = feedback.counts(Path(read["trial_dir"]), task_dir) if valid else None
    record = {"job": name, "source_job": source_job, "task": task, "arm": arm, "attempt": attempt,
              "tries": tries, "valid": valid, "reward": read["reward"] if valid else None,
              "graded_failed": graded[0] if graded else None, "graded_total": graded[1] if graded else None}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def regrade_practice(runs: Path, *, run=subprocess.run) -> list:
    """Re-grade every practice run (its image was removed after the task, so pull it again)."""
    out = []
    for path in sorted((runs / "practice" / "records").glob("*.json")):
        record = json.loads(path.read_text())
        image = dataset.docker_image(runs / "scale" / "v2" / "tasks" / record["task"])
        jobs.pull_image(image, run=run)
        try:
            out.append(regrade(record["job"], record["task"], "refined", 1, runs=runs, run=run))
        finally:
            jobs.remove_image(image, run=run)
    return out


def main(argv=None) -> int:
    jobs.install_stop_handlers()
    parser = argparse.ArgumentParser(description="Re-grade the practice runs on pristine images.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    args = parser.parse_args(argv)
    jobs.require_no_harbor(args.runs / "jobs")  # other studies' runs may go on beside it
    records = regrade_practice(args.runs)
    print(f"{sum(1 for r in records if r['reward'] == 1.0)} of {len(records)} practice runs pass on re-grade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
