import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BIN = REPO_ROOT / ".claude" / "harness" / "bin"
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


# --- CRITICAL 1: layer validation (G2 cap defeat via REVERTED sentinel) ---

def test_record_rejects_reverted_sentinel(tmp_path, isolated):
    """CRITICAL 1: the CHANGELOG pre-flight (refine SKILL.md Step 4) skips
    any line whose layer field reads REVERTED when counting today's edits
    against the cap of 3. If record() accepted layer="REVERTED", that call
    would produce a real, committed, undoable edit invisible to the
    counter -- REVERTED must be unconstructible through record()."""
    target = tmp_path / "x.md"
    with pytest.raises(ValueError):
        refine_log.record("REVERTED", target, "rationale", "evidence")
    # observable state: no entry file was written, no side effect at all
    assert list((isolated / "undo").glob("*.json")) == []


def test_record_rejects_unknown_layer(tmp_path, isolated):
    target = tmp_path / "x.md"
    with pytest.raises(ValueError):
        refine_log.record("bogus", target, "r", "e")
    assert list((isolated / "undo").glob("*.json")) == []


def test_record_rejects_layer_containing_pipe(tmp_path, isolated):
    """A `|` in the layer field would corrupt CHANGELOG's `|`-delimited
    positional parsing (the same parsing the G2 pre-flight snippet relies
    on to read the layer field by position)."""
    target = tmp_path / "x.md"
    with pytest.raises(ValueError):
        refine_log.record("rho|REVERTED", target, "r", "e")
    assert list((isolated / "undo").glob("*.json")) == []


def test_record_rejects_layer_containing_newline(tmp_path, isolated):
    target = tmp_path / "x.md"
    with pytest.raises(ValueError):
        refine_log.record("rho\nG | x | y | z", target, "r", "e")
    assert list((isolated / "undo").glob("*.json")) == []


def test_record_accepts_every_valid_layer(tmp_path, isolated):
    for layer in ("rho", "G", "K", "M"):
        target = tmp_path / f"{layer}.md"
        entry = refine_log.record(layer, target, "r", "e")
        assert entry["layer"] == layer


# --- CRITICAL 2: G3 no-self-exemption enforced in code, not only prose ---

def test_record_denies_refine_skill_as_target(isolated):
    target = REPO_ROOT / ".claude" / "skills" / "refine" / "SKILL.md"
    with pytest.raises(ValueError):
        refine_log.record("G", target, "r", "e")
    assert list((isolated / "undo").glob("*.json")) == []


def test_record_denies_horizon_skill_as_target(isolated):
    target = REPO_ROOT / ".claude" / "skills" / "horizon" / "SKILL.md"
    with pytest.raises(ValueError):
        refine_log.record("G", target, "r", "e")
    assert list((isolated / "undo").glob("*.json")) == []


def test_record_denies_harness_bin_target(isolated):
    target = REPO_ROOT / ".claude" / "harness" / "bin" / "goal.py"
    with pytest.raises(ValueError):
        refine_log.record("G", target, "r", "e")
    assert list((isolated / "undo").glob("*.json")) == []


def test_record_denylist_survives_dotdot_traversal(isolated):
    """The denylist compares resolved absolute paths, not raw strings, so
    a `../` cannot slip a denied target past the check."""
    sneaky = (
        REPO_ROOT / ".claude" / "skills" / "horizon" / ".." / "refine" / "SKILL.md"
    )
    assert str(sneaky) != str(REPO_ROOT / ".claude" / "skills" / "refine" / "SKILL.md")
    with pytest.raises(ValueError):
        refine_log.record("G", sneaky, "r", "e")
    assert list((isolated / "undo").glob("*.json")) == []


def test_record_allows_ordinary_target_outside_denylist(tmp_path, isolated):
    """Sanity: the denylist doesn't over-broadly reject legitimate writes."""
    target = tmp_path / "CLAUDE.md"
    entry = refine_log.record("rho", target, "r", "e")
    assert entry["target"] == str(target)


# --- F1: denylist bypass via filename case / hardlink (identity, not string) ---

def test_record_denies_case_variant_of_protected_target(isolated):
    """F1: Path.resolve() canonicalizes symlinks and `..` but not case. On
    a case-insensitive filesystem (APFS's default) a differently-cased
    spelling of a protected path opens the exact same file and must be
    denied just as the canonically-cased path is."""
    canonical = REPO_ROOT / ".claude" / "skills" / "refine" / "SKILL.md"
    variant = REPO_ROOT / ".claude" / "skills" / "refine" / "skill.md"

    if not variant.exists() or not os.path.samefile(canonical, variant):
        pytest.skip(
            "filesystem is case-sensitive: lowercase variant does not "
            "resolve to the protected target, so this bypass doesn't apply"
        )

    with pytest.raises(ValueError):
        refine_log.record("G", variant, "r", "e")
    assert list((isolated / "undo").glob("*.json")) == []


def test_record_denies_hardlink_to_protected_target(tmp_path, isolated):
    """F1: a hardlink shares the protected file's inode but resolves to a
    completely different path string, so a string comparison of resolved
    paths misses it entirely. Identity comparison (samefile) must not."""
    canonical = REPO_ROOT / ".claude" / "skills" / "refine" / "SKILL.md"
    link = tmp_path / "not-suspicious-at-all.md"

    try:
        os.link(canonical, link)
    except OSError as exc:
        pytest.skip(f"hardlinks unsupported on this filesystem/setup: {exc}")

    assert os.path.samefile(canonical, link)

    with pytest.raises(ValueError):
        refine_log.record("G", link, "r", "e")
    assert list((isolated / "undo").glob("*.json")) == []


# --- IMPORTANT 3: CHANGELOG date stamped at commit time, not record time ---

def test_changelog_date_is_commit_time_not_record_time(tmp_path, isolated, monkeypatch):
    """IMPORTANT 3: record() sets `at` before the edit; commit can land
    after midnight UTC. The CHANGELOG line must reflect commit time, or a
    late-night edit is silently attributed to yesterday and undercounts
    against today's G2 cap -- the direction the skill says must never
    happen."""
    times = iter([
        "2026-08-08T23:59:50+00:00",  # record() timestamp
        "2026-08-09T00:00:10+00:00",  # commit_entry() timestamp
    ])
    monkeypatch.setattr(refine_log, "_now", lambda: next(times))

    target = tmp_path / "x.md"
    entry = refine_log.record("G", target, "r", "e")
    assert entry["at"].startswith("2026-08-08")

    target.write_text("content")
    refine_log.commit_entry(entry["id"])

    line = refine_log.paths.changelog().read_text().strip().splitlines()[-1]
    date = line.split("|")[0].strip()
    assert date == "2026-08-09"
