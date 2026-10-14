"""One refine session per practice task, in its own offline container.

The notes state lives at RUNS/refine/state ({app/, memory/, entries.json}). A session gets the state, the
frozen refine snapshot and three inputs (task statement, transcript, result line), and Harbor's
RefineClaudeCode copies the state back out. What refine applied is read from disk: the harness ledger
(`refine-history`) and the bundle manifest before and after, never from the session's own report.
"""
import json
import shutil
import subprocess
from pathlib import Path

from bench.swepro import bundle, config, jobs
from bench.tb4 import stream

PROMPT = """/refine

You are improving the working notes of a coding agent that solves tasks in the ansible repository
(github.com/ansible/ansible). A practice task has just finished. Its evidence is in /inputs:

- /inputs/task.md: the task statement the agent was given.
- /inputs/transcript.jsonl: the agent's session transcript.
- /inputs/result.txt: the hidden-test result in one line, for example `passed` or
  `failed: 2 of 16 graded tests failed`. You will not get test names or test output.

The project is /app. It holds no ansible code, only the notes the agent will have on future ansible
tasks: CLAUDE.md, .claude/skills, .claude/agents, and project memory. Follow the refine skill as written,
with PROJECT=/app and project scope, to decide whether this evidence supports one small change that
would help on *different* future tasks in this repository.

For this study the operator authorises you to apply your own proposal: run `refine-apply` with
`--approved` and `--override-cap`. Apply at most one proposal. If nothing is worth learning, apply
nothing and say so. Do not run `refine-outcome` or `refine-undo`, and do not copy task-specific code,
file contents or test names into the notes.
"""

TASK_TOML = """schema_version = "1.4"

[task]
name = "swepro-refine/session"
description = "One refine session over a practice task's evidence."

[agent]
network_mode = "no-network"
timeout_sec = 1800.0

[verifier]
network_mode = "public"
timeout_sec = 120.0

[environment]
network_mode = "public"
build_timeout_sec = 900.0
os = "linux"
cpus = 1
memory_mb = 2048
storage_mb = 4096
"""

TEST_SH = """#!/bin/bash
mkdir -p /logs/verifier
echo 1 > /logs/verifier/reward.txt
"""

STATE = config.RUNS / "refine" / "state"


def build_task(dest: Path = config.RUNS / "refine" / "task") -> Path:
    (dest / "environment").mkdir(parents=True, exist_ok=True)
    (dest / "tests").mkdir(parents=True, exist_ok=True)
    (dest / "task.toml").write_text(TASK_TOML)
    (dest / "instruction.md").write_text(PROMPT)
    (dest / "environment" / "Dockerfile").write_text(
        f"FROM {config.REFINE_BASE_IMAGE}\nRUN mkdir -p /app /inputs\nWORKDIR /app\n")
    test_sh = dest / "tests" / "test.sh"
    test_sh.write_text(TEST_SH)
    test_sh.chmod(0o755)
    return dest


def make_inputs(task_dir: Path, trial_dir: Path, result_line: str, dest: Path) -> Path:
    """The statement the agent saw, its transcript, and the result line. Nothing from tests/ or solution/."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copyfile(task_dir / "instruction.md", dest / "task.md")
    sessions = sorted((trial_dir / "agent" / "sessions" / "projects").rglob("*.jsonl"))
    (dest / "transcript.jsonl").write_text("".join(p.read_text(errors="replace") for p in sessions))
    (dest / "result.txt").write_text(result_line + "\n")
    return dest


def history_ids(trial_dir: Path):
    try:
        data = json.loads((trial_dir / "agent" / "refine-history.json").read_text())
    except (OSError, ValueError):
        return None
    return [str(e.get("id")) for e in data.get("entries", [])]


def skill_used(trial_dir: Path) -> bool:
    """A Skill tool call, or a call to the snapshot CLI (`/refine` in the prompt loads the skill directly)."""
    events = stream.read_events(trial_dir / "agent" / "claude-code.txt")
    return (any(b.get("name") == "Skill" and (b.get("input") or {}).get("skill") == "refine"
                for _, b in stream.tool_uses(events))
            or any(".claude/skills/refine/scripts/harness.py" in c for c in stream.bash_commands(events)))


def _bundle_files(state: Path, scratch: Path) -> dict:
    return bundle.export(state, scratch)["files"]


def absorb(out_dir: Path, state: Path, archive: Path) -> list:
    """Make `out_dir` the new state (minus the refine snapshot), keep the old state in `archive`, and
    return the bundle files that changed."""
    scratch = archive.parent / f".{archive.name}.scratch"
    before = _bundle_files(state, scratch / "before")
    new = state.with_name(state.name + ".next")
    if new.exists():
        shutil.rmtree(new)
    shutil.copytree(out_dir / "app", new / "app", symlinks=True)
    shutil.rmtree(new / "app" / ".claude" / "skills" / "refine", ignore_errors=True)
    if (out_dir / "memory").is_dir():
        shutil.copytree(out_dir / "memory", new / "memory", symlinks=True)
    if (state / "entries.json").exists():
        shutil.copyfile(state / "entries.json", new / "entries.json")
    after = _bundle_files(new, scratch / "after")
    shutil.rmtree(scratch)
    archive.parent.mkdir(parents=True, exist_ok=True)
    if state.exists():
        state.rename(archive)
    new.rename(state)
    return sorted(rel for rel in set(before) | set(after) if before.get(rel) != after.get(rel))


def run_session(index: int, task: str, task_dir: Path, trial_dir: Path, result_line: str, *, runs: Path,
                skill: Path, token: str, run=subprocess.run, before_rerun=lambda reason: None) -> dict:
    state = runs / "refine" / "state"
    task_path = build_task(runs / "refine" / "task")
    inputs = make_inputs(task_dir, trial_dir, result_line, runs / "refine" / "inputs" / f"{index:03d}")

    def make_cmd(name):
        kwargs = {"tools_dir": runs / "tools", "state_dir": state, "skill_dir": skill, "inputs_dir": inputs,
                  "out_dir": runs / "refine" / "out" / name}
        return jobs.harbor_command(task_path, name, runs / "jobs", jobs.REFINE_AGENT, kwargs, claude=True)

    read, tries = jobs.run_with_reruns(config.job_name("refine", task, "refine", 1), make_cmd,
                                       jobs_dir=runs / "jobs", logs_dir=runs / "logs", env=jobs.job_env(token),
                                       run=run, before_rerun=before_rerun)
    record = {"index": index, "task": task, "result_line": result_line, "tries": tries,
              "valid": tries[-1]["reason"] is None, "entries_added": [], "changed": [], "skill_used": False,
              "over_one_edit": False, "cost_usd": (read or {}).get("cost_usd")}
    out = runs / "refine" / "out" / tries[-1]["job"]
    if record["valid"] and (out / "app").is_dir():
        trial = Path(read["trial_dir"])
        before = json.loads((state / "entries.json").read_text()) if (state / "entries.json").exists() else []
        after = history_ids(trial) or []
        record["entries_added"] = [e for e in after if e not in before]
        record["over_one_edit"] = len(record["entries_added"]) > 1
        record["skill_used"] = skill_used(trial)
        record["changed"] = absorb(out, state, runs / "refine" / "history" / f"{index:03d}")
        (state / "entries.json").write_text(json.dumps(after) + "\n")
    elif record["valid"]:
        record["valid"] = False
        record["reason"] = "no state came back"
    path = runs / "refine" / "records" / f"{index:03d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record
