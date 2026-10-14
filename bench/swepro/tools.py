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


def write_manifest(tools_dir: Path = TOOLS) -> dict:
    manifest = {rel: sha256_file(tools_dir / rel) for rel in (CLAUDE_REL, LOADER_REL, "patch_replay.py")}
    (tools_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch the arm64 Claude Code build and musl loader.")
    parser.add_argument("--tools", type=Path, default=TOOLS)
    args = parser.parse_args(argv)
    fetch_claude(args.tools)
    fetch_loader(args.tools)
    print(json.dumps(write_manifest(args.tools), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
