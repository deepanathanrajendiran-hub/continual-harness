import hashlib
import json
import os
import subprocess
import sys

import pytest

from bench.tb4 import bundle, config


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("bundle") / "root"
    return out, bundle.build(config.REPO_ROOT, config.BUNDLE_COMMIT, out)


def test_exact_tree(built):
    out, manifest = built
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert files == sorted(bundle.LAYOUT)
    assert sorted(manifest) == sorted(bundle.LAYOUT)
    assert "horizon/SKILL.md" in files and "horizon/scripts/harness.py" in files


def test_no_symlinks(built):
    out, _ = built
    assert [p for p in out.rglob("*") if p.is_symlink()] == []


def test_bytes_come_from_the_commit(built):
    out, manifest = built
    for rel, src in bundle.LAYOUT.items():
        expected = subprocess.run(
            ["git", "-C", str(config.REPO_ROOT), "show", f"{config.BUNDLE_COMMIT}:{src}"],
            capture_output=True, check=True).stdout
        assert (out / rel).read_bytes() == expected
        assert manifest[rel] == hashlib.sha256(expected).hexdigest()


def test_refuses_a_nonempty_output_directory(tmp_path):
    (tmp_path / "x").write_text("1")
    with pytest.raises(FileExistsError):
        bundle.build(config.REPO_ROOT, config.BUNDLE_COMMIT, tmp_path)


def _cli(skill, project, home, *args):
    return subprocess.run(
        [sys.executable, str(skill / "scripts/harness.py"), "--runtime", "claude",
         "--project", str(project), *args],
        capture_output=True, text=True, timeout=60, env={**os.environ, "HOME": str(home)})


def test_bundle_runs_outside_the_repository(built, tmp_path):
    out, _ = built
    skill = out / "horizon"
    project = tmp_path / "scratch project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    doctor = _cli(skill, project, home, "doctor")
    assert doctor.returncode == 0, doctor.stderr
    assert json.loads(doctor.stdout)["implementation"].startswith(str(out.resolve()))
    start = _cli(skill, project, home, "start", "smoke", "--gate", "true",
                 "--max-turns", "200", "--max-minutes", "100")
    assert start.returncode == 0, start.stderr
    summary = json.loads(start.stdout)
    assert summary["budget"] == {"max_turns": 200, "max_minutes": 100}
    check = _cli(skill, project, home, "check", summary["slug"], "--did", "smoke", "--next", "none")
    assert check.returncode == 0, check.stdout + check.stderr
    assert (project / ".claude/harness/goals" / f"{summary['slug']}.json").is_file()


def test_representative_ledger_is_realistic_and_has_no_python(built, tmp_path):
    out, _ = built
    ledger = tmp_path / "ledger"
    slug = bundle.representative_ledger(out / "horizon", ledger)
    goal = json.loads((ledger / "goals" / f"{slug}.json").read_text())
    assert goal["budget"] == {"max_turns": 200, "max_minutes": 100}
    assert goal["used"]["turns"] == 1
    assert list(ledger.rglob("*.py")) == []
