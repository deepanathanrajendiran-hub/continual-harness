import hashlib
import json
import os
import subprocess
import tarfile
import tomllib
from pathlib import Path

import pytest

from bench.evo import config, dataset

REV = "rev-test"
# The shape the HF paths-info API returned for the pinned archive on 2026-10-09.
PATHS_INFO = [{
    "type": "file", "oid": "0c64f0cc960105014af45c94409188afd04ec75a", "size": 70121019,
    "lfs": {"oid": "a13d0cb47574282372c59366217ac68d895ff49d1387c81098b058f739906184",
            "size": 70121019, "pointerSize": 133},
    "xetHash": "bb9b08eb3070f43107a0717b9d3ce088c15a8ad456623230ff4f768fe3661381",
    "path": "archives/evocodebench_wotraj.tar.zst",
}]


def task_toml(rounds=3, agent=1800.0, verifier=1800.0, strategy="mean", step_agent=None):
    """A synthetic task.toml in EvoCode's documented format (README, schema_version 1.2)."""
    lines = ['schema_version = "1.2"']
    if strategy is not None:
        lines.append(f'multi_step_reward_strategy = "{strategy}"')
    lines += ["", "[metadata]", 'name = "synthetic"', "", "[metadata.requirement_chain]",
              f"num_steps = {rounds}"]
    for i in range(1, rounds + 1):
        lines += ["", "[[metadata.requirement_chain.steps]]", f'step = "round-{i}"',
                  'change_types = ["extension"]']
    if agent is not None:
        lines += ["", "[agent]", f"timeout_sec = {agent}"]
    if verifier is not None:
        lines += ["", "[verifier]", f"timeout_sec = {verifier}"]
    lines += ["", "[environment]", "build_timeout_sec = 600.0", "cpus = 1", "memory_mb = 4096"]
    for i in range(1, rounds + 1):
        lines += ["", "[[steps]]", f'name = "round-{i}"']
        if step_agent and i in step_agent:
            lines += ["", "[steps.agent]", f"timeout_sec = {step_agent[i]}"]
    return "\n".join(lines) + "\n"


def write_task(root: Path, name: str, toml: str) -> Path:
    task = root / name
    (task / "environment").mkdir(parents=True)
    (task / "environment" / "Dockerfile").write_text("FROM ubuntu:22.04\n")
    (task / "task.toml").write_text(toml)
    for step in tomllib.loads(toml).get("steps", []):
        step_dir = task / "steps" / step["name"]
        for sub in ("tests", "solution"):
            (step_dir / sub).mkdir(parents=True)
        (step_dir / "instruction.md").write_text("synthetic request\n")
        (step_dir / "tests" / "test.sh").write_text("#!/bin/bash\n")
        (step_dir / "solution" / "solve.sh").write_text("#!/bin/bash\n")
    return task


def make_archive(tmp_path: Path, tasks: dict, wrapper=None) -> bytes:
    src = tmp_path / "archive-src"
    base = src / wrapper if wrapper else src
    base.mkdir(parents=True)
    for name, toml in tasks.items():
        write_task(base, name, toml)
    (src / "README.md").write_text("synthetic\n")
    tar = tmp_path / "archive.tar"
    with tarfile.open(tar, "w") as out:
        for child in sorted(src.iterdir()):
            out.add(child, arcname=child.name)
    zst = tmp_path / "archive.tar.zst"
    subprocess.run(["zstd", "-q", "-f", str(tar), "-o", str(zst)], check=True)
    return zst.read_bytes()


class Downloader:
    def __init__(self, blob: bytes):
        self.blob, self.calls = blob, []

    def __call__(self, url, dest):
        self.calls.append(url)
        Path(dest).write_bytes(self.blob)


def boom(*args, **kwargs):
    raise AssertionError("must not be called")


@pytest.fixture
def blob(tmp_path):
    return make_archive(tmp_path, {"theme_d1_w2_x": task_toml(3), "theme_d5_w1_y": task_toml(2, agent=3600.0)})


def test_archive_url():
    assert dataset.archive_url(config.DATASET_REVISION) == (
        "https://huggingface.co/datasets/UnipatAI/EvoCodeBench/resolve/"
        "9fcae3e5539d1c0e85e2481fe06bd6af42cc4bc6/archives/evocodebench_wotraj.tar.zst")


def test_lfs_oid_posts_the_archive_path_to_paths_info():
    calls = []

    def fetch(url, data=None):
        calls.append((url, data))
        return PATHS_INFO

    assert dataset.lfs_oid(config.DATASET_REVISION, fetch=fetch) == config.ARCHIVE_LFS_OID
    assert calls == [("https://huggingface.co/api/datasets/UnipatAI/EvoCodeBench/paths-info/"
                      "9fcae3e5539d1c0e85e2481fe06bd6af42cc4bc6",
                      b"paths=archives%2Fevocodebench_wotraj.tar.zst")]


def test_lfs_oid_refuses_a_missing_or_non_lfs_entry():
    with pytest.raises(dataset.DatasetMismatch):
        dataset.lfs_oid(REV, fetch=lambda url, data=None: [])
    no_lfs = [{**PATHS_INFO[0], "lfs": None}]
    with pytest.raises(dataset.DatasetMismatch):
        dataset.lfs_oid(REV, fetch=lambda url, data=None: no_lfs)


def test_fetch_verifies_extracts_and_pins(tmp_path, blob):
    root = tmp_path / "dataset"
    digest = hashlib.sha256(blob).hexdigest()
    download = Downloader(blob)
    tasks = dataset.fetch(REV, root, download=download, oid=lambda rev: digest, now=lambda: 0)
    assert tasks == root / REV / "tasks"
    assert download.calls == [dataset.archive_url(REV)]
    assert sorted(p.name for p in tasks.iterdir()) == ["theme_d1_w2_x", "theme_d5_w1_y"]
    assert (tasks / "theme_d1_w2_x" / "task.toml").is_file()
    assert (root / REV / "archive.tar.zst").read_bytes() == blob
    pin = json.loads((root / REV / "PIN.json").read_text())
    assert pin == {"revision": REV, "sha256": digest, "lfs_oid": digest, "url": dataset.archive_url(REV),
                   "fetched_at": "1970-01-01T00:00:00Z"}
    assert sorted(p.name for p in (root / REV).iterdir()) == ["PIN.json", "archive.tar.zst", "tasks"]


def test_fetch_raises_on_a_sha256_mismatch_and_leaves_nothing_pinned(tmp_path, blob):
    root = tmp_path / "dataset"
    with pytest.raises(dataset.DatasetMismatch):
        dataset.fetch(REV, root, download=Downloader(blob), oid=lambda rev: "0" * 64)
    assert not (root / REV / "PIN.json").exists()
    assert not (root / REV / "tasks").exists()
    assert not (root / REV / "archive.tar.zst").exists()
    assert not (root / REV / "archive.tar.zst.part").exists()


def test_fetch_refuses_an_api_oid_that_differs_from_the_pinned_one(tmp_path):
    with pytest.raises(dataset.DatasetMismatch):
        dataset.fetch(config.DATASET_REVISION, tmp_path, download=boom, oid=lambda rev: "0" * 64)
    assert not (tmp_path / config.DATASET_REVISION / "archive.tar.zst").exists()


def test_fetch_is_idempotent_when_the_pin_matches(tmp_path, blob):
    root = tmp_path / "dataset"
    digest = hashlib.sha256(blob).hexdigest()
    first = dataset.fetch(REV, root, download=Downloader(blob), oid=lambda rev: digest, now=lambda: 0)
    pin_before = (root / REV / "PIN.json").read_text()
    again = dataset.fetch(REV, root, download=boom, oid=boom, now=lambda: 99)
    assert again == first
    assert (root / REV / "PIN.json").read_text() == pin_before


def test_fetch_refuses_a_tampered_archive_after_pinning(tmp_path, blob):
    root = tmp_path / "dataset"
    digest = hashlib.sha256(blob).hexdigest()
    dataset.fetch(REV, root, download=Downloader(blob), oid=lambda rev: digest)
    (root / REV / "archive.tar.zst").write_bytes(blob + b"x")
    with pytest.raises(dataset.DatasetMismatch):
        dataset.fetch(REV, root, download=boom, oid=boom)


def test_fetch_flattens_a_wrapper_directory(tmp_path):
    blob = make_archive(tmp_path, {"theme_d8_w5_z": task_toml(2)}, wrapper="EvoCodeBench")
    root = tmp_path / "dataset"
    tasks = dataset.fetch(REV, root, download=Downloader(blob), oid=lambda rev: hashlib.sha256(blob).hexdigest())
    assert [p.name for p in tasks.iterdir()] == ["theme_d8_w5_z"]
    assert not (root / REV / "tasks.partial").exists()


def test_fetch_reuses_a_verified_archive_and_replaces_an_unpinned_extraction(tmp_path, blob):
    base = tmp_path / "dataset" / REV
    (base / "tasks" / "half-extracted").mkdir(parents=True)
    (base / "tasks.partial" / "junk").mkdir(parents=True)
    (base / "archive.tar.zst").write_bytes(blob)
    tasks = dataset.fetch(REV, tmp_path / "dataset", download=boom, oid=lambda rev: hashlib.sha256(blob).hexdigest())
    assert sorted(p.name for p in tasks.iterdir()) == ["theme_d1_w2_x", "theme_d5_w1_y"]
    assert not (base / "tasks.partial").exists()
    assert (base / "PIN.json").is_file()


def test_fetch_refuses_an_archive_without_tasks(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "README.md").write_text("no tasks\n")
    tar, zst = tmp_path / "a.tar", tmp_path / "a.tar.zst"
    with tarfile.open(tar, "w") as out:
        out.add(src / "README.md", arcname="README.md")
    subprocess.run(["zstd", "-q", "-f", str(tar), "-o", str(zst)], check=True)
    blob = zst.read_bytes()
    with pytest.raises(dataset.DatasetMismatch):
        dataset.fetch(REV, tmp_path / "dataset", download=Downloader(blob),
                      oid=lambda rev: hashlib.sha256(blob).hexdigest())
    assert not (tmp_path / "dataset" / REV / "PIN.json").exists()


@pytest.fixture
def locked_steps():
    """chmod 000 every steps/ directory so any read under it raises PermissionError."""
    locked = []
    yield locked
    for path in locked:
        os.chmod(path, 0o755)


def test_list_tasks_parses_multi_step_tasks_without_touching_steps(tmp_path, locked_steps):
    root = tmp_path / "tasks"
    write_task(root, "theme_d1_w2_x", task_toml(3))
    write_task(root, "theme_d5_w1_y", task_toml(4, agent=1800.0, step_agent={2: 3600.0}, strategy=None,
                                                 verifier=None))
    (root / "notes.txt").write_text("not a task\n")
    (root / "empty-dir").mkdir()
    for steps in root.glob("*/steps"):
        os.chmod(steps, 0)
        locked_steps.append(steps)
    infos = dataset.list_tasks(root)
    assert infos == [
        {"task": "theme_d1_w2_x", "dir": str((root / "theme_d1_w2_x").resolve()), "rounds": 3,
         "step_names": ["round-1", "round-2", "round-3"], "agent_timeout_sec": 1800.0,
         "verifier_timeout_sec": 1800.0, "reward_strategy": "mean", "uniform_agent_timeout": True},
        {"task": "theme_d5_w1_y", "dir": str((root / "theme_d5_w1_y").resolve()), "rounds": 4,
         "step_names": ["round-1", "round-2", "round-3", "round-4"], "agent_timeout_sec": 3600.0,
         "verifier_timeout_sec": 600.0, "reward_strategy": "mean", "uniform_agent_timeout": False},
    ]
    json.dumps(infos)


def test_list_tasks_refuses_single_step_tasks_and_missing_agent_timeouts(tmp_path):
    single = tmp_path / "single"
    write_task(single, "t", task_toml(0))
    with pytest.raises(ValueError, match="multi-step"):
        dataset.list_tasks(single)
    untimed = tmp_path / "untimed"
    write_task(untimed, "t", task_toml(2, agent=None))
    with pytest.raises(ValueError, match="agent timeout"):
        dataset.list_tasks(untimed)


def test_minutes():
    assert dataset.minutes({"agent_timeout_sec": 1800.0}) == 30
    assert dataset.minutes({"agent_timeout_sec": 3599.0}) == 30
    assert dataset.minutes({"agent_timeout_sec": 3600.0}) == 60
    assert dataset.minutes({"agent_timeout_sec": 7200.0}) == 60


def test_cli_fetch_then_list(tmp_path, monkeypatch, capsys):
    names = {config.POOL[0]: task_toml(10), config.POOL[1]: task_toml(10, agent=3600.0),
             config.WALKTHROUGH: task_toml(5), "theme_d2_w1_other": task_toml(7, step_agent={1: 900.0})}
    blob = make_archive(tmp_path, names)
    monkeypatch.setattr(dataset, "download_file", Downloader(blob))
    monkeypatch.setattr(dataset, "lfs_oid", lambda rev: hashlib.sha256(blob).hexdigest())
    root = tmp_path / "dataset"
    assert dataset.main(["fetch", "--root", str(root), "--revision", REV]) == 0
    fetched = json.loads(capsys.readouterr().out)
    assert fetched["revision"] == REV and fetched["tasks"] == 4
    out = tmp_path / "tasks.json"
    assert dataset.main(["list", "--root", str(root), "--revision", REV, "--out", str(out)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "revision": REV, "tasks": 4, "rounds": 32, "reward_strategies": ["mean"],
        "pool_missing": list(config.POOL[2:]), "pool_rounds": 20,
        "pool": {config.POOL[0]: {"rounds": 10, "minutes": 30}, config.POOL[1]: {"rounds": 10, "minutes": 60}},
        "walkthrough": {"rounds": 5, "minutes": 30},
        "nonuniform_agent_timeouts": ["theme_d2_w1_other"],
    }
    assert [i["task"] for i in json.loads(out.read_text())] == sorted(names)


def test_cli_list_requires_a_finished_fetch(tmp_path, capsys):
    assert dataset.main(["list", "--root", str(tmp_path), "--revision", REV]) == 2
    assert "fetch" in capsys.readouterr().err
