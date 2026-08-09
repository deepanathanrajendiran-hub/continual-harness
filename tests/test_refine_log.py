import sys
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[1] / ".claude" / "harness" / "bin"
sys.path.insert(0, str(BIN))

import refine_log  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "harness"
    (root / "undo").mkdir(parents=True)
    monkeypatch.setattr(refine_log.paths, "undo_dir", lambda: root / "undo")
    monkeypatch.setattr(refine_log.paths, "changelog", lambda: root / "CHANGELOG.md")
    return root


def test_undo_removes_a_created_file(tmp_path, isolated):
    """T7: a created memory file is removed and the entry retired."""
    target = tmp_path / "memory" / "no-api-keys.md"
    target.parent.mkdir()

    entry = refine_log.record("M", target, "user prefers no-key solutions", "turn 12")
    target.write_text("---\nname: no-api-keys\n---\nbody")
    refine_log.commit_entry(entry["id"])

    assert target.exists()
    refine_log.undo()
    assert not target.exists()
    assert "REVERTED" in refine_log.paths.changelog().read_text()


def test_undo_restores_previous_content(tmp_path, isolated):
    target = tmp_path / "CLAUDE.md"
    target.write_text("original\n")

    entry = refine_log.record("rho", target, "add routing rule", "turn 4")
    target.write_text("original\nnew rule\n")
    refine_log.commit_entry(entry["id"])

    refine_log.undo()
    assert target.read_text() == "original\n"


def test_changelog_line_format(tmp_path, isolated):
    target = tmp_path / "x.md"
    entry = refine_log.record("G", target, "promote retry helper", "turns 3,7,11")
    target.write_text("skill")
    refine_log.commit_entry(entry["id"])

    line = refine_log.paths.changelog().read_text().strip().splitlines()[-1]
    parts = [p.strip() for p in line.split("|")]
    assert parts[1] == "G"
    assert parts[3] == "promote retry helper"
    assert parts[4] == "turns 3,7,11"


def test_undo_with_empty_changelog_raises():
    with pytest.raises(refine_log.NothingToUndo):
        refine_log.undo()


def test_undo_twice_walks_back_two_entries(tmp_path, isolated):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    for target in (a, b):
        entry = refine_log.record("M", target, f"add {target.name}", "turn 1")
        target.write_text("content")
        refine_log.commit_entry(entry["id"])

    refine_log.undo()
    assert not b.exists() and a.exists()
    refine_log.undo()
    assert not a.exists()


def test_uncommitted_entry_is_not_undone(tmp_path, isolated):
    """A recorded-but-never-committed entry means the edit failed; undo
    must not act on it."""
    target = tmp_path / "never.md"
    refine_log.record("M", target, "aborted edit", "turn 2")
    with pytest.raises(refine_log.NothingToUndo):
        refine_log.undo()
