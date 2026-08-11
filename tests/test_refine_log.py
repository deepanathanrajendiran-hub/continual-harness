import base64
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BIN = REPO_ROOT / ".claude" / "harness" / "bin"
sys.path.insert(0, str(BIN))

import refine_log  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "harness"
    (root / "undo").mkdir(parents=True)
    monkeypatch.setattr(refine_log.paths, "undo_dir", lambda: root / "undo")
    monkeypatch.setattr(refine_log.paths, "changelog", lambda: root / "CHANGELOG.md")
    return root


# ---------------------------------------------------------------- apply/undo

def test_apply_writes_the_approved_content(tmp_path):
    """The module performs the write, so what was approved, what was
    recorded and what landed cannot diverge."""
    target = tmp_path / "CLAUDE.md"
    target.write_text("original\n")

    entry = refine_log.apply_edit("rho", [(target, "original\nnew rule\n")],
                                  "add a rule", "turn 12")

    assert target.read_text() == "original\nnew rule\n"
    assert entry["targets"][0]["new_sha256"] == refine_log._sha256(target.read_text())


def test_undo_restores_previous_content(tmp_path):
    target = tmp_path / "CLAUDE.md"
    target.write_text("original\n")
    refine_log.apply_edit("rho", [(target, "changed\n")], "r", "e")

    refine_log.undo()
    assert target.read_text() == "original\n"


def test_undo_removes_a_created_file(tmp_path):
    """T7: a created memory file is removed and the entry retired."""
    target = tmp_path / "memory" / "no-api-keys.md"
    target.parent.mkdir()
    refine_log.apply_edit("M", [(target, "---\nname: x\n---\nbody\n")], "r", "e")
    assert target.exists()

    refine_log.undo()
    assert not target.exists()
    assert "REVERTED" in refine_log.paths.changelog().read_text()


def test_undo_twice_walks_back_two_entries(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    refine_log.apply_edit("M", [(a, "A")], "first", "e")
    refine_log.apply_edit("M", [(b, "B")], "second", "e")

    refine_log.undo()
    assert not b.exists() and a.exists()
    refine_log.undo()
    assert not a.exists()


def test_undo_with_no_entries_raises():
    with pytest.raises(refine_log.NothingToUndo):
        refine_log.undo()


# ------------------------------------------------- multi-target atomic units

def test_one_proposal_reverts_all_of_its_files(tmp_path):
    """A memory write touches the memory file AND the MEMORY.md index. If
    the index sits outside the entry, undo orphans it -- the index keeps
    advertising a memory that no longer exists."""
    mem = tmp_path / "memory"
    mem.mkdir()
    note, index = mem / "quote-paths.md", mem / "MEMORY.md"
    index.write_text("- [Older](older.md) — hook\n")

    refine_log.apply_edit("M", [
        (note, "---\nname: quote-paths\n---\nbody\n"),
        (index, index.read_text() + "- [Quote paths](quote-paths.md) — hook\n"),
    ], "record the lesson", "turn 3")

    assert note.exists() and "quote-paths" in index.read_text()

    refine_log.undo()
    assert not note.exists()
    assert index.read_text() == "- [Older](older.md) — hook\n", "index line orphaned"


def test_a_failed_write_rolls_back_the_whole_proposal(tmp_path, monkeypatch):
    """An entry must never describe a partially applied proposal."""
    good = tmp_path / "good.md"
    good.write_text("before\n")
    # A missing parent is now created on purpose, so trigger a failure that
    # cannot be: a regular file standing where a directory would have to be.
    blocker = tmp_path / "afile"
    blocker.write_text("i am not a directory")
    bad = blocker / "bad.md"

    with pytest.raises((refine_log.UndoTargetUnavailable, NotADirectoryError, OSError)):
        refine_log.apply_edit("M", [(good, "after\n"), (bad, "x")], "r", "e")

    assert good.read_text() == "before\n", "first target not rolled back"
    assert not list((refine_log.paths.undo_dir()).glob("*.json")), "entry recorded for a failed proposal"


# ------------------------------------------------------------------- the cap

def test_cap_counts_entries_not_changelog_lines(tmp_path):
    """A newline in a rationale must not hide a real edit from the cap.
    Counting parsed markdown lines made one unescaped delimiter enough to
    make a committed, undoable edit invisible."""
    for i in range(3):
        refine_log.apply_edit("M", [(tmp_path / f"h{i}.md", "x")], f"rationale {i}", "ev")
    assert refine_log.count_edits_today() == 3

    refine_log.apply_edit("M", [(tmp_path / "fourth.md", "real")],
                          "loosen the bar\n(continued on a new line)", "quoted:\noutput\nhere")

    assert refine_log.count_edits_today() == 4, "a newline hid a real edit from the cap"
    assert (tmp_path / "fourth.md").exists()


def test_changelog_stays_one_line_per_entry(tmp_path):
    refine_log.apply_edit("M", [(tmp_path / "a.md", "x")],
                          "multi\nline\nrationale", "multi\nline\nevidence")
    body = [l for l in refine_log.paths.changelog().read_text().splitlines()
            if l.startswith("20")]
    assert len(body) == 1
    assert body[0].count("|") == 4, "field count broken by embedded delimiters"


def test_reverted_entries_do_not_count_toward_the_cap(tmp_path):
    refine_log.apply_edit("M", [(tmp_path / "a.md", "x")], "r", "e")
    assert refine_log.count_edits_today() == 1
    refine_log.undo()
    assert refine_log.count_edits_today() == 0


def test_cap_refuses_to_count_past_corruption(tmp_path):
    refine_log.apply_edit("M", [(tmp_path / "a.md", "x")], "r", "e")
    (refine_log.paths.undo_dir() / "0001.json").write_text("{not json")
    with pytest.raises(refine_log.CorruptEntry):
        refine_log.count_edits_today()


# ---------------------------------------------------------------- guardrails

@pytest.mark.parametrize("bad_layer", ["REVERTED", "rho|x", "M\nX", "", "memory"])
def test_apply_rejects_invalid_layers(tmp_path, bad_layer):
    with pytest.raises(ValueError):
        refine_log.apply_edit(bad_layer, [(tmp_path / "a.md", "x")], "r", "e")


@pytest.mark.parametrize("path_fragment", [
    ".claude/skills/refine/SKILL.md",
    ".claude/skills/horizon/SKILL.md",
    ".claude/harness/bin/refine_log.py",
    ".claude/harness/CHANGELOG.md",
    ".claude/harness/undo/0001.json",
    ".claude/harness/goals/x.json",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/hooks/pre.sh",
])
def test_protected_paths_are_denied_in_any_project(tmp_path, path_fragment):
    """G3 must hold for the global copies too, not just this project's --
    and for the ledger the cap is counted from, and for settings files
    that can configure hooks running arbitrary shell."""
    for base in (tmp_path / "someproject", tmp_path / "fakehome"):
        target = base / path_fragment
        target.parent.mkdir(parents=True, exist_ok=True)
        with pytest.raises(refine_log.ProtectedTarget):
            refine_log.apply_edit("M", [(target, "x")], "r", "e")


def test_protected_check_survives_dotdot_and_case(tmp_path):
    base = tmp_path / "proj" / ".claude" / "skills" / "refine"
    base.mkdir(parents=True)
    (base / "SKILL.md").write_text("rules")
    sneaky = tmp_path / "proj" / ".claude" / "skills" / ".." / "skills" / "refine" / "SKILL.md"
    with pytest.raises(refine_log.ProtectedTarget):
        refine_log.apply_edit("M", [(sneaky, "x")], "r", "e")


def test_ordinary_targets_are_still_allowed(tmp_path):
    """A denylist that blocks everything is not a fix."""
    target = tmp_path / "proj" / ".claude" / "agents" / "researcher.md"
    target.parent.mkdir(parents=True)
    entry = refine_log.apply_edit("K", [(target, "spec")], "r", "e")
    assert target.read_text() == "spec"
    assert entry["layer"] == "K"


# ------------------------------------------------------------- content fidelity

def test_symlinked_target_keeps_its_link(tmp_path):
    """A dotfiles-managed CLAUDE.md is a symlink. Replacing the link
    instead of its destination silently detaches it from the repo that
    manages it, while appearing to have worked."""
    real = tmp_path / "dotfiles" / "CLAUDE.md"
    real.parent.mkdir()
    real.write_text("# rules\noriginal\n")
    link = tmp_path / "CLAUDE.md"
    link.symlink_to(real)

    refine_log.apply_edit("rho", [(link, "# rules\noriginal\nnew\n")], "r", "e")
    assert link.is_symlink(), "the symlink was replaced by a regular file"
    assert real.read_text() == "# rules\noriginal\nnew\n"

    refine_log.undo()
    assert link.is_symlink()
    assert real.read_text() == "# rules\noriginal\n", "undo left the change live in dotfiles"


def test_undo_is_byte_exact_for_crlf(tmp_path):
    target = tmp_path / "win.md"
    target.write_bytes(b"line1\r\nline2\r\n")
    refine_log.apply_edit("rho", [(target, "replaced\n")], "r", "e")
    refine_log.undo()
    assert target.read_bytes() == b"line1\r\nline2\r\n"


def test_non_utf8_target_round_trips(tmp_path):
    """A latin-1 CLAUDE.md must not crash the snapshot, and must come
    back byte-identical."""
    target = tmp_path / "latin.md"
    original = "caf\xe9 na\xefve\n".encode("latin-1")
    target.write_bytes(original)

    refine_log.apply_edit("rho", [(target, "ascii replacement\n")], "r", "e")
    refine_log.undo()
    assert target.read_bytes() == original


def test_directory_as_target_is_rejected(tmp_path):
    d = tmp_path / "adir"
    d.mkdir()
    with pytest.raises(ValueError):
        refine_log.apply_edit("M", [(d, "x")], "r", "e")


# ----------------------------------------------------------------- staleness

def test_undo_refuses_when_the_target_changed(tmp_path):
    target = tmp_path / "CLAUDE.md"
    target.write_text("original\n")
    refine_log.apply_edit("rho", [(target, "approved\n")], "r", "e")
    target.write_text("approved\nMY OWN LATER EDIT\n")

    with pytest.raises(refine_log.UndoConflict):
        refine_log.undo()
    assert "MY OWN LATER EDIT" in target.read_text()


def test_undo_force_overrides_staleness(tmp_path):
    target = tmp_path / "CLAUDE.md"
    target.write_text("original\n")
    refine_log.apply_edit("rho", [(target, "approved\n")], "r", "e")
    target.write_text("approved\nlater\n")

    refine_log.undo(force=True)
    assert target.read_text() == "original\n"


def test_undo_reports_a_missing_parent_clearly(tmp_path):
    import shutil
    d = tmp_path / "layer"
    d.mkdir()
    target = d / "CLAUDE.md"
    target.write_text("original\n")
    refine_log.apply_edit("rho", [(target, "changed\n")], "r", "e")
    shutil.rmtree(d)

    with pytest.raises(refine_log.UndoTargetUnavailable):
        refine_log.undo()
    entries, _ = refine_log._entries()
    assert entries[-1]["reverted"] is False


def test_undo_raises_on_corrupt_entry(tmp_path):
    refine_log.apply_edit("M", [(tmp_path / "a.md", "A")], "first", "e")
    refine_log.apply_edit("M", [(tmp_path / "b.md", "B")], "second", "e")
    (refine_log.paths.undo_dir() / "0002.json").write_text("{not json")

    with pytest.raises(refine_log.CorruptEntry):
        refine_log.undo()
    entries, _ = refine_log._entries()
    assert all(not e["reverted"] for e in entries), "reverted past damaged history"


def test_ids_do_not_collide_after_a_gap(tmp_path):
    for n in ("a", "b", "c"):
        refine_log.apply_edit("M", [(tmp_path / f"{n}.md", n)], "r", "e")
    (refine_log.paths.undo_dir() / "0002.json").unlink()

    refine_log.apply_edit("M", [(tmp_path / "d.md", "d")], "r", "e")
    ids = sorted(p.stem for p in refine_log.paths.undo_dir().glob("*.json"))
    assert len(ids) == len(set(ids)) == 3
    assert json.loads((refine_log.paths.undo_dir() / "0001.json").read_text())["rationale"] == "r"


@pytest.mark.parametrize("variant", [
    ".claude/Skills/refine/SKILL.md",
    ".claude/SKILLS/refine/SKILL.md",
    ".CLAUDE/skills/refine/SKILL.md",
    ".claude/Harness/bin/refine_log.py",
])
def test_protected_paths_are_case_insensitive(tmp_path, variant):
    """On a case-insensitive filesystem (macOS default) a capitalised
    directory reaches the same real file. A case-sensitive regex let
    .claude/Skills/refine/SKILL.md overwrite the real rules."""
    target = tmp_path / "proj" / variant
    target.parent.mkdir(parents=True, exist_ok=True)
    with pytest.raises(refine_log.ProtectedTarget):
        refine_log.apply_edit("M", [(target, "G3 REMOVED")], "r", "e")


def test_protected_check_resolves_a_symlinked_parent(tmp_path):
    """Resolving only the final component missed a symlinked parent: a link
    at proj/notes -> .claude/harness/bin let a write land on the real
    enforcement code."""
    proj = tmp_path / "proj"
    real = proj / ".claude" / "harness" / "bin"
    real.mkdir(parents=True)
    (real / "refine_log.py").write_text("REAL ENFORCEMENT\n")
    (proj / "notes").symlink_to(real)

    with pytest.raises(refine_log.ProtectedTarget):
        refine_log.apply_edit("M", [(proj / "notes" / "refine_log.py", "REPLACED")], "r", "e")
    assert (real / "refine_log.py").read_text() == "REAL ENFORCEMENT\n"


@pytest.mark.parametrize("surface", [
    ".claude.json", ".mcp.json", ".claude/commands/x.md",
    ".claude/plugins/p/hooks/h.sh", ".claude/settings.json.bak",
])
def test_other_arbitrary_shell_surfaces_are_denied(tmp_path, surface):
    """Each of these defines something that executes in a later session."""
    target = tmp_path / "proj" / surface
    target.parent.mkdir(parents=True, exist_ok=True)
    with pytest.raises(refine_log.ProtectedTarget):
        refine_log.apply_edit("M", [(target, "x")], "r", "e")


def test_a_foreign_schema_entry_is_corruption_not_a_crash(tmp_path):
    """An entry from an older schema parses as JSON and then raised a bare
    KeyError deep inside undo() — which the skill's documented try/except
    does not catch, because CorruptEntry is what it was told to expect."""
    refine_log.apply_edit("M", [(tmp_path / "a.md", "A")], "r", "e")
    (refine_log.paths.undo_dir() / "0099.json").write_text(json.dumps({
        "id": "0099", "at": "2026-08-09T00:00:00+00:00", "layer": "M",
        "target": str(tmp_path / "old.md"),        # old single-target schema
        "post_edit_sha256": "abc", "committed": True, "reverted": False,
    }))
    with pytest.raises(refine_log.CorruptEntry):
        refine_log.undo()
    with pytest.raises(refine_log.CorruptEntry):
        refine_log.count_edits_today()


def test_a_first_memory_creates_its_parent_directory(tmp_path):
    """"Creating the file is part of the approved edit" — so is creating
    the directory it lives in. A project with no memory dir yet failed on
    its very first /refine proposal."""
    target = tmp_path / "projects" / "key" / "memory" / "quote-paths.md"
    refine_log.apply_edit("M", [(target, "---\nname: quote-paths\n---\n")], "r", "e")
    assert target.read_text().startswith("---")
