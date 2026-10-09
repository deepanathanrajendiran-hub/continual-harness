"""Run one Harbor multi-step job per (task, arm, attempt, phase), paced by subscription usage, and keep the evidence."""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from bench.evo import config, copies, dataset, images, order, steps
from bench.tb4 import stream
from bench.tb4.run import (USAGE_EXCEPTIONS, ImageChanged, InfrastructureFailure, RunnerBusy, agent_env, cleanup_job,
                           compose_containers, copy_ledger, hold_lock, job_result, probe_usage, read_token,
                           remove_containers, running_trials, sleep_marker, wait_for_headroom)

PHASES = ("dry", "main")
WEEKLY_PER_AGENT_HOUR = 0.0127    # TB4: seven-day utilization one agent-hour used
FIVE_HOUR_PER_AGENT_HOUR = 0.098  # TB4: five-hour utilization one agent-hour used
FIVE_HOUR_WINDOW_HOURS = 5.0

# Harbor exception types that mean the API or the network failed, not the model: the run is invalid and rerun.
API_EXCEPTIONS = ("ApiError", "ApiRateLimitError", "ApiInternalServerError", "ApiOverloadedError",
                  "ApiConnectionClosedError", "ApiResponseStalledError", "UnknownApiError",
                  "ApiProviderResourceNotFoundError", "AgentAuthenticationError", "ModelNotFoundError",
                  "NetworkConnectionError")
# Harbor exception types that are the model's own outcome: EvoCode counts the round as failed; the run stays valid.
MODEL_OUTCOMES = ("AgentTimeoutError", "AgentSafetyRefusalError", "ContextWindowExceededError",
                  "OutputTokenExceededError", "VerifierTimeoutError", "RewardFileNotFoundError",
                  "RewardFileEmptyError", "VerifierOutputParseError")


class NotValidated(RuntimeError):
    """The task has no passing validation record, so it may not run."""


class MissingInput(FileNotFoundError):
    """The agent copy, the arm's prompt file or the Horizon bundle is missing."""


class TaskDropped(RuntimeError):
    """An arm was invalid twice; the task is dropped and the phase stops for the operator to look."""


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def tasks(self): return self.root / "dataset" / config.DATASET_REVISION / "tasks"

    @property
    def agent_copies(self): return self.root / "copies" / "agent"

    @property
    def prompts(self): return self.root / "prompts"

    @property
    def skill(self): return self.root / "bundle" / "horizon"

    @property
    def validation(self): return self.root / "validation"

    @property
    def jobs(self): return self.root / "jobs"

    @property
    def records(self): return self.root / "records"

    @property
    def ledgers(self): return self.root / "ledgers"

    @property
    def logs(self): return self.root / "logs"

    @property
    def deviations(self): return self.root / "deviations.md"

    @property
    def lock(self): return self.root / "runner.lock"

    def copy(self, task: str) -> Path:
        return self.agent_copies / task

    def prompt(self, task: str, arm: str) -> Path:
        return self.prompts / f"{task}__{arm}.md"

    def ensure(self):
        for d in (self.agent_copies, self.prompts, self.validation, self.jobs, self.records, self.ledgers, self.logs):
            d.mkdir(parents=True, exist_ok=True)
        return self


@dataclass(frozen=True)
class EvoTrial:
    phase: str
    task: str
    arm: str
    attempt: int

    @property
    def job_name(self) -> str:
        return config.job_name(self.phase, self.task, self.arm, self.attempt)


def harbor_command(trial: EvoTrial, paths: Paths) -> list:
    cmd = ["harbor", "run", "-p", str(paths.copy(trial.task)), "-a", "claude-code", "-m", config.MODEL,
           "--effort", config.EFFORT,
           "--ak", f"version={config.CLAUDE_CODE_VERSION}",
           "--ak", "disable_web_search=true",
           "--ae", "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}",
           "--ae", f"CLAUDE_CODE_MAX_OUTPUT_TOKENS={config.MAX_OUTPUT_TOKENS}",
           "--agent-timeout-multiplier", str(config.AGENT_TIMEOUT_MULTIPLIER),
           "--agent-setup-timeout-multiplier", str(config.AGENT_SETUP_TIMEOUT_MULTIPLIER),
           "--extra-instruction-path", str(paths.prompt(trial.task, trial.arm)),
           "--ek", "keep_containers=true", "--no-force-build",
           "-n", "1", "-k", "1", "-r", "0",
           "-o", str(paths.jobs), "--job-name", trial.job_name, "-y"]
    if trial.arm == "horizon":
        cmd += ["--skill", str(paths.skill)]
    return cmd


def worst_case_hours(task_info: dict) -> float:
    """Agent-hours if every round runs to its timeout."""
    return task_info["rounds"] * task_info["agent_timeout_sec"] * config.AGENT_TIMEOUT_MULTIPLIER / 3600


def needed_weekly(hours: float) -> float:
    return hours * WEEKLY_PER_AGENT_HOUR


def headroom_limits(task_info: dict) -> tuple:
    """(five-hour, seven-day) utilization above which a job waits, so its worst case stays under the ceilings."""
    hours = worst_case_hours(task_info)
    five = config.FIVE_HOUR_CEILING - min(hours, FIVE_HOUR_WINDOW_HOURS) * FIVE_HOUR_PER_AGENT_HOUR
    return round(five, 4), round(config.WEEKLY_CEILING - needed_weekly(hours), 4)


def task_infos(paths: Paths) -> dict:
    return {info["task"]: info for info in dataset.list_tasks(paths.tasks)}


def prepare(info: dict, paths: Paths) -> Path:
    """Make the agent copy and both prompt files once; an existing copy or prompt is never rewritten."""
    task = info["task"]
    dest = paths.copy(task)
    if not dest.exists():
        tmp = dest.with_name(dest.name + ".tmp")
        if tmp.exists():
            shutil.rmtree(tmp)
        copies.make_copy(Path(info["dir"]), tmp, kind="agent", image_tag=config.image_tag(task))
        os.replace(tmp, dest)
    for arm in config.ARMS:
        if not paths.prompt(task, arm).exists():
            copies.write_prompt(paths.prompt(task, arm), arm, dataset.minutes(info))
    return dest


def _write_json(path: Path, obj) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def _exception_type(value):
    if isinstance(value, dict):
        return value.get("exception_type")
    return value or None


def started_steps(read: dict) -> list:
    """(step, stream-json events) for every step whose agent phase started, in step order."""
    return [(s, stream.read_events(Path(s["agent_dir"]) / "claude-code.txt") if s.get("agent_dir") else [])
            for s in read["steps"] if s.get("agent_started")]


def _evidence(step: dict, events: list) -> list:
    """A timed-out round's claude is killed mid-write, so a cut-off last line is not evidence."""
    if _exception_type(step.get("exception")) == "AgentTimeoutError" and events and events[-1].get("type") == "_raw":
        return events[:-1]
    return events


def classify(read, slept: bool):
    """Why a finished job is invalid ("interrupted", "usage_limit", "api_error", "infrastructure",
    "host_slept"), or None when it is valid. `read` is steps.read_trial output, or None without a result.
    Harbor puts every agent-phase exception on the started step, so its type decides: usage and API types
    invalidate the run, MODEL_OUTCOMES do not, and any other type is infrastructure (docker exec, container)."""
    if read is None:
        return "infrastructure"
    trial_exception = _exception_type(read.get("trial_exception"))
    if trial_exception == "CancelledError":
        return "interrupted"
    started = started_steps(read)
    events = [_evidence(s, e) for s, e in started]
    types = [_exception_type(s.get("exception")) for s, _ in started]
    if any(t in USAGE_EXCEPTIONS for t in types) or any(stream.usage_limit_evidence(e) for e in events):
        return "usage_limit"
    if any(t in API_EXCEPTIONS for t in types) or any(stream.terminal_api_error(e) for e in events):
        return "api_error"
    if (trial_exception or not started
            or any(t and t not in MODEL_OUTCOMES for t in types)
            or any(s.get("exception") and not s.get("agent_started") for s in read["steps"])):
        return "infrastructure"
    if slept:
        return "host_slept"
    return None


def _cwd(events):
    return next((e.get("cwd") for e in events if e.get("type") == "system" and e.get("subtype") == "init"), None)


def final_ledger(streams, containers, dest: Path, run=subprocess.run):
    """Copy the project ledger from the kept main container: the state after the last round."""
    candidates = []
    for events in streams:
        cwd = _cwd(events)
        for path in (stream.ledger_candidates(events, cwd) if cwd else []):
            if path not in candidates:
                candidates.append(path)
    return copy_ledger(containers, candidates, dest, run) if candidates else None


def _harbor_version(job_dir: Path):
    try:
        return json.loads((job_dir / "lock.json").read_text())["harbor"]["version"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def validated_image(task: str, paths: Paths) -> str:
    path = paths.validation / f"{task}.json"
    if not path.exists():
        raise NotValidated(f"{task}: no validation record; run python3 -m bench.evo.validate first")
    data = json.loads(path.read_text())
    if not data.get("ok"):
        raise NotValidated(f"{task}: validation did not pass: {data.get('reason')}")
    return data["image_id"]


def check_inputs(trial: EvoTrial, paths: Paths) -> None:
    needed = [paths.copy(trial.task), paths.prompt(trial.task, trial.arm)]
    if trial.arm == "horizon":
        needed.append(paths.skill / "SKILL.md")
    missing = [str(p) for p in needed if not p.exists()]
    if missing:
        raise MissingInput(f"{trial.job_name}: missing {missing}")


def new_record(trial: EvoTrial, paths: Paths, freeze: str) -> dict:
    return {"job_name": trial.job_name, "phase": trial.phase, "task": trial.task, "arm": trial.arm,
            "attempt": trial.attempt, "started": None, "finished": None, "exit_code": None,
            "job_dir": str(paths.jobs / trial.job_name), "trial_dir": None, "valid": False, "invalid_reason": None,
            "image_id": None, "container_image": None, "freeze": freeze, "harbor_version": None,
            "claude_code_version": None, "command": harbor_command(trial, paths), "usage_before": None,
            "usage_after": None, "ledger": None}


def _finish(record: dict, trial: EvoTrial, paths: Paths, trial_dir: Path, result: dict, slept: bool, run) -> None:
    record["trial_dir"] = str(trial_dir)
    record["harbor_version"] = _harbor_version(paths.jobs / trial.job_name)
    record["claude_code_version"] = (result.get("agent_info") or {}).get("version")
    read = steps.read_trial(trial_dir)
    streams = [events for _, events in started_steps(read)]
    containers = compose_containers(result.get("trial_name") or trial_dir.name, run)
    main = next((c for c in containers if c["role"] == "agent" and c["service"] == "main"), None)
    record["container_image"] = main["image"] if main else None
    reason = classify(read, slept)
    if reason is None and main is not None and main["image"] != record["image_id"]:
        reason = "infrastructure"  # Harbor ran another image than the validated one
    record["invalid_reason"] = reason
    record["usage_after"] = next((info for info in map(stream.rate_limit_info, reversed(streams)) if info), None)
    if streams:
        record["ledger"] = final_ledger(streams, containers, paths.ledgers / trial.job_name, run)
    remove_containers(containers, run)


def run_trial(trial: EvoTrial, paths: Paths, token: str, freeze: str, *, run=subprocess.run, now=time.time,
              probe, info=None, sleep=time.sleep, log=print) -> dict:
    record_path = paths.records / f"{trial.job_name}.json"
    if record_path.exists():
        return json.loads(record_path.read_text())
    busy = running_trials(run)
    if busy:
        raise RunnerBusy(f"trial containers still running: {busy}")
    record = new_record(trial, paths, freeze)
    job_dir = paths.jobs / trial.job_name
    if job_dir.exists():  # an earlier runner stopped mid-job: record it without waiting or running
        cleanup_job(job_dir, run)
        record["invalid_reason"] = "interrupted"
        _write_json(record_path, record)
        return record
    check_inputs(trial, paths)
    expected = validated_image(trial.task, paths)
    found = images.inspect(config.image_tag(trial.task), run)["id"]
    if found != expected:
        raise ImageChanged(f"{trial.task}: {config.image_tag(trial.task)} is {found}, validated {expected}")
    record["image_id"] = expected
    five_limit, weekly_limit = headroom_limits(info or task_infos(paths)[trial.task])
    record["usage_before"] = wait_for_headroom(probe, five_limit, weekly_limit, sleep=sleep, now=now, log=log)
    slept_before = sleep_marker(run)
    record["started"] = now()
    with open(paths.logs / f"{trial.job_name}.log", "w") as out:
        proc = run(record["command"], env=agent_env(token), stdout=out, stderr=subprocess.STDOUT)
    record["finished"], record["exit_code"] = now(), proc.returncode
    slept = sleep_marker(run) != slept_before
    if not job_dir.exists():  # Harbor never started the job: fix the command or host; no attempt is spent
        raise InfrastructureFailure(f"{trial.job_name}: harbor exited {proc.returncode} without a job directory; "
                                    f"see {paths.logs / (trial.job_name + '.log')}")
    trial_dir, result = job_result(job_dir)
    if trial_dir is None:
        cleanup_job(job_dir, run)
        record["invalid_reason"] = "infrastructure"
    else:
        _finish(record, trial, paths, trial_dir, result, slept, run)
    record["valid"] = record["invalid_reason"] is None
    _write_json(record_path, record)
    return record


def _drop_prefix(phase: str, task: str) -> str:
    return f"- {phase} {task}: dropped"


def dropped_tasks(paths: Paths, phase: str) -> list:
    """Tasks of this phase that deviations.md records as dropped, in the order they were dropped."""
    if not paths.deviations.exists():
        return []
    pattern = re.compile(rf"^- {re.escape(phase)} (\S+): dropped\b", re.M)
    return pattern.findall(paths.deviations.read_text())


def note_drop(paths: Paths, phase: str, task: str, arm: str, attempts: list) -> str:
    """Append the drop line; `attempts` is [(attempt number, invalid_reason), ...]."""
    detail = "; ".join(f"a{number}: {reason}" for number, reason in attempts)
    line = f"{_drop_prefix(phase, task)} after two invalid runs of the {arm} arm ({detail})\n"
    with open(paths.deviations, "a") as handle:
        handle.write(line)
    return line


def valid_record(paths: Paths, phase: str, task: str, arm: str):
    """The first valid record of this (phase, task, arm), whatever its attempt number, or None."""
    for path in sorted(paths.records.glob("*.json")):
        record = json.loads(path.read_text())
        if (record.get("phase"), record.get("task"), record.get("arm")) == (phase, task, arm) and record.get("valid"):
            return record
    return None


def run_phase(phase: str, tasks, *, attempt: int = 1, paths: Paths, token: str, freeze: str, probe, infos=None,
              run=subprocess.run, now=time.time, sleep=time.sleep, log=print) -> dict:
    """Run each task's arms in its seeded order; retry an invalid run once; two invalid runs drop the task.
    An arm that already has a valid record, of any attempt, is not run again: one scored attempt per arm."""
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {PHASES}")
    infos = task_infos(paths) if infos is None else infos
    missing = [task for task in tasks if task not in infos]
    if missing:
        raise MissingInput(f"{missing} not in {paths.tasks}; run python3 -m bench.evo.dataset fetch first")
    records, dropped = [], []
    for task in tasks:
        if task in dropped_tasks(paths, phase):
            log(f"{task}: dropped earlier in phase {phase}; skipping")
            dropped.append(task)
            continue
        prepare(infos[task], paths)
        for arm in order.arm_order(task, config.SEED):
            done = valid_record(paths, phase, task, arm)
            if done:
                log(f"{task} {arm}: a valid record exists ({done['job_name']}); not run again")
                records.append(done)
                continue
            attempts = []
            for number in (attempt, attempt + 1):
                record = run_trial(EvoTrial(phase, task, arm, number), paths, token, freeze, run=run, now=now,
                                   probe=probe, info=infos[task], sleep=sleep, log=log)
                records.append(record)
                log(f"{record['job_name']}: {'valid' if record['valid'] else record['invalid_reason']}")
                if record["valid"]:
                    break
                attempts.append((number, record["invalid_reason"]))
            else:
                raise TaskDropped(note_drop(paths, phase, task, arm, attempts).strip())
    return {"records": records, "dropped": dropped}


def main_tasks(prereg: dict, dropped) -> list:
    """The pre-registered tasks, then one reserve per main task dropped so far, in reserve order: a drop is
    replaced by the next unused reserve, and with none left it stays a drop."""
    reserve = list(prereg.get("reserve") or [])
    return list(prereg["tasks"]) + reserve[:len(set(dropped))]


def phase_tasks(phase: str, prereg_path: Path, only=None, *, paths=None, prereg=None) -> list:
    """The walkthrough task for the dry run; for the main run the pre-registered list plus the reserves that
    replace the main tasks deviations.md records as dropped under `paths` (none without `paths`). The main run
    reads `prereg` (the frozen record) when it is given, else the file at `prereg_path`."""
    if phase == "dry":
        tasks = [config.WALKTHROUGH]
    else:
        dropped = dropped_tasks(paths, "main") if paths is not None else []
        record = prereg if prereg is not None else json.loads(Path(prereg_path).read_text())
        tasks = main_tasks(record, dropped)
    if only is None:
        return tasks
    if only not in tasks:
        raise SystemExit(f"--only {only}: not a {phase} task ({', '.join(tasks)})")
    return [only]


def main(argv=None, *, require_freeze=None, require_frozen_record=None, verify_runs=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=PHASES, required=True)
    parser.add_argument("--only", help="run just this task of the phase")
    parser.add_argument("--attempt", type=int, default=1, help="first attempt number (a retry uses the next)")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--prereg", type=Path, default=config.DOCS / "prereg.json")
    parser.add_argument("--print-commands", action="store_true", help="print the Harbor commands and exit")
    args = parser.parse_args(argv)
    paths = Paths(args.runs)
    # for a main run this list only serves --print-commands and the --only check: the run itself plans below from
    # the frozen record, never from the unchecked --prereg file
    tasks = phase_tasks(args.phase, args.prereg, args.only, paths=paths)
    if args.print_commands:
        for task in tasks:
            for arm in order.arm_order(task, config.SEED):
                trial = EvoTrial(args.phase, task, arm, args.attempt)
                print(" ".join(shlex.quote(x) for x in harbor_command(trial, paths)))
        return 0
    paths.ensure()
    with hold_lock(paths.lock):
        freeze = "pre-freeze"
        if args.phase == "main":
            # Task 11; imported late so this module stands alone
            from bench.evo import prereg as frozen
            require_freeze = require_freeze or frozen.require_freeze
            require_frozen_record = require_frozen_record or frozen.require_frozen_record
            verify_runs = verify_runs or frozen.verify_runs
            freeze = require_freeze(subprocess.run)
            record = require_frozen_record(args.prereg, subprocess.run)
            tasks = phase_tasks(args.phase, args.prereg, args.only, paths=paths, prereg=record)
            # a validation rerun after the freeze rebuilds the image and rewrites its record: refuse that here
            pinned = record["task_details"]
            for task in tasks:
                if validated_image(task, paths) != (pinned.get(task) or {}).get("image_id"):
                    raise ImageChanged(f"{task}: validated image differs from the pre-registered one")
            verify_runs(record, args.runs, tasks)  # the bundle, prompt files and agent copies are the pinned ones
        token = read_token()
        try:
            result = run_phase(args.phase, tasks, attempt=args.attempt, paths=paths, token=token, freeze=freeze,
                               probe=lambda: probe_usage(token))
        except TaskDropped as error:
            print(f"stopped: {error}", file=sys.stderr)
            return 3
    print(json.dumps({"phase": args.phase, "dropped": result["dropped"],
                      "records": [[r["job_name"], r["valid"], r["invalid_reason"]] for r in result["records"]]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
