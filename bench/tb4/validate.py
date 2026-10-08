"""Build, check, and pin every candidate task; write validation.json (spec: Task selection, steps 2-3)."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from bench.tb4 import config, copies, images, run

EXPECTED = {"oracle": 1.0, "nop": 0.0, "ledger": 1.0}


def harbor_reward(job_dir: Path):
    _, result = run.job_result(job_dir)
    if result is None:
        return None
    reward = ((result.get("verifier_result") or {}).get("rewards") or {}).get("reward")
    return float(reward) if reward is not None else None


def _reset(task: str, paths: run.Paths) -> None:
    for path in (paths.copies / task, paths.check_copies / task,
                 *(paths.checks / f"{name}__{task}" for name in EXPECTED)):
        if path.exists():
            shutil.rmtree(path)


def validate_task(meta: dict, paths: run.Paths, ledger_src: Path, *, run_cmd=subprocess.run, log) -> dict:
    task = meta["name"]
    src = paths.root / "tb4" / "tasks" / task
    out = {"task": task, "category": meta["category"], "estimate_h": meta["estimate_h"], "ok": False,
           "failures": [], "checks": {}}
    _reset(task, paths)
    try:
        with open(paths.logs / f"build__{task}.log", "w") as handle:
            images.build(src, task, handle, run_cmd)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        out["failures"].append(f"build failed: {error}")
        return out
    agent = images.inspect(config.agent_tag(task), run_cmd)
    verifier = images.inspect(config.verifier_tag(task), run_cmd)
    out.update(workdir=agent["workdir"], user=agent["user"], agent_image_id=agent["id"],
               verifier_image_id=verifier["id"])
    if agent["arch"] != "arm64" or verifier["arch"] != "arm64":
        out["failures"].append(f"architecture {agent['arch']}/{verifier['arch']}")
        return out
    ok, text = images.python_ok(config.agent_tag(task), run_cmd)
    out["python"] = text.strip()[-200:]
    if not ok:
        out["failures"].append("python3 >= 3.10 missing")
        return out
    ok, text = images.bundle_ok(config.agent_tag(task), paths.skill, run_cmd)
    if not ok:
        out["failures"].append(f"bundle smoke failed: {text.strip()[-300:]}")
        return out
    try:
        out["copy_digest"] = copies.pin_task(src, paths.copies / task, task)
        copies.ledger_check_copy(paths.copies / task, paths.check_copies / task, agent["workdir"], ledger_src)
    except (ValueError, FileNotFoundError) as error:
        out["failures"].append(f"copy failed: {error}")
        return out
    for name, agent_name, directory in (("oracle", "oracle", paths.copies / task),
                                        ("nop", "nop", paths.copies / task),
                                        ("ledger", "oracle", paths.check_copies / task)):
        job = f"{name}__{task}"
        with open(paths.logs / f"{job}.log", "w") as handle:
            run_cmd(run.check_command(directory, agent_name, job, paths), stdout=handle, stderr=subprocess.STDOUT)
        reward = harbor_reward(paths.checks / job)
        out["checks"][name] = reward
        if reward != EXPECTED[name]:
            out["failures"].append(f"{name} reward {reward}, expected {EXPECTED[name]}")
    after = {"agent": images.inspect(config.agent_tag(task), run_cmd)["id"],
             "verifier": images.inspect(config.verifier_tag(task), run_cmd)["id"]}
    if after != {"agent": agent["id"], "verifier": verifier["id"]}:
        out["failures"].append("image ID changed during checks")
    out["ok"] = not out["failures"]
    return out


def validate_all(metas, paths: run.Paths, ledger_src: Path, out: Path, *, run_cmd=subprocess.run, log=print) -> dict:
    per_task = paths.root / "validation"
    per_task.mkdir(exist_ok=True)
    results = []
    for meta in sorted(metas, key=lambda m: m["name"]):
        saved = per_task / f"{meta['name']}.json"
        if saved.exists():
            results.append(json.loads(saved.read_text()))
            continue
        log(f"validating {meta['name']}")
        result = validate_task(meta, paths, ledger_src, run_cmd=run_cmd, log=log)
        if not result["ok"]:
            run_cmd(["docker", "image", "rm", "-f", config.agent_tag(meta["name"]), config.verifier_tag(meta["name"])],
                    capture_output=True, text=True)
        saved.write_text(json.dumps(result, indent=2) + "\n")
        results.append(result)
    ok = sum(1 for r in results if r["ok"])
    report = {"tasks": results, "summary": {"candidates": len(results), "ok": ok, "failed": len(results) - ok}}
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tasks", help="comma-separated subset")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    args = parser.parse_args(argv)
    band = json.loads(args.survey.read_text())["band"]
    if args.tasks:
        band = [m for m in band if m["name"] in set(args.tasks.split(","))]
    paths = run.Paths(args.runs).ensure()
    with run.hold_lock(paths.root / "runner.lock"):
        report = validate_all(band, paths, args.ledger, args.out)
    print(json.dumps(report["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
