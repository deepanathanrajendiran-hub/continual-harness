"""Build, inspect, and smoke-test the locally pinned agent and verifier images."""
import json
import subprocess
from pathlib import Path

from bench.tb4 import config

PLATFORM = "linux/arm64"
PYTHON_PROBE = ('python3 -c "import sys; assert sys.version_info >= (3, 10), sys.version; '
                'print(sys.version.split()[0])"')
BUNDLE_PROBE = r'''set -eu
P="$(mktemp -d)"
H=/opt/horizon/scripts/harness.py
python3 "$H" --runtime claude --project "$P" doctor >/dev/null
python3 "$H" --runtime claude --project "$P" start smoke --gate true --max-turns 3 --max-minutes 5 > "$P.start.json"
S="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["slug"])' "$P.start.json")"
python3 "$H" --runtime claude --project "$P" check "$S" --did smoke --next none >/dev/null
python3 "$H" --runtime claude --project "$P" status "$S" >/dev/null
test -f "$P/.claude/harness/goals/$S.json"
echo ok
'''


def build_commands(task_dir: Path, task: str) -> list:
    return [
        ["docker", "build", "--platform", PLATFORM, "-t", config.agent_tag(task), str(task_dir / "environment")],
        ["docker", "build", "--platform", PLATFORM, "-t", config.verifier_tag(task), str(task_dir / "tests")],
    ]


def build(task_dir: Path, task: str, log, run=subprocess.run) -> None:
    for cmd in build_commands(task_dir, task):
        run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=3600)


def inspect(tag: str, run=subprocess.run) -> dict:
    out = run(["docker", "image", "inspect", tag], check=True, capture_output=True, text=True).stdout
    data = json.loads(out)[0]
    cfg = data.get("Config") or {}
    return {"id": data["Id"], "arch": data.get("Architecture"),
            "workdir": cfg.get("WorkingDir") or "/", "user": cfg.get("User") or "root"}


def _run_in_image(tag: str, script: str, mounts=(), run=subprocess.run):
    cmd = ["docker", "run", "--rm", "--platform", PLATFORM, "--network", "none", "--entrypoint", "sh"]
    for host, container in mounts:
        cmd += ["-v", f"{host}:{container}:ro"]
    cmd += [tag, "-c", script]
    proc = run(cmd, capture_output=True, text=True, timeout=600)
    return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")


def python_ok(tag: str, run=subprocess.run):
    return _run_in_image(tag, PYTHON_PROBE, run=run)


def bundle_ok(tag: str, skill_dir: Path, run=subprocess.run):
    return _run_in_image(tag, BUNDLE_PROBE, mounts=[(str(skill_dir), "/opt/horizon")], run=run)
