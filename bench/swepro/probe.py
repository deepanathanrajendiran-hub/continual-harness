"""Check that the agent phase is offline except the model endpoint.

The probe is a copy of the smoke task (excluded from the study) whose oracle solution tries five URLs with
Python (the images have no curl). It must reach only the study's model host (config.ALLOW_HOST).
"""
import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from bench.swepro import config, dataset, jobs

MODEL_URL = f"https://{config.ALLOW_HOST}/v1/models"
ANTHROPIC_URL = "https://api.anthropic.com/v1/models"
BLOCKED_URLS = ("https://api.github.com", "https://raw.githubusercontent.com/ansible/ansible/devel/README.md",
                "https://pypi.org/simple/", "https://www.google.com",
                *(() if MODEL_URL == ANTHROPIC_URL else (ANTHROPIC_URL,)))  # a provider study must not reach Anthropic
PROBE_SCRIPT = """#!/bin/bash
echo "=== NETWORK PROBE (agent phase, python) ==="
PY=$(command -v python3 || command -v python)
"$PY" - <<'PY'
import urllib.request
for u in %s:
    try:
        r = urllib.request.urlopen(u, timeout=8); print("NET", u, "status", r.status)
    except urllib.error.HTTPError as e:
        print("NET", u, "http_error", e.code)
    except Exception as e:
        print("NET", u, "blocked", type(e).__name__, str(e)[:80])
PY
""" % repr([*BLOCKED_URLS, MODEL_URL])


class ProbeFailed(RuntimeError):
    pass


def parse(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "NET":
            out[parts[1]] = parts[2]
    return out


def passed(outcomes: dict) -> bool:
    return (outcomes.get(MODEL_URL) in ("status", "http_error")
            and all(outcomes.get(u) == "blocked" for u in BLOCKED_URLS))


def make_probe_task(src: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    solve = dest / "solution" / "solve.sh"
    solve.parent.mkdir(parents=True, exist_ok=True)
    solve.write_text(PROBE_SCRIPT)
    solve.chmod(0o755)
    return dest


def run_probe(runs: Path, tasks_dir: Path, label: str, *, run=subprocess.run) -> dict:
    probes = runs / "probes"
    probes.mkdir(parents=True, exist_ok=True)
    # count job directories, not records: a probe cut off before its record must not reuse a job name
    n = len(list((runs / "jobs").glob("probe__*"))) + 1
    task = make_probe_task(tasks_dir / config.SMOKE_TASK, runs / "probe-task" / config.SMOKE_TASK)
    image = dataset.docker_image(task)
    jobs.pull_image(image, run=run)
    name = config.job_name("probe", config.SMOKE_TASK, "probe", n)
    read = jobs.run_job(jobs.harbor_command(task, name, runs / "jobs", "oracle", {}, claude=False,
                                            allow_host=True),
                        runs / "jobs" / name, env=jobs.job_env(None), log_path=runs / "logs" / f"{name}.log", run=run)
    text = ""
    if read is not None:
        out = Path(read["trial_dir"]) / "agent" / "oracle.txt"
        text = out.read_text(errors="replace") if out.exists() else ""
    outcomes = parse(text)
    record = {"n": n, "label": label, "job": name, "outcomes": outcomes, "passed": passed(outcomes),
              "at": datetime.now(timezone.utc).isoformat()}
    (probes / f"{n:03d}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    if not record["passed"]:
        raise ProbeFailed(f"network probe {n} ({label}) failed: {outcomes}")
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the agent-phase network probe.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--label", default="manual")
    args = parser.parse_args(argv)
    record = run_probe(args.runs, args.runs / "scale" / "v2" / "tasks", args.label)
    print(json.dumps(record["outcomes"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
