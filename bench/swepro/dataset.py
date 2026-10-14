"""Fetch SWE-bench Pro v2 at the pinned commit and list the study repository's tasks.

Reads only task.toml. Never opens a task's tests/, solution/ or instruction.md.
"""
import argparse
import hashlib
import shutil
import subprocess
import tomllib
from pathlib import Path

from bench.swepro import config


class DatasetError(RuntimeError):
    pass


def _git(repo: Path, *args, run=subprocess.run) -> str:
    proc = run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise DatasetError(f"git {' '.join(args)} failed: {(proc.stderr or '')[-300:]}")
    return proc.stdout or ""


def fetch(dest: Path = config.RUNS / "scale", *, run=subprocess.run) -> Path:
    """Sparse-clone v2/ at SCALE_COMMIT (or reuse a clone already there) and return v2/tasks."""
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        proc = run(["git", "clone", "--filter=blob:none", "--no-checkout", config.SCALE_URL, str(dest)],
                   capture_output=True, text=True)
        if proc.returncode != 0:
            raise DatasetError(f"clone failed: {(proc.stderr or '')[-300:]}")
        _git(dest, "sparse-checkout", "set", "v2", run=run)
        _git(dest, "checkout", config.SCALE_COMMIT, run=run)
    head = _git(dest, "rev-parse", "HEAD", run=run).strip()
    if head != config.SCALE_COMMIT:
        raise DatasetError(f"{dest} is at commit {head}, not {config.SCALE_COMMIT}")
    return dest / "v2" / "tasks"


def repo_tasks(tasks_dir: Path) -> list:
    """The study repository's tasks (config.REPO_PREFIX), sorted."""
    return sorted(p.name for p in tasks_dir.iterdir()
                  if p.name.startswith(config.REPO_PREFIX) and (p / "task.toml").is_file())


def study_pool(tasks_dir: Path) -> list:
    """The repository's tasks minus config.EXCLUDED, which must all be present."""
    names = repo_tasks(tasks_dir)
    missing = [t for t in config.EXCLUDED if t not in names]
    if missing:
        raise DatasetError(f"excluded tasks not in the tree: {missing}")
    return [t for t in names if t not in config.EXCLUDED]


def docker_image(task_dir: Path) -> str:
    data = tomllib.loads((task_dir / "task.toml").read_text())
    image = (data.get("environment") or {}).get("docker_image")
    if not image:
        raise DatasetError(f"{task_dir.name}: task.toml names no docker_image")
    return image


def install_replay(scale_repo: Path, tools_dir: Path) -> Path:
    """Copy Scale's patch_replay.py into tools/ after checking it against the pinned sha256."""
    src = scale_repo / "v2" / "tooling" / "patch_replay.py"
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    if digest != config.REPLAY_SHA256:
        raise DatasetError(f"patch_replay.py sha256 {digest} != pinned {config.REPLAY_SHA256}")
    tools_dir.mkdir(parents=True, exist_ok=True)
    out = tools_dir / "patch_replay.py"
    shutil.copyfile(src, out)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch SWE-bench Pro v2 and list the study pool.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    args = parser.parse_args(argv)
    tasks = fetch(args.runs / "scale")
    install_replay(args.runs / "scale", args.runs / "tools")
    pool = study_pool(tasks)
    print(f"{len(repo_tasks(tasks))} {config.REPO_LABEL} tasks; {len(pool)} in the study pool")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
