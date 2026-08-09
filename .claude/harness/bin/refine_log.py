"""Changelog and rollback for refine (spec §4.2 step 6).

Two-phase by design: record() snapshots the target before the edit,
commit_entry() appends the CHANGELOG line only after the edit succeeded.
An entry that was recorded but never committed represents a failed edit
and is invisible to undo().
"""

import json
from datetime import datetime, timezone

import paths
import hashlib
import uuid
from pathlib import Path
import os


class NothingToUndo(Exception):
    """Raised when undo() finds no un-reverted committed entry."""

class CorruptEntry(Exception):
    """Raised when undo() finds an unreadable/unparseable entry file.

    undo() must never guess past corrupted history -- silently skipping
    a damaged entry could revert the wrong edit.
    """


class UndoConflict(Exception):
    """Raised when the target changed after its entry was committed.

    undo() would otherwise silently discard whatever wrote that change.
    Pass force=True to undo() to override deliberately.
    """


_VALID_LAYERS = ("rho", "G", "K", "M")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    """The project root, two levels above .claude/harness."""
    return paths.harness_root().parent.parent


def _protected_targets() -> set[Path]:
    """Files record() must never write to (G3 no-self-exemption): the
    skill's own guardrails and the independent verification judge, whose
    dispatch mechanism a self-write could flip to `fork` and turn into a
    self-grader. Resolved to absolute paths, not compared as raw strings,
    so a `../` in the caller's target cannot slip past.
    """
    claude_dir = _repo_root() / ".claude"
    return {
        (claude_dir / "skills" / "refine" / "SKILL.md").resolve(),
        (claude_dir / "skills" / "horizon" / "SKILL.md").resolve(),
    }


def _protected_bin_dir() -> Path:
    """`.claude/harness/bin/` -- the code that enforces the guardrails
    (this module and its siblings). A proposal to edit it is a proposal
    to edit the enforcement, not just the instructions."""
    return (paths.harness_root() / "bin").resolve()

def _hash_file(target) -> str | None:
    """sha256 of target's current bytes, or None if it does not exist."""
    try:
        with open(target, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except FileNotFoundError:
        return None

def _atomic_write(path: Path, content: str) -> None:
    """Write content to path so a failure never leaves a torn file.

    Writes to a temp file in the same directory, then os.replace()s it
    into place. POSIX rename is atomic, so path ends up either fully the
    old content or fully the new content -- never truncated partway.
    """
    path = Path(path)
    tmp = path.parent / f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _entries() -> tuple[list[dict], list[str]]:
    """Return (valid entries, paths of files that failed to parse).

    Corrupt files are reported, never silently dropped: undo() must not
    guess past damaged history.
    """
    out = []
    corrupt = []
    for p in sorted(paths.undo_dir().glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except (json.JSONDecodeError, OSError):
            corrupt.append(str(p))
    return out, corrupt


def _write(entry: dict) -> None:
    _atomic_write(
        paths.undo_dir() / f"{entry['id']}.json",
        json.dumps(entry, indent=2) + "\n",
    )

def _next_id() -> str:
    """Smallest unused sequence id, derived from the max id on disk.

    Deriving from a count instead would reuse an id after any entry file
    is removed, letting _write() silently overwrite a surviving entry and
    destroy its previous_content.
    """
    seq = 0
    for p in paths.undo_dir().glob("*.json"):
        if p.stem.isdigit():
            seq = max(seq, int(p.stem))
    return f"{seq + 1:04d}"


def record(layer: str, target_path, rationale: str, evidence: str) -> dict:
    """Snapshot the target before an edit. Call this BEFORE writing.

    Raises ValueError if `layer` is not one of the four harness codes
    (`rho`, `G`, `K`, `M`), or contains a `|` or a newline (either would
    corrupt CHANGELOG field parsing). This is what keeps the `REVERTED`
    sentinel unconstructible through record(): the G2 cap pre-flight
    (refine SKILL.md Step 4) skips any CHANGELOG line whose layer field
    reads `REVERTED`, so a caller able to pass layer="REVERTED" could
    produce a real, committed, undoable edit invisible to the counter.

    Raises ValueError if the resolved target is refine's or horizon's own
    SKILL.md, or anything under `.claude/harness/bin/` -- G3's no-self-
    exemption rule, enforced here (not only in prose) so it cannot be
    bypassed by a proposal that simply doesn't mention it.
    """
    if layer not in _VALID_LAYERS or "|" in layer or "\n" in layer:
        raise ValueError(
            f"layer must be one of {_VALID_LAYERS!r}, got {layer!r}"
        )

    resolved = Path(target_path).resolve()
    protected_bin = _protected_bin_dir()
    if resolved in _protected_targets() or resolved == protected_bin or protected_bin in resolved.parents:
        raise ValueError(
            f"refine may not write to {resolved}: it enforces or verifies "
            "the harness guardrails (G3 no-self-exemption)"
        )

    target = str(target_path)
    existing = None
    try:
        with open(target, encoding="utf-8") as fh:
            existing = fh.read()
    except FileNotFoundError:
        existing = None

    entry = {
        "id": _next_id(),
        "at": _now(),
        "layer": layer,
        "target": target,
        "rationale": rationale,
        "evidence": evidence,
        "previous_content": existing,
        "created_file": existing is None,
        "committed": False,
        "reverted": False,
    }
    _write(entry)
    return entry


def commit_entry(entry_id: str) -> None:
    """Mark the edit as applied and append its CHANGELOG line."""
    path = paths.undo_dir() / f"{entry_id}.json"
    entry = json.loads(path.read_text())
    entry["committed"] = True
    entry["post_edit_sha256"] = _hash_file(entry["target"])
    _write(entry)

    log = paths.changelog()
    if not log.exists():
        log.write_text("# Harness changelog\n\n")
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(
            f"{entry['at'][:10]} | {entry['layer']} | {entry['target']} | "
            f"{entry['rationale']} | {entry['evidence']}\n"
        )


def undo(force: bool = False) -> dict:
    """Revert the most recent committed, un-reverted entry.

    Raises CorruptEntry if any undo-log entry file is unreadable -- undo
    must never guess past damaged history. Raises UndoConflict if the
    target changed since the entry was committed, unless force=True.
    """
    entries, corrupt = _entries()
    if corrupt:
        raise CorruptEntry(
            "cannot undo: unreadable entry file(s): " + ", ".join(corrupt)
        )

    candidates = [e for e in entries if e["committed"] and not e["reverted"]]
    if not candidates:
        raise NothingToUndo("no committed harness edits left to revert")

    entry = candidates[-1]
    target = entry["target"]

    if not force:
        current_hash = _hash_file(target)
        expected_hash = entry.get("post_edit_sha256")
        if current_hash != expected_hash:
            raise UndoConflict(
                f"target changed since commit, refusing to undo: {target}"
            )

    if entry["created_file"]:
        try:
            os.remove(target)
        except FileNotFoundError:
            pass
    else:
        _atomic_write(Path(target), entry["previous_content"])

    entry["reverted"] = True
    entry["reverted_at"] = _now()
    _write(entry)

    with open(paths.changelog(), "a", encoding="utf-8") as fh:
        fh.write(f"{entry['reverted_at'][:10]} | REVERTED | {target} | "
                 f"undo of entry {entry['id']} | -\n")
    return entry
