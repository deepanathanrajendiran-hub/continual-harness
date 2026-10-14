"""One Harbor job per run: build the command, run it, read the single trial it leaves, classify it.

Reads only result.json, the agent's own logs and the verifier's reward. Never prints verifier output.
"""
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from bench.evo.run import API_EXCEPTIONS, MODEL_OUTCOMES
from bench.swepro import config
from bench.tb4 import stream
from bench.tb4.run import STRIP_ENV, USAGE_EXCEPTIONS

ARM_AGENT = "bench.swepro.agent:ArmClaudeCode"
REFINE_AGENT = "bench.swepro.agent:RefineClaudeCode"
REPLAY_AGENT = "patch_replay:PatchReplayAgent"
RESULT_EXCEPTIONS = (*MODEL_OUTCOMES, "NonZeroAgentExitCodeError")  # the model's outcome, not a rerun
INPUT_FIELDS = ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")
AUDIT = re.compile(r"(?<![\w.-])/(?:tests|solution|logs/verifier)(?![\w.-])")


class JobError(RuntimeError):
    pass


def harbor_command(task_dir: Path, job: str, jobs_dir: Path, agent: str, kwargs: dict, *, claude: bool,
                   model: str | None = None, allow_host: bool | None = None) -> list:
    """`allow_host` (default: same as `claude`) opens the model endpoint during the offline agent phase."""
    cmd = ["harbor", "run", "-p", str(task_dir), "-a", agent]
    if claude:
        cmd += ["-m", config.MODEL, "--effort", config.EFFORT,
                "--ak", f"version={config.CLAUDE_CODE_VERSION}", "--ak", "disable_web_search=true",
                "--ae", "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}",
                "--ae", f"CLAUDE_CODE_MAX_OUTPUT_TOKENS={config.MAX_OUTPUT_TOKENS}"]
    elif model:
        cmd += ["-m", model]
    if claude if allow_host is None else allow_host:
        cmd += ["--allow-agent-host", config.ALLOW_HOST]
    for key, value in sorted(kwargs.items()):
        cmd += ["--ak", f"{key}={value}"]
    return cmd + ["-n", "1", "-k", "1", "-r", "0", "-o", str(jobs_dir), "--job-name", job, "-y"]


def job_env(token: str | None, base=None, extra_path=()) -> dict:
    env = {k: v for k, v in (os.environ if base is None else base).items() if k not in STRIP_ENV}
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    env["PYTHONPATH"] = ":".join([str(config.REPO_ROOT), *map(str, extra_path)])
    return env


def _trial_dir(job_dir: Path):
    found = sorted(job_dir.glob("*/result.json")) if job_dir.is_dir() else []
    return found[0].parent if len(found) == 1 else None


def _seconds(phase) -> float | None:
    if not phase or not phase.get("started_at") or not phase.get("finished_at"):
        return None
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
    return (parse(phase["finished_at"]) - parse(phase["started_at"])).total_seconds()


def _json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def read_trial(job_dir: Path):
    """The job's one trial as a flat dict, or None when Harbor left no single result.json."""
    trial = _trial_dir(job_dir)
    if trial is None:
        return None
    result = json.loads((trial / "result.json").read_text())
    exception = (result.get("exception_info") or {}).get("exception_type")
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    agent = trial / "agent"
    events = stream.read_events(agent / "claude-code.txt")
    final = None if exception == "AgentTimeoutError" else stream.final_result(events)
    usage = (final or {}).get("modelUsage") or {}
    init = stream.init_info(events)
    tool_text = " ".join(str(v) for _, b in stream.tool_uses(events) for v in (b.get("input") or {}).values())
    patch = agent / "model.patch"
    return {
        "trial_dir": str(trial),
        "task_name": str(result.get("task_name") or "").split("/")[-1],
        "reward": rewards.get("reward"),
        "exception": exception,
        "cost_usd": (final or {}).get("total_cost_usd"),
        "tokens_in": sum(int(m.get(k) or 0) for m in usage.values() for k in INPUT_FIELDS) if final else None,
        "tokens_out": sum(int(m.get("outputTokens") or 0) for m in usage.values()) if final else None,
        "claude_version": init.get("version"),
        "model": init.get("model"),
        "agent_sec": _seconds(result.get("agent_execution")),
        "verifier_sec": _seconds(result.get("verifier")),
        "notes": _json(agent / "notes.json"),
        "patch_bytes": patch.stat().st_size if patch.exists() else None,
        "audit_tests": bool(AUDIT.search(tool_text)),
        "usage_evidence": bool(stream.usage_limit_evidence(events)),
        "api_error": bool(stream.terminal_api_error(events)) and exception not in RESULT_EXCEPTIONS,
    }


def classify(read) -> str | None:
    """None for a valid run; otherwise why it must be rerun."""
    if read is None:
        return "infrastructure"
    exception = read["exception"]
    if exception == "CancelledError":
        return "interrupted"
    if exception in USAGE_EXCEPTIONS or read["usage_evidence"]:
        return "usage_limit"
    if exception in API_EXCEPTIONS or read["api_error"]:
        return "api_error"
    if exception and exception not in RESULT_EXCEPTIONS:
        return "infrastructure"
    return None


def run_job(cmd: list, job_dir: Path, *, env: dict, log_path: Path, run=subprocess.run, fresh: bool = True):
    if fresh and job_dir.exists():
        raise JobError(f"{job_dir} exists; a job directory is never reused")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as log:
        run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, text=True)
    return read_trial(job_dir)


def pull_image(image: str, run=subprocess.run) -> None:
    proc = run(["docker", "pull", "-q", "--platform", "linux/amd64", image], capture_output=True, text=True)
    if proc.returncode != 0:
        raise JobError(f"docker pull {image} failed: {(proc.stderr or '')[-300:]}")


def remove_image(image: str, run=subprocess.run) -> None:
    run(["docker", "image", "rm", image], capture_output=True, text=True)


def run_with_reruns(job: str, make_cmd, *, jobs_dir: Path, logs_dir: Path, env: dict, run=subprocess.run,
                    before_rerun=lambda reason: None, reruns: int = config.INFRA_RERUNS):
    """Run `job`; rerun it as `{job}-rerun{k}` while the result is invalid, at most `reruns` times.

    A job directory left by an earlier process (killed before its record was written) counts as that
    try: it is read, not run again, and a valid one is kept.

    Returns (read, tries): the last try's read_trial result (None if Harbor left none) and one
    {"job", "reason"} per try, where reason is classify()'s verdict (None for the valid one)."""
    tries = []
    for k in range(reruns + 1):
        name = job if k == 0 else f"{job}-rerun{k}"
        if (jobs_dir / name).exists():
            read = read_trial(jobs_dir / name)
        else:
            read = run_job(make_cmd(name), jobs_dir / name, env=env, log_path=logs_dir / f"{name}.log", run=run)
        reason = classify(read)
        tries.append({"job": name, "reason": reason})
        if reason is None:
            break
        if k < reruns:
            before_rerun(reason)
    return read, tries
