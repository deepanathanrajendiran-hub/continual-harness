"""Changelog and rollback for refine (spec §4.2 step 6).

Two-phase by design: record() snapshots the target before the edit,
commit_entry() appends the CHANGELOG line only after the edit succeeded.
An entry that was recorded but never committed represents a failed edit
and is invisible to undo().
"""

import json
from datetime import datetime, timezone

import paths


class NothingToUndo(Exception):
    """Raised when undo() finds no un-reverted committed entry."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entries() -> list[dict]:
    out = []
    for p in sorted(paths.undo_dir().glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def _write(entry: dict) -> None:
    (paths.undo_dir() / f"{entry['id']}.json").write_text(
        json.dumps(entry, indent=2) + "\n"
    )


def record(layer: str, target_path, rationale: str, evidence: str) -> dict:
    """Snapshot the target before an edit. Call this BEFORE writing."""
    target = str(target_path)
    existing = None
    try:
        with open(target, encoding="utf-8") as fh:
            existing = fh.read()
    except FileNotFoundError:
        existing = None

    seq = len(list(paths.undo_dir().glob("*.json"))) + 1
    entry = {
        "id": f"{seq:04d}",
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
    _write(entry)

    log = paths.changelog()
    if not log.exists():
        log.write_text("# Harness changelog\n\n")
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(
            f"{entry['at'][:10]} | {entry['layer']} | {entry['target']} | "
            f"{entry['rationale']} | {entry['evidence']}\n"
        )


def undo() -> dict:
    """Revert the most recent committed, un-reverted entry."""
    candidates = [e for e in _entries() if e["committed"] and not e["reverted"]]
    if not candidates:
        raise NothingToUndo("no committed harness edits left to revert")

    entry = candidates[-1]
    target = entry["target"]
    if entry["created_file"]:
        try:
            import os
            os.remove(target)
        except FileNotFoundError:
            pass
    else:
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(entry["previous_content"])

    entry["reverted"] = True
    entry["reverted_at"] = _now()
    _write(entry)

    with open(paths.changelog(), "a", encoding="utf-8") as fh:
        fh.write(f"{entry['reverted_at'][:10]} | REVERTED | {target} | "
                 f"undo of entry {entry['id']} | -\n")
    return entry
