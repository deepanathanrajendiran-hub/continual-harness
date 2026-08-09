import sys
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[1] / ".claude" / "harness" / "bin"
sys.path.insert(0, str(BIN))

import refine_log  # noqa: E402
import json


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

def test_undo_atomic_restore_failure_leaves_target_intact(tmp_path, isolated, monkeypatch):
    """Critical 1: a crash between truncate and write must not empty the
    target. undo() must write to a temp file and os.replace() it in, so a
    failed replace leaves the target exactly as it was post-edit."""
    target = tmp_path / "CLAUDE.md"
    target.write_text("original\n")

    entry = refine_log.record("rho", target, "add routing rule", "turn 4")
    target.write_text("original\nnew rule\n")
    refine_log.commit_entry(entry["id"])

    def boom(*_args, **_kwargs):
        raise OSError("simulated disk failure during replace")

    monkeypatch.setattr(refine_log.os, "replace", boom)

    with pytest.raises(OSError):
        refine_log.undo()

    assert target.read_text() == "original\nnew rule\n"


def test_undo_raises_on_corrupt_entry(tmp_path, isolated):
    """Critical 2: a torn/corrupt entry file must never be silently
    skipped -- that would revert the wrong edit. undo() must refuse and
    leave every entry, including older ones, untouched."""
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    committed = []
    for target in (a, b):
        entry = refine_log.record("M", target, f"add {target.name}", "turn 1")
        target.write_text("content")
        refine_log.commit_entry(entry["id"])
        committed.append(entry)

    undo_dir = isolated / "undo"
    newest_path = undo_dir / f"{committed[-1]['id']}.json"
    newest_path.write_text("{not valid json")

    with pytest.raises(refine_log.CorruptEntry):
        refine_log.undo()

    oldest_path = undo_dir / f"{committed[0]['id']}.json"
    oldest_on_disk = json.loads(oldest_path.read_text())
    assert oldest_on_disk["reverted"] is False
    assert a.exists() and b.exists()


def test_undo_raises_on_staleness_conflict(tmp_path, isolated):
    """Important 3: if something modified the target after commit,
    undo() must refuse rather than silently discard that change."""
    target = tmp_path / "CLAUDE.md"
    target.write_text("original\n")

    entry = refine_log.record("rho", target, "add routing rule", "turn 4")
    target.write_text("original\nnew rule\n")
    refine_log.commit_entry(entry["id"])

    target.write_text("original\nnew rule\nexternal edit\n")

    with pytest.raises(refine_log.UndoConflict):
        refine_log.undo()

    assert target.read_text() == "original\nnew rule\nexternal edit\n"


def test_undo_force_overrides_staleness_conflict(tmp_path, isolated):
    """Important 3: force=True lets a user who has seen the conflict
    proceed deliberately."""
    target = tmp_path / "CLAUDE.md"
    target.write_text("original\n")

    entry = refine_log.record("rho", target, "add routing rule", "turn 4")
    target.write_text("original\nnew rule\n")
    refine_log.commit_entry(entry["id"])

    target.write_text("original\nnew rule\nexternal edit\n")

    refine_log.undo(force=True)
    assert target.read_text() == "original\n"


def test_record_does_not_reuse_sequence_id_after_gap(tmp_path, isolated):
    """Important 4: the next id must be max(existing) + 1, not a count,
    or removing an entry file causes the next record() to collide with
    and destroy a surviving entry."""
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    c = tmp_path / "c.md"
    a.write_text("a-original\n")
    b.write_text("b-original\n")
    c.write_text("c-original\n")

    committed = []
    for target in (a, b, c):
        entry = refine_log.record("M", target, f"edit {target.name}", "turn 1")
        target.write_text(target.read_text() + "edited\n")
        refine_log.commit_entry(entry["id"])
        committed.append(entry)

    undo_dir = isolated / "undo"
    survivor_a_id = committed[0]["id"]
    survivor_c_id = committed[2]["id"]
    middle_id = committed[1]["id"]

    before_a = json.loads((undo_dir / f"{survivor_a_id}.json").read_text())
    before_c = json.loads((undo_dir / f"{survivor_c_id}.json").read_text())

    (undo_dir / f"{middle_id}.json").unlink()

    d = tmp_path / "d.md"
    d.write_text("d-original\n")
    entry4 = refine_log.record("M", d, "edit d.md", "turn 1")

    assert entry4["id"] not in (survivor_a_id, survivor_c_id)

    after_a = json.loads((undo_dir / f"{survivor_a_id}.json").read_text())
    after_c = json.loads((undo_dir / f"{survivor_c_id}.json").read_text())
    assert after_a == before_a
    assert after_c == before_c
    assert after_a["previous_content"] == "a-original\n"
    assert after_c["previous_content"] == "c-original\n"
