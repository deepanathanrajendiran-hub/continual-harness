"""Apply, log and roll back harness edits for refine.

One approved proposal is one entry is one atomic write of N files.

That shape is deliberate, and replaces an earlier two-phase design where
the caller snapshotted a path, applied the edit itself with some other
tool, then told this module the edit had landed. Nothing connected the
three steps: the path snapshotted, the file actually edited, and the text
the user approved could all differ, and the module could not tell. A
mistyped path produced a changelog asserting an edit that never happened
and an `undo()` that "reverted" an untouched file, while the change that
did land had no snapshot at all. Here the module receives the approved
content and performs the write, so those cannot diverge.

Multi-file proposals are first class for the same reason. Writing a
memory file also means appending a line to `MEMORY.md`; if that second
write sits outside the entry, `undo()` removes the memory and leaves the
index advertising it.

The cap that `refine` enforces counts entries in `undo/*.json`, not lines
in `CHANGELOG.md`. The changelog is a rendering for humans and may
contain arbitrary quoted text; counting from it would mean a newline in a
rationale could hide a real edit from the cap.
"""

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import filelock
import paths


class NothingToUndo(Exception):
    """No committed, un-reverted entry remains."""


class CorruptEntry(Exception):
    """An entry file is unreadable or unparseable.

    undo() must never guess past damaged history -- silently skipping a
    corrupt entry could revert the wrong edit.
    """


class UndoConflict(Exception):
    """A target changed after its entry was written.

    undo() would otherwise discard whatever made that change, which was
    never snapshotted and is therefore unrecoverable. Pass force=True to
    override deliberately, after showing the user what they would lose.
    """


class UndoTargetUnavailable(Exception):
    """A target cannot be written because its location is gone.

    The recorded content is intact and the revert stays valid once the
    path is restored.
    """


class ProtectedTarget(ValueError):
    """The target is part of the harness's own enforcement or state.

    Guardrail G3: refine may not edit its own rules, the code enforcing
    them, the verification mechanism, the ledger the cap is counted from,
    or settings files that can run arbitrary commands.
    """


VALID_LAYERS = ("rho", "G", "K", "M")
MAX_FIELD = 2000


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def _clean_field(name: str, value: str) -> str:
    """Free text destined for the changelog rendering.

    Newlines and pipes are collapsed rather than rejected: `evidence` is
    documented as a quoted trajectory moment, and quoted terminal output is
    multi-line by nature, so rejecting them would fire constantly on
    legitimate input. The stored JSON entry keeps the original.
    """
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    flat = re.sub(r"\s*[\r\n]+\s*", " ", value).replace("|", "/")
    return flat[:MAX_FIELD]


def _protected_patterns() -> list[re.Pattern]:
    """Path patterns refine may never write to, in any project or in $HOME.

    Matched against the resolved absolute path, so `../`, a symlink, a
    lowercase spelling on a case-insensitive filesystem, or a hardlink all
    land on the same test. Patterns rather than a list of literal paths:
    the literal form only ever covered the current project, leaving every
    `--global` target -- and the ledger itself -- writable.
    """
    return [
        re.compile(r"/\.claude/harness/"),                 # modules, ledger, undo, goals
        re.compile(r"/\.claude/skills/refine/"),           # its own rules
        re.compile(r"/\.claude/skills/horizon/"),          # the verification mechanism
        re.compile(r"/\.claude/settings[^/]*\.json$"),     # hooks: arbitrary shell
        re.compile(r"/\.claude/hooks/"),
    ]


def _assert_allowed(resolved: Path) -> None:
    s = str(resolved)
    for pattern in _protected_patterns():
        if pattern.search(s):
            raise ProtectedTarget(
                f"refine may not write to {resolved}: matches protected pattern "
                f"{pattern.pattern!r} (guardrail G3). Editing the harness's own "
                f"rules, enforcement code, ledger, or settings is off-limits "
                f"regardless of how well-evidenced the proposal is."
            )


# --------------------------------------------------------------------------
# storage
# --------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_if_exists(path: Path):
    """Previous content, or None if the file does not exist.

    Binary or non-UTF-8 files are stored base64 so a rollback is still
    byte-exact; a latin-1 CLAUDE.md would otherwise crash the snapshot.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None, False
    except IsADirectoryError as e:
        raise ValueError(f"target is a directory, not a file: {path}") from e
    try:
        return raw.decode("utf-8"), False
    except UnicodeDecodeError:
        import base64
        return base64.b64encode(raw).decode("ascii"), True


def _atomic_write(path: Path, content: str, is_b64: bool = False) -> None:
    """Write via a temp file in the same directory, then os.replace().

    The path is resolved first so a symlinked target has its destination
    rewritten rather than being replaced by a regular file -- a
    dotfiles-managed CLAUDE.md is the common case, and replacing the link
    would silently detach it from the repo it is managed by.
    """
    path = Path(path)
    if path.is_symlink():
        path = path.resolve()
    if not path.parent.is_dir():
        raise UndoTargetUnavailable(
            f"cannot write {path}: parent directory {path.parent} does not exist"
        )
    data = content.encode("utf-8")
    if is_b64:
        import base64
        data = base64.b64decode(content)
    tmp = path.parent / f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _entries() -> tuple[list[dict], list[str]]:
    good, corrupt = [], []
    for p in sorted(paths.undo_dir().glob("*.json")):
        try:
            good.append(json.loads(p.read_text()))
        except (json.JSONDecodeError, OSError):
            corrupt.append(str(p))
    good.sort(key=lambda e: e.get("at", ""))
    return good, corrupt


def _write_entry(entry: dict) -> None:
    p = paths.undo_dir() / f"{entry['id']}.json"
    tmp = p.parent / f".{p.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
    try:
        tmp.write_text(json.dumps(entry, indent=2) + "\n")
        os.replace(tmp, p)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _next_id() -> str:
    """max(existing) + 1, so pruning a file never mints a colliding id."""
    highest = 0
    for p in paths.undo_dir().glob("*.json"):
        if p.stem.isdigit():
            highest = max(highest, int(p.stem))
    return f"{highest + 1:04d}"


def _append_changelog(line: str) -> None:
    log = paths.changelog()
    if not log.exists():
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("# Harness changelog\n\n")
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------

def apply_edit(layer: str, edits, rationale: str, evidence: str) -> dict:
    """See _apply_edit_locked. Serialised on the undo directory because
    _next_id() is check-then-write: two concurrent proposals would both
    read the same highest id and one would overwrite the other's snapshot,
    losing the ability to undo it."""
    with filelock.locked(paths.undo_dir() / "ENTRIES"):
        return _apply_edit_locked(layer, edits, rationale, evidence)


def _apply_edit_locked(layer: str, edits, rationale: str, evidence: str) -> dict:
    """Apply one approved proposal: write every target, log it, make it undoable.

    `edits` is a sequence of (target_path, new_content) pairs. All of them
    are snapshotted before any is written, and if a later write fails the
    earlier ones are rolled back, so an entry never describes a partially
    applied proposal.

    Returns the stored entry.
    """
    if layer not in VALID_LAYERS:
        raise ValueError(f"layer must be one of {VALID_LAYERS}, got {layer!r}")
    rationale_flat = _clean_field("rationale", rationale)
    evidence_flat = _clean_field("evidence", evidence)

    edits = [(Path(t), c) for t, c in edits]
    if not edits:
        raise ValueError("apply_edit needs at least one (target, content) pair")

    targets = []
    for target, content in edits:
        if not isinstance(content, str):
            raise ValueError(f"content for {target} must be a string")
        resolved = target.resolve() if target.is_symlink() else Path(os.path.abspath(target))
        _assert_allowed(resolved)
        previous, was_b64 = _read_if_exists(resolved)
        targets.append({
            "path": str(resolved),
            "previous_content": previous,
            "previous_was_base64": was_b64,
            "created_file": previous is None,
            "new_sha256": _sha256(content),
        })

    written = []
    try:
        for spec, (_, content) in zip(targets, edits):
            _atomic_write(Path(spec["path"]), content)
            written.append(spec)
    except Exception:
        for spec in reversed(written):          # roll back a partial proposal
            try:
                if spec["created_file"]:
                    os.remove(spec["path"])
                else:
                    _atomic_write(Path(spec["path"]), spec["previous_content"],
                                  spec["previous_was_base64"])
            except OSError:
                pass
        raise

    entry = {
        "id": _next_id(),
        "at": _now(),
        "layer": layer,
        "rationale": rationale,
        "evidence": evidence,
        "targets": targets,
        "reverted": False,
    }
    _write_entry(entry)
    _append_changelog(
        f"{entry['at'][:10]} | {layer} | "
        f"{', '.join(Path(t['path']).name for t in targets)} | "
        f"{rationale_flat} | {evidence_flat}"
    )
    return entry


def count_edits_today() -> int:
    """Non-reverted entries applied today, in UTC.

    Counted from the JSON entries rather than by parsing CHANGELOG.md.
    The changelog carries quoted user text; a newline in a rationale would
    split a markdown line and hide a real edit from a line-based count,
    which is exactly the direction a cap must never fail in.
    """
    entries, corrupt = _entries()
    if corrupt:
        raise CorruptEntry(
            "cannot count today's edits: unreadable entry file(s): " + ", ".join(corrupt)
        )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return sum(1 for e in entries if e.get("at", "")[:10] == today and not e.get("reverted"))


def undo(force: bool = False) -> dict:
    """Serialised against apply_edit for the same reason."""
    with filelock.locked(paths.undo_dir() / "ENTRIES"):
        return _undo_locked(force)


def _undo_locked(force: bool = False) -> dict:
    """Revert the most recent applied, un-reverted entry, all targets together."""
    entries, corrupt = _entries()
    if corrupt:
        raise CorruptEntry(
            "cannot undo: unreadable entry file(s): " + ", ".join(corrupt)
        )

    candidates = [e for e in entries if not e.get("reverted")]
    if not candidates:
        raise NothingToUndo("no harness edits left to revert")
    entry = candidates[-1]

    for spec in entry["targets"]:
        p = Path(spec["path"])
        if not p.parent.is_dir():
            raise UndoTargetUnavailable(
                f"cannot undo {p}: parent directory {p.parent} no longer exists"
            )
        if not force:
            current, _ = _read_if_exists(p)
            if current is None or _sha256(current) != spec["new_sha256"]:
                raise UndoConflict(
                    f"{p} changed since this edit was applied; refusing to undo. "
                    f"Show the user what would be lost before passing force=True."
                )

    for spec in entry["targets"]:
        if spec["created_file"]:
            try:
                os.remove(spec["path"])
            except FileNotFoundError:
                pass
        else:
            _atomic_write(Path(spec["path"]), spec["previous_content"],
                          spec["previous_was_base64"])

    entry["reverted"] = True
    entry["reverted_at"] = _now()
    _write_entry(entry)
    _append_changelog(
        f"{entry['reverted_at'][:10]} | REVERTED | "
        f"{', '.join(Path(t['path']).name for t in entry['targets'])} | "
        f"undo of entry {entry['id']} | -"
    )
    return entry
