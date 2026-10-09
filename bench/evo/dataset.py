"""Fetch, verify and extract the pinned EvoCode-Bench archive; list tasks from task.toml only.

Contamination rule: nothing in this module opens, lists or prints anything under a task's steps/.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

from bench.evo import config

HF = "https://huggingface.co"
USER_AGENT = "evocode-horizon-first-look"
HARBOR_VERIFIER_DEFAULT_SEC = 600.0  # harbor 0.24.0 models/task/config.py VerifierConfig.timeout_sec


class DatasetMismatch(Exception):
    """The archive, the API answer or an existing extraction is not the pinned dataset."""


def archive_url(revision: str) -> str:
    return f"{HF}/datasets/{config.DATASET_REPO}/resolve/{revision}/{config.ARCHIVE_PATH}"


def urlopen_json(url: str, data=None):
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def download_file(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response, open(dest, "wb") as out:
        shutil.copyfileobj(response, out, 1 << 20)


def lfs_oid(revision: str, *, fetch=urlopen_json) -> str:
    """The archive's LFS oid (its sha256) as the HF paths-info API reports it at `revision`."""
    url = f"{HF}/api/datasets/{config.DATASET_REPO}/paths-info/{revision}"
    entries = fetch(url, urllib.parse.urlencode({"paths": config.ARCHIVE_PATH}).encode())
    for entry in entries:
        if entry.get("path") == config.ARCHIVE_PATH:
            oid = (entry.get("lfs") or {}).get("oid")
            if not oid:
                raise DatasetMismatch(f"{config.ARCHIVE_PATH} at {revision} is not an LFS file")
            return oid
    raise DatasetMismatch(f"{config.ARCHIVE_PATH} not found at {revision}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def extract(archive: Path, dest: Path, run=subprocess.run) -> None:
    dest.mkdir(parents=True)
    run(["bash", "-o", "pipefail", "-c", 'zstd -d -q -c -- "$0" | tar -x -f - -C "$1"',
         str(archive), str(dest)], check=True)


def _task_children(directory: Path) -> list:
    return sorted(c for c in directory.iterdir() if c.is_dir() and (c / "task.toml").is_file())


def tasks_parent(root: Path, depth: int = 3) -> Path:
    """The one shallowest directory whose children hold task.toml; never enters a task directory."""
    level = [root]
    for _ in range(depth):
        hits = [d for d in level if _task_children(d)]
        if len(hits) > 1:
            raise DatasetMismatch(f"tasks found in several directories: {hits}")
        if hits:
            return hits[0]
        level = [c for d in level for c in sorted(d.iterdir())
                 if c.is_dir() and not (c / "task.toml").exists()]
    raise DatasetMismatch(f"no task directories under {root}")


def _check_expected(revision: str, expected: str) -> None:
    if revision == config.DATASET_REVISION and expected != config.ARCHIVE_LFS_OID:
        raise DatasetMismatch(f"LFS oid {expected} differs from the pinned {config.ARCHIVE_LFS_OID}")


def _check_pin(revision: str, base: Path) -> Path:
    pin = json.loads((base / "PIN.json").read_text())
    archive, tasks = base / "archive.tar.zst", base / "tasks"
    if (pin.get("revision") != revision or pin.get("sha256") != pin.get("lfs_oid")
            or not tasks.is_dir() or not archive.is_file() or sha256_file(archive) != pin["sha256"]):
        raise DatasetMismatch(f"{base} does not match its PIN.json; move it aside and fetch again")
    _check_expected(revision, pin["lfs_oid"])
    return tasks


def fetch(revision: str, dest_root: Path, *, download=download_file, oid=lfs_oid, now=time.time) -> Path:
    """Download, verify and extract the archive into dest_root/<revision>/tasks; return that directory.

    PIN.json is written last and marks a finished fetch. With a matching PIN.json nothing is fetched
    again; anything else left in the directory is from an interrupted fetch and is replaced.
    """
    base = Path(dest_root) / revision
    archive, tasks, staging = base / "archive.tar.zst", base / "tasks", base / "tasks.partial"
    if (base / "PIN.json").exists():
        return _check_pin(revision, base)
    expected = oid(revision)
    _check_expected(revision, expected)
    base.mkdir(parents=True, exist_ok=True)
    if not (archive.is_file() and sha256_file(archive) == expected):
        part = base / "archive.tar.zst.part"
        part.unlink(missing_ok=True)
        download(archive_url(revision), part)
        got = sha256_file(part)
        if got != expected:
            part.unlink()
            raise DatasetMismatch(f"downloaded sha256 {got} != LFS oid {expected}")
        part.replace(archive)
    for leftover in (staging, tasks):
        if leftover.exists():
            shutil.rmtree(leftover)
    extract(archive, staging)
    try:
        found = _task_children(tasks_parent(staging))
        tasks.mkdir()
        for task_dir in found:
            task_dir.rename(tasks / task_dir.name)
    finally:
        shutil.rmtree(staging)
    pin = {"revision": revision, "sha256": sha256_file(archive), "lfs_oid": expected,
           "url": archive_url(revision), "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now()))}
    (base / "PIN.json").write_text(json.dumps(pin, indent=2) + "\n")
    return tasks


def read_task(task_dir: Path) -> dict:
    """Facts about one task, read from its task.toml alone."""
    data = tomllib.loads((task_dir / "task.toml").read_text())
    steps = data.get("steps") or []
    if not steps:
        raise ValueError(f"{task_dir.name}: no [[steps]]; not a multi-step task")
    default_agent = data.get("agent", {}).get("timeout_sec")
    per_step = [step.get("agent", {}).get("timeout_sec", default_agent) for step in steps]
    if any(t is None for t in per_step):
        raise ValueError(f"{task_dir.name}: a step has no agent timeout")
    return {
        "task": task_dir.name,
        "dir": str(task_dir.resolve()),
        "rounds": len(steps),
        "step_names": [step["name"] for step in steps],
        "agent_timeout_sec": float(max(per_step)),
        "verifier_timeout_sec": float(data.get("verifier", {}).get("timeout_sec", HARBOR_VERIFIER_DEFAULT_SEC)),
        "reward_strategy": data.get("multi_step_reward_strategy", "mean"),
        "uniform_agent_timeout": len(set(per_step)) == 1,
    }


def list_tasks(tasks_root: Path) -> list:
    return [read_task(d) for d in _task_children(Path(tasks_root))]


def minutes(task_info: dict) -> int:
    """M for the prompts: 60 for a 3,600-s task, else 30."""
    return 60 if task_info["agent_timeout_sec"] >= 3600 else 30


def summary(infos: list, revision: str) -> dict:
    by_name = {i["task"]: i for i in infos}
    pool = {t: {"rounds": by_name[t]["rounds"], "minutes": minutes(by_name[t])}
            for t in config.POOL if t in by_name}
    walk = by_name.get(config.WALKTHROUGH)
    return {
        "revision": revision,
        "tasks": len(infos),
        "rounds": sum(i["rounds"] for i in infos),
        "reward_strategies": sorted({i["reward_strategy"] for i in infos}),
        "pool_missing": [t for t in config.POOL if t not in by_name],
        "pool_rounds": sum(p["rounds"] for p in pool.values()),
        "pool": pool,
        "walkthrough": {"rounds": walk["rounds"], "minutes": minutes(walk)} if walk else None,
        "nonuniform_agent_timeouts": [i["task"] for i in infos if not i["uniform_agent_timeout"]],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "list"))
    parser.add_argument("--root", type=Path, default=config.RUNS / "dataset")
    parser.add_argument("--revision", default=config.DATASET_REVISION)
    parser.add_argument("--out", type=Path, help="list: also write every task's facts here as JSON")
    args = parser.parse_args(argv)
    base = args.root / args.revision
    if args.command == "fetch":
        tasks = fetch(args.revision, args.root, download=download_file, oid=lfs_oid)
        pin = json.loads((base / "PIN.json").read_text())
        print(json.dumps({**pin, "tasks_dir": str(tasks), "tasks": len(_task_children(tasks))}))
        return 0
    if not (base / "PIN.json").is_file():
        print(f"no PIN.json under {base}; run fetch first", file=sys.stderr)
        return 2
    infos = list_tasks(base / "tasks")
    if args.out:
        args.out.write_text(json.dumps(infos, indent=2) + "\n")
    print(json.dumps(summary(infos, args.revision), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
