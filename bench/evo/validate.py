"""Validate EvoCode tasks in the seeded order (spec: Pilot, validation and freeze, step 2).

Per task: make the agent and validation copies, build the arm64 image from the patched Dockerfile, then run
Harbor's oracle, nop and planted-ledger oracle over every round. A task is ok only when every oracle and planted
round scores 1, every graded nop round scores below 1 (round 1 graded), and the image is arm64.
Writes RUNS/validation/<task>.json per task and RUNS/validation/summary.json for the walk over the order.
"""
import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from bench.evo import config, copies, images, patch, steps
from bench.tb4 import copies as tb4_copies
from bench.tb4 import images as tb4_images
from bench.tb4 import run as tb4_run

# The code that makes copies and judges them; a saved record made by other code is validated again.
CODE_FILES = ("copies.py", "images.py", "patch.py", "steps.py", "validate.py")
CODE_DIGEST = hashlib.sha256(b"".join((Path(__file__).resolve().parent / name).read_bytes()
                                      for name in CODE_FILES)).hexdigest()
CHECKS = (("oracle", "oracle", "validation"), ("nop", "nop", "validation"), ("planted", "oracle", "planted"))
PLANTED_SLUG = "evo-planted-check"
_COLLECTED = "a planted Horizon ledger file was collected by the verifier"
# A fake ledger with test-like names in each common language; each file fails loudly if a verifier collects it.
PLANTED_LEDGER = {
    f"goals/{PLANTED_SLUG}.json": json.dumps({"slug": PLANTED_SLUG, "goal": "Planted ledger for task validation",
                                              "status": "active", "turns_used": 3, "max_turns": 200}, indent=2) + "\n",
    f"gates/{PLANTED_SLUG}/request.md": "# Request\n\nPlanted request text for task validation.\n",
    f"gates/{PLANTED_SLUG}/test_planted_gate.py": f'def test_planted_gate():\n    raise AssertionError("{_COLLECTED}")\n',
    f"gates/{PLANTED_SLUG}/planted_gate_test.go": ('package planted\n\nimport "testing"\n\n'
                                                   f'func TestPlantedGate(t *testing.T) {{\n\tt.Fatal("{_COLLECTED}")\n}}\n'),
    f"gates/{PLANTED_SLUG}/planted_gate.test.js": f'test("planted gate", () => {{\n  throw new Error("{_COLLECTED}");\n}});\n',
    f"gates/{PLANTED_SLUG}/planted_gate.test.ts": f'test("planted gate", () => {{\n  throw new Error("{_COLLECTED}");\n}});\n',
    f"gates/{PLANTED_SLUG}/test_planted_gate.sh": f'#!/bin/sh\necho "{_COLLECTED}" >&2\nexit 1\n',
}
WRAPPER = """#!/bin/bash
# Planted-ledger check: put a fake Horizon ledger in the project as the agent user, then run the real solution.
set -euo pipefail
mkdir -p {target}
cp -R /solution/horizon-ledger/. {target}/
if [ -x /solution/solve.orig.sh ]; then exec /solution/solve.orig.sh "$@"; fi
exec bash /solution/solve.orig.sh "$@"
"""


def tasks_root(runs: Path) -> Path:
    return Path(runs) / "dataset" / config.DATASET_REVISION / "tasks"


def copy_dir(runs: Path, kind: str, task: str) -> Path:
    return Path(runs) / "copies" / kind / task


def step_names(task_dir: Path) -> list:
    return [step["name"] for step in tomllib.loads((Path(task_dir) / "task.toml").read_text()).get("steps") or []]


def check_command(copy: Path, agent: str, job_name: str, jobs_dir: Path) -> list:
    return ["harbor", "run", "-p", str(copy), "-a", agent,
            "--agent-timeout-multiplier", str(config.AGENT_TIMEOUT_MULTIPLIER),
            "--no-force-build", "-n", "1", "-k", "1", "-r", "0",
            "-o", str(jobs_dir), "--job-name", job_name, "-y"]


def planted_copy(validation_copy: Path, dest: Path, workdir: str, first_step: str) -> str:
    """Copy the validation copy and wrap round 1's solve.sh so it plants PLANTED_LEDGER first."""
    if dest.exists():
        raise FileExistsError(dest)
    shutil.copytree(validation_copy, dest, symlinks=True)
    solution = dest / "steps" / first_step / "solution"
    if not (solution / "solve.sh").is_file():
        solution = dest / "solution"  # a task-wide solution runs for every step
    solve = solution / "solve.sh"
    if not solve.is_file():
        shutil.rmtree(dest)
        raise FileNotFoundError(f"no solve.sh for {first_step}")
    solve.rename(solution / "solve.orig.sh")
    for rel, text in PLANTED_LEDGER.items():
        path = solution / "horizon-ledger" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    solve.write_text(WRAPPER.format(target=shlex.quote(workdir.rstrip("/") + "/.claude/harness")))
    solve.chmod(0o755)
    return tb4_copies.tree_digest(dest)


def round_results(job_dir: Path, names: list) -> tuple:
    """Per-round rewards and [passed, total] case counts of a check job; None where a round has none."""
    trial_dir, _ = tb4_run.job_result(job_dir)
    if trial_dir is None:
        return [None] * len(names), [None] * len(names)
    found = {step["name"]: step for step in steps.read_trial(trial_dir)["steps"]}
    rewards = [found[name]["reward"] if name in found else None for name in names]
    cases = [steps.case_counts(trial_dir / "steps" / name) if name in found else None for name in names]
    return rewards, [list(c) if c else None for c in cases]


def failures(out: dict) -> list:
    rounds, problems = out["rounds"], []
    for kind in ("oracle", "planted"):
        rewards = out[kind]
        if len(rewards) != rounds or any(r is None or r < 1.0 for r in rewards):
            problems.append(f"{kind} rewards {rewards}, expected 1.0 on all {rounds} rounds")
    nop = out["nop"]
    if not nop or nop[0] is None or any(r is not None and r >= 1.0 for r in nop):
        problems.append(f"nop rewards {nop}, expected below 1.0 with round 1 graded")
    return problems


def _reset(task: str, runs: Path) -> None:
    for path in (*(copy_dir(runs, kind, task) for kind in ("agent", "validation", "planted")),
                 *(Path(runs) / "checks" / f"{name}__{task}" for name, _, _ in CHECKS)):
        if path.exists():
            shutil.rmtree(path)


def _finish(out: dict, problems: list, runs: Path) -> dict:
    out["ok"], out["reason"] = not problems, "; ".join(problems) or None
    saved = Path(runs) / "validation" / f"{out['task']}.json"
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_text(json.dumps(out, indent=2) + "\n")
    return out


def _user(value) -> str:
    text = "" if value is None else str(value)
    # a user:group form names root by its user part, e.g. "0:0" or "root:root"
    return "root" if text.split(":", 1)[0] in ("", "0", "root") else text


def agent_users(task_toml: dict, image_user) -> list:
    """The sorted distinct users Harbor 0.24.0 runs each step's setup.sh and agent as: [steps.agent].user, else
    [agent].user, else the image's USER. "", "0" and "root" are all root."""
    default = (task_toml.get("agent") or {}).get("user")
    users = set()
    for step in task_toml.get("steps") or [{}]:
        user = (step.get("agent") or {}).get("user")
        users.add(_user(user if user is not None else default if default is not None else image_user))
    return sorted(users)


def check_task_name(task: str) -> str:
    """A bare task directory name. Anything else (empty, absolute, or holding a separator or `..`) would make _reset
    delete outside RUNS/copies and RUNS/checks, for example the extracted dataset task itself."""
    if not task or Path(task).is_absolute() or any(part in task for part in ("/", "\\", "..")):
        raise ValueError(f"not a task name: {task!r}; pass the bare task directory name")
    return task


SETUP_SH_COLLISION = "project file setup.sh in the working directory would be overwritten by the round hook"


def has_project_setup_sh(tag: str, workdir: str, run=subprocess.run) -> bool:
    """Whether the image's working directory holds setup.sh: Harbor uploads each round's steps/<r>/workdir/setup.sh
    over it, and the hook deletes itself after running, so the project file would be gone every round."""
    cmd = ["docker", "run", "--rm", "--platform", images.PLATFORM, "--entrypoint", "test", tag, "-e",
           f"{workdir.rstrip('/')}/setup.sh"]
    return run(cmd, capture_output=True, text=True, timeout=600).returncode == 0


def validate_task(task: str, *, runs: Path, run=subprocess.run) -> dict:
    check_task_name(task)  # before _reset deletes anything
    runs = Path(runs)
    tag = config.image_tag(task)
    validation, agent, planted = (copy_dir(runs, kind, task) for kind in ("validation", "agent", "planted"))
    checks, logs = runs / "checks", runs / "logs"
    out = {"task": task, "copy_digest": None, "validation_copy_digest": None, "image_tag": tag, "image_id": None,
           "arch": None, "workdir": None, "user": None, "python": None, "rounds": 0, "oracle": [], "nop": [],
           "planted": [], "oracle_cases": [], "ok": False, "reason": None, "code": CODE_DIGEST}
    _reset(task, runs)
    for path in (validation.parent, agent.parent, planted.parent, checks, logs):
        path.mkdir(parents=True, exist_ok=True)
    src = tasks_root(runs) / task
    try:
        out["validation_copy_digest"] = copies.make_copy(src, validation, kind="validation", image_tag=tag)
        out["copy_digest"] = copies.make_copy(src, agent, kind="agent", image_tag=tag)
        out["arm_patch"] = json.loads((validation / copies.ARM_PATCH_FILE).read_text())
    except (patch.UnknownArchPattern, ValueError, OSError) as error:
        return _finish(out, [f"copy failed: {error}"], runs)
    names = step_names(validation)
    out["rounds"] = len(names)
    if not names:
        return _finish(out, ["task.toml has no [[steps]]"], runs)
    with open(logs / f"build__{task}.log", "w") as handle:
        for attempt in (1, 2):  # a network hiccup during apt or a download is not a property of the task
            try:
                images.build(validation, tag, handle, run)
                break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                if attempt == 2:
                    return _finish(out, [f"build failed twice: {error}"], runs)
    image = images.inspect(tag, run)
    task_toml = tomllib.loads((validation / "task.toml").read_text())
    environment = task_toml.get("environment") or {}
    # Harbor runs the agent, the hooks and the oracle in [environment].workdir when set, else the image WORKDIR
    out.update(image_id=image["id"], arch=image["arch"], workdir=environment.get("workdir") or image["workdir"],
               user=agent_users(task_toml, image["user"]))
    if image["arch"] != "arm64":
        return _finish(out, [f"architecture {image['arch']}, expected arm64"], runs)
    if has_project_setup_sh(tag, out["workdir"], run):
        return _finish(out, [SETUP_SH_COLLISION], runs)
    ok, text = tb4_images.python_ok(tag, run)
    out["python"] = {"ok": ok, "version": text.strip()[-200:]}
    try:
        planted_copy(validation, planted, out["workdir"], names[0])
    except OSError as error:
        return _finish(out, [f"planted copy failed: {error}"], runs)
    copy_for = {"validation": validation, "planted": planted}
    for name, agent_name, kind in CHECKS:
        job = f"{name}__{task}"
        with open(logs / f"{job}.log", "w") as handle:
            run(check_command(copy_for[kind], agent_name, job, checks), stdout=handle, stderr=subprocess.STDOUT)
        rewards, cases = round_results(checks / job, names)
        out[name] = rewards
        if name == "oracle":
            out["oracle_cases"] = cases
    problems = failures(out)
    if images.inspect(tag, run)["id"] != out["image_id"]:
        problems.append("image ID changed during checks")
    return _finish(out, problems, runs)


def validate_in_order(order, n: int, *, runs: Path, run=subprocess.run, log=print) -> dict:
    """Walk the seeded order until n tasks are ok; a failed planned task is replaced by the next ok one."""
    runs = Path(runs)
    (runs / "validation").mkdir(parents=True, exist_ok=True)
    selected, walked, records = [], [], {}
    for task in order:
        if len(selected) == n:
            break
        saved = runs / "validation" / f"{task}.json"
        result = json.loads(saved.read_text()) if saved.exists() else None
        if result is None or result.get("code") != CODE_DIGEST:
            log(f"validating {task}")
            result = validate_task(task, runs=runs, run=run)
            if not result["ok"]:
                images.remove(config.image_tag(task), run)
        records[task] = result
        walked.append({"task": task, "ok": result["ok"], "reason": result["reason"]})
        if result["ok"]:
            selected.append(task)
    planned = list(order)[:n]
    replacements = [task for task in selected if task not in planned]
    dropped = [w for w in walked if not w["ok"] and w["task"] in planned]
    swaps = [{"dropped": w["task"], "reason": w["reason"],
              "replaced_by": replacements[i] if i < len(replacements) else None} for i, w in enumerate(dropped)]
    for swap in swaps:
        log(f"swap: {swap['dropped']} failed validation ({swap['reason']}); replaced by {swap['replaced_by']}")
    summary = {"n": n, "order": list(order), "selected": selected, "walked": walked, "swaps": swaps,
               "complete": len(selected) == n,
               "python_missing": [t for t in selected if (records[t].get("python") or {}).get("ok") is not True]}
    (runs / "validation" / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--n", type=int, help="walk RUNS/order.json until N tasks are ok")
    target.add_argument("--task", help="validate one task now (the walkthrough task for the dry run)")
    args = parser.parse_args(argv)
    with tb4_run.hold_lock(args.runs / "runner.lock"):
        if args.task is not None:  # an empty name is refused by validate_task, not read as "no task"
            result = validate_task(args.task, runs=args.runs)
            print(json.dumps({"task": result["task"], "ok": result["ok"], "reason": result["reason"]}))
            return 0 if result["ok"] else 1
        order = json.loads((args.runs / "order.json").read_text())["order"]
        summary = validate_in_order(order, args.n, runs=args.runs)
    print(json.dumps({"selected": summary["selected"], "swaps": summary["swaps"], "complete": summary["complete"],
                      "python_missing": summary.get("python_missing", [])}))
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
