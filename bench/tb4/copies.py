"""Make the pinned task copy that both arms share, and the check-only copy for reference check 3."""
import hashlib
import json
import os
import re
import shlex
import shutil
import tomllib
from pathlib import Path

from bench.tb4 import config

_ENV_HEADER = re.compile(r"^\[environment\][ \t]*$", re.M)
_VERIFIER_ENV_HEADER = re.compile(r"^\[verifier\.environment\][ \t]*$", re.M)
WRAPPER = """#!/bin/bash
# Reference check 3: plant a representative Horizon ledger as the agent user, then run the real solution.
set -euo pipefail
mkdir -p {target}
cp -R /solution/horizon-ledger/. {target}/
exec bash /solution/solve.orig.sh "$@"
"""


def tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix().encode()
        if path.is_symlink():
            h.update(b"L" + rel + b"\0" + os.readlink(path).encode() + b"\0")
        elif path.is_file():
            h.update(b"F" + rel + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list) and all(isinstance(v, (bool, int, float, str)) for v in value):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise ValueError(f"cannot copy TOML value {value!r}")


def _insert_after(pattern, text: str, line: str, what: str) -> str:
    if len(pattern.findall(text)) != 1:
        raise ValueError(f"expected exactly one {what} header")
    return pattern.sub(lambda m: m.group(0) + "\n" + line, text, count=1)


def pin_toml(text: str, agent_tag: str, verifier_tag: str) -> str:
    data = tomllib.loads(text)
    env = data.get("environment")
    if env is None:
        raise ValueError("task.toml has no [environment] table")
    if "docker_image" in env:
        raise ValueError("task already sets [environment].docker_image")
    copied = []
    verifier = data.get("verifier", {})
    if "environment" not in verifier:
        for key, value in env.items():
            if isinstance(value, dict):
                if value:
                    raise ValueError(f"cannot copy non-empty table environment.{key}")
                continue
            copied.append(f"{key} = {_toml_value(value)}")
    text = _insert_after(_ENV_HEADER, text, f'docker_image = "{agent_tag}"', "[environment]")
    if "environment" in verifier:
        if "docker_image" in verifier["environment"]:
            raise ValueError("task already sets [verifier.environment].docker_image")
        text = _insert_after(_VERIFIER_ENV_HEADER, text, f'docker_image = "{verifier_tag}"',
                             "[verifier.environment]")
    else:
        block = ["", "[verifier.environment]", *copied, f'docker_image = "{verifier_tag}"']
        text = text.rstrip("\n") + "\n" + "\n".join(block) + "\n"
    pinned = tomllib.loads(text)
    if pinned["environment"].get("docker_image") != agent_tag:
        raise ValueError("agent image pin did not take effect")
    if pinned["verifier"]["environment"].get("docker_image") != verifier_tag:
        raise ValueError("verifier image pin did not take effect")
    return text


def pin_task(src: Path, dest: Path, task: str) -> str:
    if dest.exists():
        raise FileExistsError(dest)
    shutil.copytree(src, dest, symlinks=True)
    toml_path = dest / "task.toml"
    toml_path.write_text(pin_toml(toml_path.read_text(), config.agent_tag(task), config.verifier_tag(task)))
    instruction = dest / "instruction.md"
    body = instruction.read_text()
    found = body.count(config.DEADLINE_SENTENCE)
    if found != 1:
        shutil.rmtree(dest)
        raise ValueError(f"{task}: deadline sentence found {found} times, expected 1")
    instruction.write_text(body.replace(config.DEADLINE_SENTENCE, "", 1))
    return tree_digest(dest)


def ledger_check_copy(pinned: Path, dest: Path, workdir: str, ledger_src: Path) -> str:
    if dest.exists():
        raise FileExistsError(dest)
    shutil.copytree(pinned, dest, symlinks=True)
    solution = dest / "solution"
    solve = solution / "solve.sh"
    if not solve.is_file():
        raise FileNotFoundError(solve)
    solve.rename(solution / "solve.orig.sh")
    shutil.copytree(ledger_src, solution / "horizon-ledger")
    target = shlex.quote(workdir.rstrip("/") + "/.claude/harness")
    solve.write_text(WRAPPER.format(target=target))
    solve.chmod(0o755)
    return tree_digest(dest)
