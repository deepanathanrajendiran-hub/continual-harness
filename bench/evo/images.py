"""Build, inspect and remove the arm64 image of an EvoCode task copy (one image per task, shared by its copies)."""
import subprocess
from pathlib import Path

from bench.tb4 import images as tb4_images

PLATFORM = tb4_images.PLATFORM  # linux/arm64


def build_command(copy_dir: Path, tag: str) -> list:
    return ["docker", "build", "--platform", PLATFORM, "-t", tag, str(Path(copy_dir) / "environment")]


def build(copy_dir: Path, tag: str, log, run=subprocess.run) -> None:
    """Build <copy_dir>/environment (the ARM-patched Dockerfile) as `tag`; raises CalledProcessError on failure."""
    run(build_command(copy_dir, tag), check=True, stdout=log, stderr=subprocess.STDOUT, timeout=3600)


def inspect(tag: str, run=subprocess.run) -> dict:
    """{"id", "arch", "workdir", "user"} of a local image (TB4's reader)."""
    return tb4_images.inspect(tag, run)


def remove(tag: str, run=subprocess.run) -> None:
    run(["docker", "image", "rm", "-f", tag], capture_output=True, text=True)
