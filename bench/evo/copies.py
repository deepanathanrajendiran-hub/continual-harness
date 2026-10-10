"""Agent and validation copies of an EvoCode task: arm64 Dockerfile with python3 for the Horizon CLI when the
image lacks it (both arms), per-round hooks, step verifier timeouts, an optional pinned image, and no
reference solutions in agent copies. Also the prompt files.

Harbor 0.24.0 facts these hooks rely on (harbor/trial/multi_step.py, harbor/trial/trial.py):
- Before each agent phase, Harbor uploads steps/<name>/workdir/. into the container's working directory
  and runs `bash <workdir>/setup.sh` there as the step's agent user. A non-zero exit fails the step and
  ends the trial, so SETUP_SH always exits 0.
- After each agent phase (also after a timeout or an agent error) and before the verifier, Harbor runs the
  task's [[verifier.collect]] hooks and then the step's [[steps.verifier.collect]] hooks in the main
  service with `bash -c`, in the same working directory. Failures are logged and never stop the trial.
- A step's verifier timeout is [steps.verifier].timeout_sec, which defaults to 600 s; the task-level
  [verifier].timeout_sec is never consulted for a step.
- Files written under /logs/artifacts during a step end up in the trial's steps/<name>/artifacts/logs/artifacts/
  (bind mount at <trial>/artifacts/logs/artifacts, moved after each step).

The env variables EVO_TMP_ROOT, EVO_PROC_ROOT and EVO_ARTIFACTS_ROOT exist only so tests can run the
hooks on a Mac sandbox; Harbor never sets them, so the defaults /tmp, /proc and /logs/artifacts apply.
"""
import datetime
import json
import os
import re
import shlex
import shutil
import tomllib
from pathlib import Path

from bench.evo import config, patch
from bench.tb4.copies import tree_digest

KINDS = ("agent", "validation")
HARBOR_VERIFIER_TIMEOUT_DEFAULT = 600.0
COLLECT_TIMEOUT_SEC = 60.0
COLLECT_USER = "root"
HARNESS_COPY = "harness"
KILLED_FILE = "killed.txt"
TMP_LISTING_FILE = "tmp-ls.txt"
PROJECT_FILES_FILE = "project-files.txt"
SURVIVORS_FILE = "survivors.txt"
ARM_PATCH_FILE = "arm-patch.json"  # the patch record, at the top of each copy

# Appended to every copy's Dockerfile after the ARM patch, for both arms; it does nothing when the image has python3.
PYTHON_LINE = ("RUN command -v python3 >/dev/null 2>&1 || (apt-get update && DEBIAN_FRONTEND=noninteractive apt-get "
               "install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*)")
PYTHON_BLOCK = ("\n# evo: python3 for the Horizon CLI, added to both arms when the image lacks it "
                f"(bench/evo/copies.py)\n{PYTHON_LINE}\n")

SETUP_SH = """#!/bin/bash
# EvoCode first look: per-round reset (bench/evo/copies.py). Harbor runs this as the step's agent user
# from the agent working directory before every agent phase. It empties /tmp and Claude's per-project
# session memory, never touches the project, deletes itself last, and always exits 0.
shopt -s dotglob nullglob
tmp_root="${EVO_TMP_ROOT:-/tmp}"
here="$(pwd -P)"
tmp_real="$(cd "$tmp_root" 2>/dev/null && pwd -P)"
if [ -n "$tmp_real" ] && [ "$here" != "$tmp_real" ]; then
  for entry in "$tmp_real"/*; do
    case "$here/" in
      "$entry"/*) continue ;;
    esac
    rm -rf -- "$entry" 2>/dev/null
  done
fi
rm -rf -- "${HOME:-/root}/.claude/projects" 2>/dev/null
rm -f -- "$0"
exit 0
"""

_COLLECT_TEMPLATE = r"""# evo-collect-hook (bench/evo/copies.py)
set +e
out="${EVO_ARTIFACTS_ROOT:-/logs/artifacts}"/__ROUND__
proc="${EVO_PROC_ROOT:-/proc}"
mkdir -p "$out"
evo_tree() {
  roots=" " pairs=""
  for d in "$proc"/[0-9]*; do
    pid=${d##*/}
    [ "$pid" = "$$" ] && continue
    ppid=""
    while read -r key val rest; do
      if [ "$key" = "PPid:" ]; then ppid=$val; break; fi
    done 2>/dev/null < "$d/status"
    [ -n "$ppid" ] || continue
    pairs="$pairs $pid:$ppid"
    arg0=""
    IFS= read -r -d '' arg0 2>/dev/null < "$d/cmdline"
    exe=$(readlink "$d/exe" 2>/dev/null)
    case "${arg0##*/}|$exe" in
      "claude|"*|*/claude|*/claude/versions/*) roots="$roots$pid " ;;
    esac
  done
  tree=$roots grown=1
  while [ "$grown" = 1 ]; do
    grown=0
    for pair in $pairs; do
      case "$tree" in
        *" ${pair#*:} "*)
          case "$tree" in
            *" ${pair%%:*} "*) ;;
            *) tree="$tree${pair%%:*} " grown=1 ;;
          esac ;;
      esac
    done
  done
  echo $tree
}
all=" " pass=0
while [ "$pass" -lt 5 ]; do
  pass=$((pass + 1))
  new=""
  for pid in $(evo_tree); do
    case "$all" in *" $pid "*) ;; *) new="$new $pid" ;; esac
  done
  [ -n "$new" ] || break
  kill -STOP $new 2>/dev/null
  all="$all${new# } "
done
: > "$out/killed.txt"
for pid in $all; do
  printf '%s %s\n' "$pid" "$(tr '\0' ' ' 2>/dev/null < "$proc/$pid/cmdline" | cut -c1-200)" >> "$out/killed.txt"
done
[ "$all" = " " ] || kill -KILL $all 2>/dev/null
if [ -d "$PWD/.claude/harness" ]; then
  cp -R "$PWD/.claude/harness" "$out/harness"
fi
ls -la "${EVO_TMP_ROOT:-/tmp}" > "$out/tmp-ls.txt" 2>&1
find . \( -name .git -prune \) -o \( -type f -o -type l \) -print 2>/dev/null | LC_ALL=C sort > "$out/project-files.txt"
: > "$out/survivors.txt"
for d in "$proc"/[0-9]*; do
  pid=${d##*/}
  case "$pid" in "$$"|1) continue ;; esac
  case "$all" in *" $pid "*) continue ;; esac
  args=$(tr '\0\n' '  ' 2>/dev/null < "$d/cmdline" | cut -c1-200)
  args=${args% }
  case "$args" in ""|*evo-collect-hook*) continue ;; esac
  printf '%s %s\n' "$pid" "$args" >> "$out/survivors.txt"
done
chmod -R a+rwX "$out" 2>/dev/null
exit 0
"""

_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")
_ESCAPES = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r"}


def _check_step_name(name: str) -> str:
    if not name or name in (".", "..") or any(ch in name for ch in "/\\\0"):
        raise ValueError(f"step name {name!r} is not a single directory name")
    return name


def COLLECT_COMMAND(round_name: str) -> str:
    """The collect hook for one round: stop every claude process and its descendants, then snapshot the
    Horizon ledger, a /tmp listing and the project file list into /logs/artifacts/<round>/. Exits 0."""
    return _COLLECT_TEMPLATE.replace("__ROUND__", shlex.quote(_check_step_name(round_name)))


def _toml_string(text: str) -> str:
    out = []
    for ch in text:
        if ch in _ESCAPES:
            out.append(_ESCAPES[ch])
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _toml_key(key: str) -> str:
    return key if _BARE_KEY.fullmatch(key) else _toml_string(key)


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_toml_key(k)} = {_toml_value(v)}" for k, v in value.items()) + "}"
    raise ValueError(f"cannot write TOML value {value!r}")


def _is_table_array(value) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, dict) for item in value)


def _emit_table(lines: list, path: tuple, table: dict) -> None:
    for key, value in table.items():
        if not isinstance(value, dict) and not _is_table_array(value):
            lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    for key, value in table.items():
        sub = path + (key,)
        name = ".".join(_toml_key(part) for part in sub)
        if isinstance(value, dict):
            lines += ["", f"[{name}]"]
            _emit_table(lines, sub, value)
        elif _is_table_array(value):
            for item in value:
                lines += ["", f"[[{name}]]"]
                _emit_table(lines, sub, item)


def dump_toml(data: dict) -> str:
    """Write a parsed TOML document back out in a fixed order; raise unless it parses back to `data`."""
    lines = []
    _emit_table(lines, (), data)
    text = "\n".join(lines).lstrip("\n") + "\n"
    if tomllib.loads(text) != data:
        raise ValueError("TOML rewrite did not round-trip")
    return text


def _refuse_separate_verifier(data: dict) -> None:
    verifiers = [("[verifier]", data.get("verifier", {}))]
    verifiers += [(f"step {s.get('name')!r}", s.get("verifier", {})) for s in data["steps"]]
    for where, verifier in verifiers:
        if "environment" in verifier or verifier.get("environment_mode") == "separate":
            raise ValueError(f"{where}: a separate verifier environment is not supported by the copies")


def step_toml_overrides(task_toml_text: str, verifier_timeout_sec: float, *, docker_image: str | None = None) -> str:
    """Give every [[steps]] entry a verifier timeout (unless it sets its own) and the collect hook, first in
    its hook list; pin [environment].docker_image when given. Every other key is kept."""
    data = tomllib.loads(task_toml_text)
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("task.toml has no [[steps]]")
    _refuse_separate_verifier(data)
    for step in steps:
        verifier = step.setdefault("verifier", {})
        verifier.setdefault("timeout_sec", float(verifier_timeout_sec))
        hook = {"command": COLLECT_COMMAND(step["name"]), "timeout_sec": COLLECT_TIMEOUT_SEC, "user": COLLECT_USER}
        verifier["collect"] = [hook, *verifier.get("collect", [])]
    if docker_image is not None:
        environment = data.setdefault("environment", {})
        if "docker_image" in environment:
            raise ValueError("task already sets [environment].docker_image")
        environment["docker_image"] = docker_image
    return dump_toml(data)


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _fill_copy(dest: Path, kind: str, image_tag: str | None) -> None:
    dockerfile = dest / "environment" / "Dockerfile"
    text, artifacts = patch.replace_bundled_go(dest / "environment", dockerfile.read_text())
    patched, changed = patch.arm_patch(text)
    dockerfile.write_text(patched + PYTHON_BLOCK)
    record = {"changed": changed, "artifacts": artifacts, "added": [PYTHON_LINE]}
    (dest / ARM_PATCH_FILE).write_text(json.dumps(record, indent=2) + "\n")
    toml_path = dest / "task.toml"
    text = toml_path.read_text()
    data = tomllib.loads(text)
    for step in data.get("steps") or []:
        step_dir = dest / "steps" / _check_step_name(step["name"])
        if not step_dir.is_dir():
            raise FileNotFoundError(step_dir)
        setup = step_dir / "workdir" / "setup.sh"
        if setup.exists() or setup.is_symlink():
            raise ValueError(f"{setup}: the task already ships a setup.sh")
        setup.parent.mkdir(exist_ok=True)
        setup.write_text(SETUP_SH)
        setup.chmod(0o755)
    timeout = data.get("verifier", {}).get("timeout_sec", HARBOR_VERIFIER_TIMEOUT_DEFAULT)
    toml_path.write_text(step_toml_overrides(text, timeout, docker_image=image_tag))
    if kind == "agent":
        _remove(dest / "solution")
        for step_dir in sorted((dest / "steps").iterdir()):
            _remove(step_dir / "solution")


def _refuse_symlinks_leaving(task_dir: Path) -> None:
    """Raise ValueError naming the first symlink under task_dir that is absolute or, resolved lexically from its
    own directory, leaves task_dir. Links are never followed and no file is opened."""
    root = os.path.abspath(task_dir)
    for parent, dirnames, filenames in os.walk(task_dir, followlinks=False):
        for name in sorted(dirnames + filenames):
            path = os.path.join(parent, name)
            if not os.path.islink(path):
                continue
            target = os.readlink(path)
            landing = os.path.normpath(os.path.join(os.path.abspath(parent), target))
            if os.path.isabs(target) or os.path.commonpath([root, landing]) != root:
                where = os.path.relpath(path, task_dir)
                raise ValueError(f"{where}: a symlink that leaves the task directory is not supported by the copies")


def make_copy(src_task_dir: Path, dest_dir: Path, *, kind: str, image_tag: str | None) -> str:
    """Copy a task, then patch, hook, time and pin the copy; agent copies lose every solution. The copy's
    Dockerfile gets the ARM patch and then PYTHON_BLOCK, which installs python3 for the Horizon CLI when the image
    lacks it; arm-patch.json records the patched lines as `changed`, the swapped Go archives as `artifacts` and the
    appended RUN line as `added`. The source is only read: a task holding an absolute symlink, or one that leaves
    the task directory, is refused with ValueError before anything is copied, because the copy's edits would follow
    the link back into the source. Returns the copy's tree digest; on any error the partial copy is removed."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, not {kind!r}")
    src_task_dir, dest_dir = Path(src_task_dir), Path(dest_dir)
    if dest_dir.exists():
        raise FileExistsError(dest_dir)
    _refuse_symlinks_leaving(src_task_dir)
    shutil.copytree(src_task_dir, dest_dir, symlinks=True)
    try:
        _fill_copy(dest_dir, kind, image_tag)
    except BaseException:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise
    return tree_digest(dest_dir)


def write_prompt(dest: Path, arm: str, minutes: int) -> Path:
    """Write the extra-instruction file Harbor appends to every round's instruction for this arm."""
    if arm not in config.ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(config.prompt_text(arm, minutes) + "\n")
    return dest
