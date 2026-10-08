"""Run one-trial Harbor jobs in a fixed order, pace them by subscription usage, and keep the evidence."""
import argparse
import contextlib
import fcntl
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from bench.tb4 import config, draw, images, stream

STRIP_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_MAX_TURNS",
             "CLAUDE_CODE_EFFORT_LEVEL", "MAX_THINKING_TOKENS", "CLAUDE_CODE_MAX_OUTPUT_TOKENS")
FROZEN_PATHS = ("bench", "docs/evaluations/tb4-horizon-pilot/prompts",
                "docs/evaluations/tb4-horizon-pilot/manifest.csv",
                "docs/evaluations/tb4-horizon-pilot/evidence/draw.json")
RESULTS = "docs/evaluations/tb4-horizon-pilot/results.jsonl"
USAGE_EXCEPTIONS = ("ApiUsageLimitError", "ApiRateLimitError")
_USAGE_TEXT = re.compile(r"usage limit|rate.?limit|status=rejected", re.I)
_TRIAL_PROJECT = re.compile(r"__[a-z0-9]{7}__(?:env|verifier__trial)$")


class Interrupted(RuntimeError):
    """A job directory exists without a runner record: the pair reruns with a new attempt."""


class ImageChanged(RuntimeError):
    """A pinned image tag no longer has its validated ID."""


class NotFrozen(RuntimeError):
    """Measured trials need HEAD at the freeze tag and the frozen files unchanged."""


class RunnerBusy(RuntimeError):
    """Another runner holds the lock, or a trial's containers are still running."""


class ProbeError(RuntimeError):
    """The usage probe call failed; this is never read as 'no limit'."""


class InfrastructureFailure(RuntimeError):
    """A trial ended before the agent phase; fix the environment before spending more pairs."""


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def jobs(self): return self.root / "jobs"

    @property
    def checks(self): return self.root / "checks"

    @property
    def records(self): return self.root / "records"

    @property
    def ledgers(self): return self.root / "ledgers"

    @property
    def logs(self): return self.root / "logs"

    @property
    def copies(self): return self.root / "copies"

    @property
    def check_copies(self): return self.root / "check-copies"

    @property
    def skill(self): return self.root / "bundle" / "horizon"

    def ensure(self):
        for d in (self.jobs, self.checks, self.records, self.ledgers, self.logs, self.copies, self.check_copies):
            d.mkdir(parents=True, exist_ok=True)
        return self


@dataclass(frozen=True)
class Trial:
    task: str
    arm: str
    attempt: int
    phase: str
    workdir: str
    agent_image_id: str
    verifier_image_id: str

    @property
    def job_name(self) -> str:
        prefix = "setup__" if self.phase == "setup" else ""
        return f"{prefix}{self.task}__{self.arm}__a{self.attempt}"


@dataclass(frozen=True)
class Pace:
    first: float = 0.5         # five-hour utilization allowed before a pair's first trial
    second: float = 0.8        # ... before the pair's second trial
    weekly: float = 0.9        # seven-day utilization ceiling
    weekly_step: float = 0.05  # seven-day utilization one trial uses (calibrated in Task 16)

    def limits(self, index_in_pair: int):
        if index_in_pair == 0:
            return self.first, round(self.weekly - 2 * self.weekly_step, 4)
        return self.second, None


def harbor_command(trial: Trial, paths: Paths) -> list:
    cmd = ["harbor", "run", "-p", str(paths.copies / trial.task), "-a", "claude-code", "-m", config.MODEL,
           "--effort", config.EFFORT,
           "--ak", f"version={config.CLAUDE_CODE_VERSION}",
           "--ak", "disable_web_search=true",
           "--ae", "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}",
           "--ae", f"CLAUDE_CODE_MAX_OUTPUT_TOKENS={config.MAX_OUTPUT_TOKENS}",
           "--agent-timeout-multiplier", str(config.AGENT_TIMEOUT_MULTIPLIER),
           "--agent-setup-timeout-multiplier", str(config.AGENT_SETUP_TIMEOUT_MULTIPLIER),
           "--extra-instruction-path", str(config.PROMPTS / f"{trial.arm}.md"),
           "--ek", "keep_containers=true", "--no-force-build",
           "-n", "1", "-k", "1", "-r", "0",
           "-o", str(paths.jobs), "--job-name", trial.job_name, "-y"]
    if trial.arm == "horizon":
        cmd += ["--skill", str(paths.skill)]
    return cmd


def check_command(copy_dir: Path, agent: str, job_name: str, paths: Paths) -> list:
    return ["harbor", "run", "-p", str(copy_dir), "-a", agent,
            "--agent-timeout-multiplier", str(config.AGENT_TIMEOUT_MULTIPLIER),
            "--no-force-build", "-n", "1", "-k", "1", "-r", "0",
            "-o", str(paths.checks), "--job-name", job_name, "-y"]


def agent_env(token: str, base=None) -> dict:
    env = {k: v for k, v in (os.environ if base is None else base).items() if k not in STRIP_ENV}
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    env["CLAUDE_FORCE_OAUTH"] = "1"  # host env only; never --ae (Harbor would scrub every "1")
    return env


def read_token(run=subprocess.run) -> str:
    proc = run(["security", "find-generic-password", "-s", config.KEYCHAIN_SERVICE, "-w"],
               capture_output=True, text=True)
    token = (proc.stdout or "").strip()
    if proc.returncode != 0 or not token:
        raise RuntimeError(f"no token in Keychain service {config.KEYCHAIN_SERVICE}; see plan step A2")
    return token


def claude_bin() -> str:
    return shutil.which("claude") or "claude"


def isolated_claude_env(token: str, config_dir: str) -> dict:
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": config_dir,
            "CLAUDE_CONFIG_DIR": config_dir, "CLAUDE_CODE_OAUTH_TOKEN": token, "LANG": "en_US.UTF-8",
            "DISABLE_AUTOUPDATER": "1"}


def probe_command() -> list:
    return [claude_bin(), "-p", "--model", config.PROBE_MODEL, "--tools", "", "--disable-slash-commands",
            "--no-session-persistence", "--strict-mcp-config", "--output-format", "stream-json", "--verbose"]


def probe_usage(token: str, run=subprocess.run):
    try:
        with tempfile.TemporaryDirectory() as cfg:
            proc = run(probe_command(), input="Reply with the single word: ok", capture_output=True, text=True,
                       env=isolated_claude_env(token, cfg), cwd=cfg, timeout=300)
    except (subprocess.TimeoutExpired, OSError) as error:
        raise ProbeError(f"usage probe did not finish: {error}") from error
    events = stream.parse_lines(proc.stdout or "")
    info = stream.rate_limit_info(events)
    if info and not str(info.get("status") or "allowed").startswith("allowed"):
        return info  # a rejected window: wait_seconds sleeps until its reset
    result = stream.result_record(events)
    if proc.returncode != 0 or result is None or result.get("is_error"):
        raise ProbeError(f"usage probe failed (exit {proc.returncode}): {(proc.stderr or '')[-300:]}")
    return info


def wait_seconds(info, now: float, five_limit: float, weekly_limit) -> int:
    if not info:
        return 0
    five_limit = max(five_limit, 0.05)  # a fresh window always admits a trial
    status = str(info.get("status") or "allowed")
    five, seven = info.get("five_hour"), info.get("seven_day")
    if not status.startswith("allowed") or (five is not None and five >= five_limit):
        reset = info.get("five_hour_resets_at") or now + 3600
        return max(60, int(reset - now) + 60)
    if weekly_limit is not None and seven is not None and seven >= weekly_limit:
        reset = info.get("seven_day_resets_at") or now + 3600
        return max(60, int(reset - now) + 60)
    return 0


def wait_for_headroom(probe, five_limit: float, weekly_limit, sleep=time.sleep, now=time.time, log=print,
                      max_waits: int = 48):
    for _ in range(max_waits):
        try:
            info = probe()
        except ProbeError as error:
            log(f"{error}; retrying in 600 s")
            sleep(600)
            continue
        seconds = wait_seconds(info, now(), five_limit, weekly_limit)
        if seconds == 0:
            return info
        log(f"usage {info}; waiting {seconds} s")
        sleep(seconds)
    raise RuntimeError("usage headroom did not return")


def sleep_marker(run=subprocess.run) -> str:
    return run(["sysctl", "-n", "kern.sleeptime", "kern.waketime"], capture_output=True, text=True).stdout or ""


def _inspect(ids, run) -> list:
    return json.loads(run(["docker", "inspect", *ids], capture_output=True, text=True, check=True).stdout)


def running_trials(run=subprocess.run) -> list:
    ids = run(["docker", "ps", "-q", "--filter", "label=com.docker.compose.project"],
              capture_output=True, text=True, check=True).stdout.split()
    if not ids:
        return []
    projects = {((d.get("Config") or {}).get("Labels") or {}).get("com.docker.compose.project", "")
                for d in _inspect(ids, run)}
    return sorted(p for p in projects if _TRIAL_PROJECT.search(p))


def sanitize(name: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "-", name.lower())


def compose_containers(trial_name: str, run=subprocess.run) -> list:
    ids = run(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project"],
              capture_output=True, text=True, check=True).stdout.split()
    if not ids:
        return []
    prefix = sanitize(trial_name) + "__"
    found = []
    for item in _inspect(ids, run):
        labels = (item.get("Config") or {}).get("Labels") or {}
        project = labels.get("com.docker.compose.project", "")
        if project.startswith(prefix):
            found.append({"id": item["Id"], "project": project, "image": item.get("Image"),
                          "service": labels.get("com.docker.compose.service", ""),
                          "role": "verifier" if "__verifier" in project else "agent"})
    return found


def copy_ledger(containers, candidates, dest_root: Path, run=subprocess.run) -> dict:
    if dest_root.exists():
        raise FileExistsError(f"{dest_root} exists; move stale ledgers aside first")
    agent = next((c for c in containers if c["role"] == "agent" and c["service"] == "main"), None)
    copied = {}
    if agent:
        dest_root.mkdir(parents=True)
        for i, path in enumerate(candidates):
            dest = dest_root / str(i)
            proc = run(["docker", "cp", f"{agent['id']}:{path}", str(dest)], capture_output=True, text=True)
            if proc.returncode == 0:
                copied[path] = str(dest)
    return {"candidates": list(candidates), "copied": copied}


def remove_containers(containers, run=subprocess.run) -> None:
    if containers:
        run(["docker", "rm", "-f", *[c["id"] for c in containers]], capture_output=True, text=True)
    for project in sorted({c["project"] for c in containers}):
        for kind in ("network", "volume"):
            listed = run(["docker", kind, "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"],
                         capture_output=True, text=True).stdout.split()
            if listed:
                run(["docker", kind, "rm", *listed], capture_output=True, text=True)


def cleanup_job(job_dir: Path, run=subprocess.run) -> None:
    """Remove the containers of every trial directory Harbor created under a job."""
    if job_dir.is_dir():
        for trial_dir in sorted(p for p in job_dir.iterdir() if p.is_dir()):
            remove_containers(compose_containers(trial_dir.name, run), run)


def job_result(job_dir: Path):
    found = sorted(job_dir.glob("*/result.json"))
    if len(found) != 1:
        return None, None
    return found[0].parent, json.loads(found[0].read_text())


def _write_json(path: Path, obj) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


@contextlib.contextmanager
def hold_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RunnerBusy(f"another runner (pid {path.read_text().strip() or '?'}) holds {path}") from error
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        yield


def _base(trial: Trial, freeze: str) -> dict:
    return {**asdict(trial), "job_name": trial.job_name, "freeze_commit": freeze, "protocol_deviations": []}


def run_trial(trial: Trial, paths: Paths, token: str, freeze: str, *, run=subprocess.run, now=time.time,
              usage=None) -> dict:
    record_path = paths.records / f"{trial.job_name}.json"
    if record_path.exists():
        return json.loads(record_path.read_text())
    busy = running_trials(run)
    if busy:
        raise RunnerBusy(f"trial containers still running: {busy}")
    job_dir = paths.jobs / trial.job_name
    if job_dir.exists():
        cleanup_job(job_dir, run)
        _write_json(record_path, {**_base(trial, freeze), "interrupted": True})
        raise Interrupted(f"{trial.job_name}: job directory exists without a record")
    expected = {"agent": trial.agent_image_id, "verifier": trial.verifier_image_id}
    found = {"agent": images.inspect(config.agent_tag(trial.task), run)["id"],
             "verifier": images.inspect(config.verifier_tag(trial.task), run)["id"]}
    if found != expected:
        raise ImageChanged(f"{trial.task}: {found} != {expected}")
    slept_before = sleep_marker(run)
    started = now()
    with open(paths.logs / f"{trial.job_name}.log", "w") as log:
        proc = run(harbor_command(trial, paths), env=agent_env(token), stdout=log, stderr=subprocess.STDOUT)
    record = {**_base(trial, freeze), "usage_before": usage, "started_at": started, "finished_at": now(),
              "harbor_exit": proc.returncode, "agent_ran": False, "usage_limit": False, "trial_rate_limit": None,
              "image_ids_expected": expected, "trial_dir": None, "container_images": {}, "ledger": None}
    if sleep_marker(run) != slept_before:
        record["protocol_deviations"].append(config.HOST_SLEPT)
    trial_dir, result = job_result(job_dir)
    if trial_dir is None:
        record["protocol_deviations"].append("expected exactly one trial directory with result.json")
        cleanup_job(job_dir, run)
    else:
        record["trial_dir"] = str(trial_dir)
        record["agent_ran"] = bool(result.get("agent_execution"))
        containers = compose_containers(result["trial_name"], run)
        events = stream.read_events(trial_dir / "agent" / "claude-code.txt")
        exception = (result.get("exception_info") or {}).get("exception_type")
        api_error = stream.terminal_api_error(events) or ""
        record["usage_limit"] = exception in USAGE_EXCEPTIONS or bool(_USAGE_TEXT.search(api_error))
        record["trial_rate_limit"] = stream.rate_limit_info(events)
        record["ledger"] = copy_ledger(containers, stream.ledger_candidates(events, trial.workdir),
                                       paths.ledgers / trial.job_name, run)
        for c in sorted(containers, key=lambda c: c["service"] != "main"):
            record["container_images"].setdefault(c["role"], c["image"])
        remove_containers(containers, run)
    _write_json(record_path, record)
    return record


def trials_for(rows, phase: str, attempt: int, only=None) -> list:
    trials = []
    for row in rows:
        is_setup = row["first_arm"] == "setup"
        if (phase == "setup") != is_setup or (only and row["task"] not in only):
            continue
        first = "control" if is_setup else row["first_arm"]
        for arm in (first, "horizon" if first == "control" else "control"):
            trials.append(Trial(row["task"], arm, attempt, phase, row["workdir"],
                                row["agent_image_id"], row["verifier_image_id"]))
    return trials


def skip_reason(partner_record: Path):
    """Why this arm need not run: its partner is already known to be invalid."""
    if not partner_record.exists():
        return None
    partner = json.loads(partner_record.read_text())
    if partner.get("interrupted"):
        return "partner interrupted"
    if partner.get("skipped"):
        return None
    if partner.get("agent_ran") is False:
        return "partner never started"
    if config.HOST_SLEPT in (partner.get("protocol_deviations") or []):
        return "partner host slept"
    if partner.get("usage_limit"):
        return "partner hit a usage limit"
    return None


def run_all(trials, paths: Paths, token: str, freeze: str, *, probe, pace: Pace = Pace(), run=subprocess.run,
            sleep=time.sleep, now=time.time, log=print) -> list:
    records = []
    for i, trial in enumerate(trials):
        record_path = paths.records / f"{trial.job_name}.json"
        if record_path.exists():
            records.append(json.loads(record_path.read_text()))
            continue
        partner = replace(trial, arm="horizon" if trial.arm == "control" else "control")
        reason = skip_reason(paths.records / f"{partner.job_name}.json")
        if reason:
            record = {**_base(trial, freeze), "skipped": reason}
            _write_json(record_path, record)
            records.append(record)
            log(f"{trial.job_name}: skipped, {reason}")
            continue
        usage = None
        if not (paths.jobs / trial.job_name).exists():  # a half-finished job is recorded without waiting
            five_limit, weekly_limit = pace.limits(i % 2)
            usage = wait_for_headroom(probe, five_limit, weekly_limit, sleep=sleep, now=now, log=log)
        log(f"[{i + 1}/{len(trials)}] {trial.job_name}")
        record = run_trial(trial, paths, token, freeze, run=run, now=now, usage=usage)
        records.append(record)
        if not record.get("agent_ran"):
            raise InfrastructureFailure(f"{trial.job_name}: the agent phase never started; fix the "
                                        f"environment, then relaunch")
        if record.get("usage_limit"):
            seconds = wait_seconds(record.get("trial_rate_limit") or {"status": "rejected"}, now(), 0.05, None)
            log(f"{trial.job_name} hit a usage limit; waiting {seconds} s for the reset")
            sleep(seconds)
    return records


def require_freeze(run=subprocess.run) -> str:
    """Return the freeze commit; HEAD may move past it only with the frozen paths unchanged."""
    def git(*args):
        return run(["git", "-C", str(config.REPO_ROOT), *args], capture_output=True, text=True)

    tagged = git("rev-parse", f"{config.FREEZE_TAG}^{{commit}}")
    tag = tagged.stdout.strip() if tagged.returncode == 0 else ""
    if not tag:
        raise NotFrozen(f"tag {config.FREEZE_TAG} is missing")
    if git("merge-base", "--is-ancestor", tag, "HEAD").returncode != 0:
        raise NotFrozen(f"HEAD does not descend from {config.FREEZE_TAG}")
    if git("diff", "--quiet", tag, "HEAD", "--", *FROZEN_PATHS).returncode != 0:
        raise NotFrozen("frozen files changed since the freeze tag")
    dirty = git("status", "--porcelain", "--", *FROZEN_PATHS).stdout.strip()
    if dirty:
        raise NotFrozen(f"frozen files changed:\n{dirty}")
    if git("ls-files", "--error-unmatch", RESULTS).returncode == 0:
        raise NotFrozen("results.jsonl is committed: the measured run is closed")
    return tag


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("setup", "measured"), required=True)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--tasks", help="comma-separated subset, for reruns")
    parser.add_argument("--manifest", type=Path,
                        default=config.REPO_ROOT / "docs/evaluations/tb4-horizon-pilot/manifest.csv")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    paths = Paths(args.runs).ensure()
    only = set(args.tasks.split(",")) if args.tasks else None
    trials = trials_for(draw.read_manifest(args.manifest), args.phase, args.attempt, only)
    if args.dry_run:
        for trial in trials:
            print(" ".join(shlex.quote(x) for x in harbor_command(trial, paths)))
        return 0
    with hold_lock(paths.root / "runner.lock"):
        freeze = require_freeze() if args.phase == "measured" else "pre-freeze"
        token = read_token()
        run_all(trials, paths, token, freeze, probe=lambda: probe_usage(token))
    return 0


if __name__ == "__main__":
    sys.exit(main())
