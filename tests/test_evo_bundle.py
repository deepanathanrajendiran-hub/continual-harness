import hashlib
import json
import os
import subprocess
import sys

import pytest

from bench.evo import config
from bench.tb4 import bundle
from bench.tb4 import config as tb4

TB4_FILES = [
    "horizon/SKILL.md",
    "horizon/references/commands.md",
    "horizon/scripts/filelock.py",
    "horizon/scripts/gate.py",
    "horizon/scripts/goal.py",
    "horizon/scripts/harness.py",
    "horizon/scripts/paths.py",
    "horizon/scripts/refine_log.py",
    "horizon/scripts/steps.py",
    "horizon/scripts/task_state.py",
    "horizon/scripts/tree_hash.py",
]
TB4_MANIFEST = config.REPO_ROOT / "docs/evaluations/tb4-horizon-pilot/evidence/bundle-manifest.json"


def _files(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def _cli(skill, project, home, *args):
    return subprocess.run(
        [sys.executable, str(skill / "scripts/harness.py"), "--runtime", "claude",
         "--project", str(project), *args],
        capture_output=True, text=True, timeout=60, env={**os.environ, "HOME": str(home)})


@pytest.fixture(scope="module")
def v2(tmp_path_factory):
    out = tmp_path_factory.mktemp("v2 bundle") / "root"
    return out, bundle.build(config.REPO_ROOT, config.BUNDLE_COMMIT, out, modules=config.BUNDLE_MODULES)


def test_bundle_commit_is_in_the_object_store():
    done = subprocess.run(["git", "-C", str(config.REPO_ROOT), "cat-file", "-t", config.BUNDLE_COMMIT],
                          capture_output=True, text=True)
    assert done.stdout.strip() == "commit", done.stderr


def test_layout_is_computed_from_modules():
    assert bundle.LAYOUT == bundle.layout(bundle.MODULES) == bundle.layout()
    extra = bundle.layout(("x",))
    assert extra["horizon/scripts/x.py"] == "harness/x.py"
    assert extra["horizon/scripts/harness.py"] == "harness/cli.py"
    assert len(extra) == 4


def test_v2_bundle_includes_reviewing(v2):
    out, manifest = v2
    expected = sorted(bundle.layout(config.BUNDLE_MODULES))
    assert _files(out) == expected == sorted(manifest)
    assert "horizon/scripts/reviewing.py" in expected
    assert len(expected) == len(TB4_FILES) + 1


def test_v2_bytes_come_from_the_bundle_commit(v2):
    out, manifest = v2
    for rel, src in bundle.layout(config.BUNDLE_MODULES).items():
        expected = subprocess.run(
            ["git", "-C", str(config.REPO_ROOT), "show", f"{config.BUNDLE_COMMIT}:{src}"],
            capture_output=True, check=True).stdout
        assert (out / rel).read_bytes() == expected
        assert manifest[rel] == hashlib.sha256(expected).hexdigest()


def test_v2_bundle_runs_outside_the_repository(v2, tmp_path):
    out, _ = v2
    skill = out / "horizon"
    project, home = tmp_path / "scratch project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    doctor = _cli(skill, project, home, "doctor")
    assert doctor.returncode == 0, doctor.stderr
    assert json.loads(doctor.stdout)["implementation"].startswith(str(out.resolve()))
    start = _cli(skill, project, home, "start", "smoke", "--gate", "true",
                 "--max-turns", "200", "--max-minutes", "30")
    assert start.returncode == 0, start.stderr
    slug = json.loads(start.stdout)["slug"]
    assert (project / ".claude/harness/goals" / f"{slug}.json").is_file()


def test_tb4_module_set_cannot_run_the_v2_cli(tmp_path):
    out = tmp_path / "root"
    bundle.build(config.REPO_ROOT, config.BUNDLE_COMMIT, out)
    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    doctor = _cli(out / "horizon", project, home, "doctor")
    assert doctor.returncode != 0
    assert "reviewing" in doctor.stderr


def test_tb4_default_build_is_unchanged(tmp_path):
    out = tmp_path / "root"
    manifest = bundle.build(config.REPO_ROOT, tb4.BUNDLE_COMMIT, out)
    assert tb4.BUNDLE_COMMIT == "2f65f2a24d753b6875bd126fc989335baff82ed8"
    assert _files(out) == TB4_FILES == sorted(manifest)
    assert manifest == json.loads(TB4_MANIFEST.read_text())["files"]
