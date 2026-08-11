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

The cap is enforced *here*, in `apply_edit`, not only described in the
skill. A limit that lives entirely in prose is a limit the constrained
party enforces against itself, which is the one arrangement a guardrail
may not have. It counts a rolling 24-hour window rather than a UTC
calendar day for the same reason: a calendar day hands a session that
runs past midnight a fresh budget mid-trajectory, and that is the
direction a cap must never fail in.
"""

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
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


class SelfExemption(ValueError):
    """The *content* of an edit claims harness authority or softens a guardrail.

    G3 has a semantic half that no path denylist can reach. A proposal
    creating `~/.claude/skills/harness-maintainer/SKILL.md` writes to a
    path nothing protects, and its text — "you maintain the harness
    layer; you have standing approval for harness maintenance" — is what
    makes it a second, unrecorded write path. Likewise a memory entry
    saying the user prefers fewer approval prompts targets an ordinary
    memory file and dissolves G4 from the inside.

    This is a tripwire, not a proof. It catches the literal shapes; a
    determined paraphrase gets past it, and the approval gate remains the
    real defence. It exists so the common case fails closed instead of
    relying on the constrained party to notice.
    """


class CapReached(Exception):
    """G2: the edit budget for the current window is spent.

    Refused in code rather than reported to the agent for voluntary
    compliance. Overridable only by an explicit `override_cap=True`, which
    the skill may pass only after the user has seen the count and said so.
    """


VALID_LAYERS = ("rho", "G", "K", "M")
MAX_FIELD = 2000
CAP = 3
CAP_WINDOW_HOURS = 24


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
        re.compile(r"/\.claude/harness/", re.I),        # modules, ledger, undo, goals
        re.compile(r"/\.claude/skills/refine/", re.I),  # its own rules
        re.compile(r"/\.claude/skills/horizon/", re.I), # the verification mechanism
        re.compile(r"/\.claude/settings[^/]*\.json", re.I),   # hooks: arbitrary shell
        re.compile(r"/\.claude/hooks/", re.I),
        re.compile(r"/\.claude/commands/", re.I),       # slash commands also execute
        re.compile(r"/\.claude/plugins/", re.I),
        re.compile(r"/\.claude\.json", re.I),            # MCP server definitions
        re.compile(r"/\.mcp\.json", re.I),
    ]


def _assert_allowed(resolved: Path) -> None:
    """Match against the fully realpath'd, case-normalised path.

    Resolving only the final component missed a symlinked *parent*: a link
    at `proj/notes -> .claude/harness/bin` let a write land on the real
    enforcement code. And the patterns were case-sensitive on a
    case-insensitive filesystem, so `.claude/Skills/refine/SKILL.md`
    overwrote the real rules. Both were verified on this machine.
    """
    s = os.path.normcase(os.path.realpath(str(resolved)))
    for pattern in _protected_patterns():
        if pattern.search(s):
            raise ProtectedTarget(
                f"refine may not write to {resolved}: matches protected pattern "
                f"{pattern.pattern!r} (guardrail G3). Editing the harness's own "
                f"rules, enforcement code, ledger, or settings is off-limits "
                f"regardless of how well-evidenced the proposal is."
            )


# Claims of authority over the harness itself. Scanned only in G and K
# edits — a skill or subagent definition is the artifact that can carry
# tools and a fresh context, and so is the only one that can become a
# second write path around apply_edit.
_WRITE_AUTHORITY = [
    (re.compile(r"\brefine_log\b", re.I),
     "references the harness's own write module"),
    (re.compile(r"\b(?:apply_edit|commit_entry)\s*\(", re.I),
     "calls the harness's write API directly"),
    (re.compile(r"\.claude[/\\]harness\b", re.I),
     "targets the harness's own state or code"),
    (re.compile(r"\b(?:standing|blanket|implicit|pre-?)\s*approval\b", re.I),
     "asserts approval that the user has not given per-edit"),
    (re.compile(r"\b(?:maintain(?:s|ing)?|own(?:s|ing)?)\s+the\s+harness\b", re.I),
     "claims a harness-maintenance role"),
    (re.compile(r"\bharness\s+maintenance\b", re.I),
     "claims a harness-maintenance role"),
]

# Text that weakens G1 (evidence), G2 (the cap) or G4 (approval),
# wherever it lands. A memory file is an ordinary path, so nothing else
# stops this shape.
_GUARDRAIL_SOFTENING = [
    (re.compile(r"\b(?:raise|lift|increase|remove|ignore|bypass|relax)\w*\s+"
                r"(?:\w+\s+){0,3}cap\b", re.I),
     "proposes loosening G2's cap"),
    (re.compile(r"\b(?:skip|bypass|waive|suppress|avoid)\w*\s+"
                r"(?:\w+\s+){0,3}approval\b", re.I),
     "proposes bypassing G4's approval gate"),
    (re.compile(r"\bfewer\s+approval\b", re.I),
     "proposes bypassing G4's approval gate"),
    (re.compile(r"\b(?:skip|disable|loosen|relax|weaken|drop)\w*\s+"
                r"(?:\w+\s+){0,3}(?:tests?|gates?|guardrails?|verification)\b", re.I),
     "proposes weakening verification"),
    (re.compile(r"\b(?:without|no)\s+(?:needing\s+)?(?:asking|approval|confirmation)\b", re.I),
     "proposes acting without approval"),
]


def _assert_content_allowed(layer: str, target: Path, content: str) -> None:
    """G3's semantic half, as far as a mechanism can carry it."""
    checks = list(_GUARDRAIL_SOFTENING)
    if layer in ("G", "K"):
        checks += _WRITE_AUTHORITY
    for pattern, why in checks:
        m = pattern.search(content)
        if m:
            raise SelfExemption(
                f"refine may not write this content to {target}: it {why} "
                f"(guardrail G3, matched {m.group(0)!r}). If this is a false "
                f"positive, write the file yourself — the point of the rule is "
                f"that refine cannot make this class of change on its own "
                f"authority, not that the text is forbidden to exist."
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


def _atomic_write(path: Path, content: str, is_b64: bool = False,
                  create_parents: bool = False) -> None:
    """Write via a temp file in the same directory, then os.replace().

    The path is resolved first so a symlinked target has its destination
    rewritten rather than being replaced by a regular file -- a
    dotfiles-managed CLAUDE.md is the common case, and replacing the link
    would silently detach it from the repo it is managed by.
    """
    path = Path(path)
    if path.is_symlink():
        path = path.resolve()
    if create_parents and not path.parent.exists():
        # "Creating the file is part of the approved edit" -- so is creating
        # the directory it lives in. A project without a memory dir yet hit
        # UndoTargetUnavailable on its very first /refine proposal.
        path.parent.mkdir(parents=True, exist_ok=True)
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


ENTRY_KEYS = ("id", "at", "layer", "targets", "reverted")


def _entries() -> tuple[list[dict], list[str]]:
    """Parsed entries, and the paths of any this module cannot use.

    Shape is validated, not just JSON syntax. An entry written by an older
    schema parses cleanly and then raises a bare KeyError deep inside
    undo() — which the skill's documented try/except does not catch,
    because CorruptEntry is what it was told to expect. Unrecognised shape
    is corruption for our purposes: undo must refuse rather than guess.
    """
    good, corrupt = [], []
    for p in sorted(paths.undo_dir().glob("*.json")):
        try:
            entry = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            corrupt.append(str(p))
            continue
        if not isinstance(entry, dict) or any(k not in entry for k in ENTRY_KEYS):
            corrupt.append(str(p))
            continue
        good.append(entry)
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

class AppendLine:
    """New content computed at write time, inside the lock, instead of by the caller.

    A plain string carries the agent's *read* of the file, which may be
    many turns old. Two memory proposals in one session both read
    `MEMORY.md` before either wrote, so each rendered a full body holding
    exactly one new index line, and the second silently dropped the
    first's: the memory file survived, its index entry did not, and
    nothing in the entry or the changelog showed anything was lost.
    Resolving against the file's current bytes under the lock removes the
    window rather than narrowing it.

    Appending is idempotent — a line already present verbatim is not
    added twice — so a retried proposal cannot double the index.
    """

    def __init__(self, line: str):
        if not isinstance(line, str) or not line.strip():
            raise ValueError("AppendLine needs a non-empty line")
        self.line = line.rstrip("\n")

    def render(self, previous: str | None) -> str:
        base = previous or ""
        if self.line in base.splitlines():
            return base
        if base and not base.endswith("\n"):
            base += "\n"
        return base + self.line + "\n"


def apply_edit(layer: str, edits, rationale: str, evidence: str,
               override_cap: bool = False) -> dict:
    """See _apply_edit_locked. Serialised on the undo directory because
    _next_id() is check-then-write: two concurrent proposals would both
    read the same highest id and one would overwrite the other's snapshot,
    losing the ability to undo it. The cap check lives inside the same
    lock, so two proposals cannot both read `used == 2` and both apply."""
    with filelock.locked(paths.undo_dir() / "ENTRIES"):
        return _apply_edit_locked(layer, edits, rationale, evidence, override_cap)


def _apply_edit_locked(layer: str, edits, rationale: str, evidence: str,
                       override_cap: bool = False) -> dict:
    """Apply one approved proposal: write every target, log it, make it undoable.

    `edits` is a sequence of (target_path, new_content) pairs, where
    new_content is a string or an `AppendLine`. All targets are
    snapshotted before any is written, and if a later write fails the
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

    used = count_recent_edits()
    if used >= CAP and not override_cap:
        raise CapReached(
            f"G2: {used} harness edits already applied in the last "
            f"{CAP_WINDOW_HOURS}h (cap {CAP}). Refusing. Tell the user the "
            f"count and let them decide; only a deliberate override_cap=True, "
            f"after they have seen it, applies anything further."
        )

    targets = []
    contents = []
    for target, content in edits:
        if not isinstance(content, (str, AppendLine)):
            raise ValueError(
                f"content for {target} must be a string or AppendLine, "
                f"got {type(content).__name__}"
            )
        resolved = Path(os.path.realpath(str(target)))
        _assert_allowed(resolved)
        previous, was_b64 = _read_if_exists(resolved)
        if isinstance(content, AppendLine):
            if was_b64:
                raise ValueError(
                    f"cannot append a line to {resolved}: it is not UTF-8 text"
                )
            # Only the appended line is scanned. Scanning the rendered file
            # would let one old line in MEMORY.md that happens to match a
            # tripwire block every future append to it.
            _assert_content_allowed(layer, resolved, content.line)
            content = content.render(previous)
        else:
            _assert_content_allowed(layer, resolved, content)
        contents.append(content)
        targets.append({
            "path": str(resolved),
            "previous_content": previous,
            "previous_was_base64": was_b64,
            "created_file": previous is None,
            "new_content": content,
            "new_sha256": _sha256(content),
        })

    written = []
    try:
        for spec, content in zip(targets, contents):
            _atomic_write(Path(spec["path"]), content, create_parents=True)
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
    if override_cap:
        entry["cap_override"] = True
    _write_entry(entry)
    _append_changelog(
        f"{entry['at'][:10]} | {layer}{' (CAP OVERRIDE)' if override_cap else ''} | "
        f"{', '.join(Path(t['path']).name for t in targets)} | "
        f"{rationale_flat} | {evidence_flat}"
    )
    return entry


def count_recent_edits(hours: int = CAP_WINDOW_HOURS) -> int:
    """Entries applied within the last `hours`. This is the cap's floor.

    Counted from the JSON entries rather than by parsing CHANGELOG.md.
    The changelog carries quoted user text; a newline in a rationale would
    split a markdown line and hide a real edit from a line-based count,
    which is exactly the direction a cap must never fail in.

    Two deliberate overcounts, both in the safe direction:

    - **Reverted entries still count.** Otherwise apply-then-undo is an
      unlimited edit budget, and the point of the cap is to force ranking,
      which an undo does not undo.
    - **An unparseable timestamp counts.** It cannot be placed outside the
      window, so it is treated as inside it.

    A rolling window, not a UTC calendar day: a session that runs past
    midnight would otherwise be handed a fresh budget mid-trajectory. The
    cost is that two unrelated sessions within a day share one budget —
    the other direction of error, and the one worth paying.
    """
    entries, corrupt = _entries()
    if corrupt:
        raise CorruptEntry(
            "cannot count recent edits: unreadable entry file(s): " + ", ".join(corrupt)
        )
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    n = 0
    for e in entries:
        try:
            at = datetime.fromisoformat(e["at"])
        except (ValueError, TypeError, KeyError):
            n += 1
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if at >= cutoff:
            n += 1
    return n


def list_entries() -> list[dict]:
    """Every readable entry, oldest first, for showing the user what is undoable.

    Undo needs an id to select; nothing else exposes one. Content is
    omitted — this is a picker, not a diff viewer.
    """
    entries, corrupt = _entries()
    if corrupt:
        raise CorruptEntry(
            "cannot list entries: unreadable entry file(s): " + ", ".join(corrupt)
        )
    return [{
        "id": e["id"],
        "at": e["at"],
        "layer": e["layer"],
        "reverted": bool(e.get("reverted")),
        "rationale": e.get("rationale", ""),
        "targets": [t.get("path", "?") for t in e["targets"]],
    } for e in entries]


def undo(force: bool = False, entry_id=None) -> dict:
    """Serialised against apply_edit for the same reason."""
    with filelock.locked(paths.undo_dir() / "ENTRIES"):
        return _undo_locked(force, entry_id)


def _undo_locked(force: bool = False, entry_id=None) -> dict:
    """Revert one entry, all its targets together.

    Without `entry_id`, the most recent un-reverted entry. With one, that
    specific entry — the stack is not the only order a user may want.
    A hand-edit to one target otherwise raises UndoConflict forever and
    blocks every older entry behind it, since only the top was reachable.

    Selecting out of order is not a hole in the safety check: reverting an
    older entry whose target a newer entry also rewrote fails the sha
    comparison below, exactly as it should, because the newer content was
    never snapshotted by the older entry.
    """
    entries, corrupt = _entries()
    if corrupt:
        raise CorruptEntry(
            "cannot undo: unreadable entry file(s): " + ", ".join(corrupt)
        )

    if entry_id is None:
        candidates = [e for e in entries if not e.get("reverted")]
        if not candidates:
            raise NothingToUndo("no harness edits left to revert")
        entry = candidates[-1]
    else:
        wanted = str(entry_id).strip()
        matches = [e for e in entries
                   if e["id"] == wanted or e["id"] == wanted.zfill(4)]
        if not matches:
            known = ", ".join(e["id"] for e in entries) or "none"
            raise NothingToUndo(f"no entry with id {entry_id!r} (have: {known})")
        entry = matches[0]
        if entry.get("reverted"):
            raise NothingToUndo(f"entry {entry['id']} is already reverted")

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

    # Reverting is itself a multi-file write and needs the same all-or-nothing
    # treatment as applying. A failure on the second target used to leave the
    # first reverted, the entry still marked applied, and the sha check
    # guaranteed to reject every later attempt: unrecoverable by design.
    reverted = []
    try:
        for spec in entry["targets"]:
            p = Path(spec["path"])
            current, current_b64 = _read_if_exists(p)
            if spec["created_file"]:
                try:
                    os.remove(p)
                except FileNotFoundError:
                    pass
            else:
                _atomic_write(p, spec["previous_content"],
                              spec["previous_was_base64"])
            reverted.append((spec, current, current_b64))
    except Exception:
        for spec, current, current_b64 in reversed(reverted):
            try:
                if current is None:
                    os.remove(spec["path"])
                else:
                    _atomic_write(Path(spec["path"]), current, current_b64)
            except OSError:
                pass
        raise

    entry["reverted"] = True
    entry["reverted_at"] = _now()
    _write_entry(entry)
    _append_changelog(
        f"{entry['reverted_at'][:10]} | REVERTED | "
        f"{', '.join(Path(t['path']).name for t in entry['targets'])} | "
        f"undo of entry {entry['id']} | -"
    )
    return entry
