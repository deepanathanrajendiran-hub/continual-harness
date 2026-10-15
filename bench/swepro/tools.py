"""The files every container needs: the arm64-musl Claude Code build and Alpine's musl loader.

The SWE-bench Pro images are linux/amd64. Under Rosetta the x64 Claude Code build refuses to start
("CPU lacks AVX support"). The Colima VM is arm64, so the arm64 build runs natively inside the amd64
container once its loader is at /lib/ld-musl-aarch64.so.1.
"""
import argparse
import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

from bench.swepro import config

CLAUDE_REL = "claude-arm64-musl/claude"
LOADER_REL = "musl/ld-musl-aarch64.so.1"
MINI_PYTHON_REL = "mini/python.tgz"
MINI_REL = "mini/mswea.tgz"  # /opt/mswea: standalone Python with mini-swe-agent and LiteLLM installed
MINI_YAML_REL = "mini/mini.yaml"  # mini-swe-agent's packaged default config, read on the host
MINI_FREEZE_REL = "mini/freeze.txt"
MINI_BUILD = (
    "set -e; tar -xzf /w/python.tgz -C /opt && mv /opt/python /opt/mswea && "
    "pip install -q uv=={uv} && "
    "uv pip install -q --python /opt/mswea/bin/python3 --exclude-newer {newer} mini-swe-agent=={mini} litellm orjson && "
    "cp /opt/mswea/lib/python3.12/site-packages/minisweagent/config/mini.yaml /w/mini.yaml && "
    "uv pip freeze --python /opt/mswea/bin/python3 > /w/freeze.txt && "
    "tar czf /w/mswea.tgz -C /opt mswea"
)
TOOLS = config.RUNS / "tools"


class ToolError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _urlretrieve(url: str, dest: Path) -> None:
    urllib.request.urlretrieve(url, dest)  # noqa: S310 - pinned https URL, checked by sha256 below


def fetch_claude(tools_dir: Path = TOOLS, *, download=_urlretrieve) -> Path:
    out = tools_dir / CLAUDE_REL
    if out.exists() and sha256_file(out) == config.CLAUDE_ARM_SHA256:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    download(config.CLAUDE_ARM_URL, out)
    digest = sha256_file(out)
    if digest != config.CLAUDE_ARM_SHA256:
        out.unlink()
        raise ToolError(f"claude sha256 {digest} != pinned {config.CLAUDE_ARM_SHA256}")
    out.chmod(0o755)
    return out


def fetch_loader(tools_dir: Path = TOOLS, *, run=subprocess.run) -> Path:
    out = tools_dir / LOADER_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = run(["docker", "run", "--rm", "--platform", "linux/arm64", "-v", f"{out.parent}:/o",
                config.ALPINE_IMAGE, "cp", "-L", "/lib/ld-musl-aarch64.so.1", "/o/"],
               capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise ToolError(f"could not copy the musl loader: {(proc.stderr or '')[-300:]}")
    out.chmod(0o755)
    return out


def build_mini(tools_dir: Path = TOOLS, *, download=_urlretrieve, run=subprocess.run) -> Path:
    """Pre-build mini-swe-agent for the offline agent phase: the pinned standalone Python (checked by
    sha256) with pinned packages, built in an amd64 container that has network, packed as one tarball."""
    out = tools_dir / MINI_REL
    if out.exists() and (tools_dir / MINI_YAML_REL).exists():
        return out
    python = tools_dir / MINI_PYTHON_REL
    python.parent.mkdir(parents=True, exist_ok=True)
    if not (python.exists() and sha256_file(python) == config.MINI_PYTHON_SHA256):
        download(config.MINI_PYTHON_URL, python)
        digest = sha256_file(python)
        if digest != config.MINI_PYTHON_SHA256:
            python.unlink()
            raise ToolError(f"python sha256 {digest} != pinned {config.MINI_PYTHON_SHA256}")
    script = MINI_BUILD.format(uv=config.MINI_UV_VERSION, newer=config.MINI_EXCLUDE_NEWER, mini=config.MINI_VERSION)
    proc = run(["docker", "run", "--rm", "--platform", "linux/amd64", "-v", f"{python.parent}:/w",
                config.REFINE_BASE_IMAGE, "sh", "-c", script], capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists() or not (tools_dir / MINI_YAML_REL).exists():
        raise ToolError(f"could not build mini-swe-agent: {(proc.stderr or '')[-300:]}")
    return out


def write_manifest(tools_dir: Path = TOOLS) -> dict:
    mini = [rel for rel in (MINI_PYTHON_REL, MINI_REL, MINI_YAML_REL, MINI_FREEZE_REL) if (tools_dir / rel).exists()]
    manifest = {rel: sha256_file(tools_dir / rel) for rel in (CLAUDE_REL, LOADER_REL, "patch_replay.py", *mini)}
    (tools_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch the arm64 Claude Code build and musl loader.")
    parser.add_argument("--tools", type=Path, default=TOOLS)
    parser.add_argument("--mini", action="store_true", help="also pre-build mini-swe-agent")
    args = parser.parse_args(argv)
    fetch_claude(args.tools)
    fetch_loader(args.tools)
    if args.mini:
        build_mini(args.tools)
    print(json.dumps(write_manifest(args.tools), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
