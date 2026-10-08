"""Label final messages with an isolated, tool-free claude -p call; export blind sheets for the controller."""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from bench.tb4 import config, score
from bench.tb4 import run as runner

LABELS = ("claims_complete", "reports_incomplete", "neither")
SCHEMA = {"type": "object", "properties": {"label": {"type": "string", "enum": list(LABELS)}},
          "required": ["label"], "additionalProperties": False}


class JudgeError(RuntimeError):
    pass


def judge_command(model: str = config.JUDGE_MODEL) -> list:
    return [runner.claude_bin(), "-p", "--model", model, "--tools", "", "--disable-slash-commands",
            "--no-session-persistence", "--strict-mcp-config", "--output-format", "json",
            "--json-schema", json.dumps(SCHEMA, separators=(",", ":"))]


def build_prompt(message: str, rubric: str) -> str:
    if rubric.count("{{FINAL_MESSAGE}}") != 1:
        raise JudgeError("the rubric must contain exactly one {{FINAL_MESSAGE}}")
    return rubric.replace("{{FINAL_MESSAGE}}", message)


def judge(message: str, token: str, *, rubric=None, run=subprocess.run) -> str:
    rubric = rubric if rubric is not None else (config.PROMPTS / "judge.md").read_text()
    prompt = build_prompt(message, rubric)
    with tempfile.TemporaryDirectory() as cfg, tempfile.TemporaryDirectory() as cwd:
        proc = run(judge_command(), input=prompt, capture_output=True, text=True,
                   env=runner.isolated_claude_env(token, cfg), cwd=cwd, timeout=300)
    try:
        out = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as error:
        raise JudgeError(f"judge printed no JSON: {(proc.stderr or '')[:300]}") from error
    if proc.returncode != 0 or out.get("is_error"):
        raise JudgeError(f"judge failed: {out.get('subtype')} {out.get('api_error_status')}")
    label = (out.get("structured_output") or {}).get("label")
    if label not in LABELS:
        raise JudgeError(f"unexpected label {label!r}")
    return label


def blind_id(job_name: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{job_name}".encode()).hexdigest()[:12]


def export_blind(rows, salt: str, path: Path) -> int:
    items = sorted(({"id": blind_id(r["job_name"], salt), "message": r["final_message"]}
                    for r in rows if r.get("final_message")), key=lambda item: item["id"])
    path.write_text("".join(json.dumps(item) + "\n" for item in items))
    return len(items)


def read_controller_labels(path: Path) -> dict:
    with open(path, newline="") as handle:
        labels = {row["id"]: row["label"] for row in csv.DictReader(handle)}
    unknown = {k: v for k, v in labels.items() if v not in LABELS}
    if unknown:
        raise ValueError(f"unknown labels: {unknown}")
    return labels


def agreement(rows, controller: dict, salt: str) -> dict:
    judged = [(blind_id(r["job_name"], salt), r["label"]) for r in rows if r.get("final_message") and r.get("label")]
    compared = [(i, label, controller[i]) for i, label in judged if i in controller]
    agree = sum(1 for _, a, b in compared if a == b)
    return {"n": len(compared), "agree": agree, "rate": agree / len(compared) if compared else None,
            "disagreements": sorted(i for i, a, b in compared if a != b),
            "missing": sorted(i for i, _ in judged if i not in controller)}


def _read_rows(path: Path) -> list:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_rows(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def label_results(path: Path, token: str, *, judge_fn=judge, log=print) -> int:
    rows = _read_rows(path)
    labeled = 0
    for row in rows:
        if row.get("valid") and row.get("final_message") and row.get("label") is None:
            row.update(score.apply_label(row, judge_fn(row["final_message"], token)))
            _write_rows(path, rows)
            labeled += 1
            log(f"labeled {row['job_name']}: {row['label']}")
    return labeled


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("run", "export-blind", "agreement"):
        p = sub.add_parser(name)
        p.add_argument("--results", type=Path, required=True)
        if name != "run":
            p.add_argument("--out", type=Path, required=True)
        if name == "agreement":
            p.add_argument("--labels", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == "run":
        print(label_results(args.results, runner.read_token()))
        return 0
    rows = _read_rows(args.results)
    salt = rows[0]["freeze_commit"]
    if args.action == "export-blind":
        print(export_blind(rows, salt, args.out))
    else:
        result = agreement(rows, read_controller_labels(args.labels), salt)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
