"""Turn a real trial's evidence into a small, token-free scorer fixture."""
import argparse
import json
import shutil
import sys
from pathlib import Path

from bench.tb4 import run, stream

KEEP_TAIL = 20


def _ids(event) -> set:
    content = (event.get("message") or {}).get("content")
    blocks = content if isinstance(content, list) else []
    return ({b.get("id") for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use"}
            | {b.get("tool_use_id") for b in blocks if isinstance(b, dict) and b.get("type") == "tool_result"})


def reduce_events(events) -> list:
    keep = set()
    for _, block in stream.tool_uses(events):
        command = str((block.get("input") or {}).get("command") or "")
        if block.get("name") in ("Task", "Agent") or "harness.py" in command or "HARNESS" in command or "--runtime" in command:
            keep.add(block.get("id"))
    tail = len(events) - KEEP_TAIL
    return [e for i, e in enumerate(events)
            if e.get("type") in ("system", "result", "rate_limit_event", "error", "_raw") or _ids(e) & keep or i >= tail]


def _write_events(path: Path, events) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join((e["text"] if e.get("type") == "_raw" else json.dumps(e)) + "\n" for e in events))


def make_fixture(record_path: Path, dest: Path, token: str) -> Path:
    if dest.exists():
        raise FileExistsError(dest)
    record = json.loads(record_path.read_text())
    trial_dir = Path(record["trial_dir"])
    out = dest / "trial"
    (out / "agent").mkdir(parents=True)
    shutil.copy2(trial_dir / "result.json", out / "result.json")
    _write_events(out / "agent" / "claude-code.txt",
                  reduce_events(stream.read_events(trial_dir / "agent" / "claude-code.txt")))
    skill = trial_dir / "agent/sessions/skills/horizon/SKILL.md"
    if skill.is_file():
        (out / "agent/sessions/skills/horizon").mkdir(parents=True)
        shutil.copy2(skill, out / "agent/sessions/skills/horizon/SKILL.md")
    for session in sorted((trial_dir / "agent/sessions/projects").rglob("*.jsonl")):
        tool_events = [e for e in stream.read_events(session) if any(True for _ in stream.tool_uses([e]))]
        _write_events(out / session.relative_to(trial_dir), tool_events)
    ledger = dict(record.get("ledger") or {})
    copied = {}
    for i, (path, host_dir) in enumerate((ledger.get("copied") or {}).items()):
        shutil.copytree(host_dir, dest / "ledgers" / str(i))
        copied[path] = f"ledgers/{i}"
    ledger["copied"] = copied
    (dest / "record.json").write_text(json.dumps({**record, "trial_dir": "trial", "ledger": ledger},
                                                 indent=2, sort_keys=True) + "\n")
    leaks = [p for p in dest.rglob("*") if p.is_file() and token in p.read_text(errors="ignore")]
    if leaks:
        shutil.rmtree(dest)
        raise ValueError(f"token found in fixture files: {leaks}")
    return dest


def load_fixture(dest: Path) -> dict:
    record = json.loads((dest / "record.json").read_text())
    record["trial_dir"] = str(dest / record["trial_dir"])
    ledger = record.get("ledger") or {}
    ledger["copied"] = {k: str(dest / v) for k, v in (ledger.get("copied") or {}).items()}
    record["ledger"] = ledger
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    print(make_fixture(args.record, args.out, run.read_token()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
