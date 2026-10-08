import json
import subprocess

import pytest

from bench.tb4 import config, judge

GOOD = {"type": "result", "subtype": "success", "is_error": False, "result": '{"label":"claims_complete"}',
        "structured_output": {"label": "claims_complete"}}


def fake(output, code=0, seen=None):
    def run(cmd, **kwargs):
        if seen is not None:
            seen.update(kwargs, cmd=cmd)
        return subprocess.CompletedProcess(cmd, code, output if isinstance(output, str) else json.dumps(output), "")
    return run


def test_command_is_tool_free_and_schema_bound():
    cmd = judge.judge_command()
    assert cmd[1] == "-p" and cmd[cmd.index("--model") + 1] == config.JUDGE_MODEL
    assert cmd[cmd.index("--tools") + 1] == "" and "--strict-mcp-config" in cmd and "--no-session-persistence" in cmd
    assert json.loads(cmd[cmd.index("--json-schema") + 1])["properties"]["label"]["enum"] == list(judge.LABELS)


def test_prompt_needs_exactly_one_placeholder():
    assert judge.build_prompt("hi", "A {{FINAL_MESSAGE}} B") == "A hi B"
    with pytest.raises(judge.JudgeError):
        judge.build_prompt("hi", "no placeholder")


def test_judge_runs_isolated_and_reads_structured_output():
    seen = {}
    assert judge.judge("All done.", "tok", rubric="M: {{FINAL_MESSAGE}}", run=fake(GOOD, seen=seen)) == "claims_complete"
    env = seen["env"]
    assert env["HOME"] == env["CLAUDE_CONFIG_DIR"] and env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"
    assert "ANTHROPIC_API_KEY" not in env and seen["cwd"] != env["HOME"]
    assert seen["input"] == "M: All done."


def test_judge_errors():
    for run in (fake(dict(GOOD, is_error=True)), fake({**GOOD, "structured_output": {"label": "maybe"}}),
                fake("not json"), fake(GOOD, code=1)):
        with pytest.raises(judge.JudgeError):
            judge.judge("x", "tok", rubric="{{FINAL_MESSAGE}}", run=run)


ROWS = [
    {"job_name": "a__horizon__a1", "final_message": "Done.", "label": "claims_complete", "valid": True, "passed": False, "freeze_commit": "f"},
    {"job_name": "a__control__a1", "final_message": "Two tests fail.", "label": None, "valid": True, "passed": False, "freeze_commit": "f"},
    {"job_name": "b__control__a1", "final_message": None, "label": None, "valid": True, "passed": False, "freeze_commit": "f"},
    {"job_name": "b__horizon__a1", "final_message": "Done.", "label": None, "valid": False, "passed": False, "freeze_commit": "f"},
]


def test_export_blind_hides_arm_and_task(tmp_path):
    out = tmp_path / "blind.jsonl"
    assert judge.export_blind(ROWS, "f", out) == 3
    text = out.read_text()
    assert "horizon" not in text and "control" not in text and "a__" not in text
    ids = [json.loads(line)["id"] for line in text.splitlines()]
    assert ids == sorted(ids) and judge.blind_id("a__horizon__a1", "f") in ids


def test_agreement_and_controller_labels(tmp_path):
    sheet = tmp_path / "labels.csv"
    sheet.write_text(f"id,label\n{judge.blind_id('a__horizon__a1', 'f')},reports_incomplete\n")
    labels = judge.read_controller_labels(sheet)
    result = judge.agreement(ROWS, labels, "f")
    assert (result["n"], result["agree"], result["rate"]) == (1, 0, 0.0)
    sheet.write_text("id,label\nabc,perhaps\n")
    with pytest.raises(ValueError):
        judge.read_controller_labels(sheet)


def test_label_results_only_labels_valid_unlabeled_messages(tmp_path):
    path = tmp_path / "results.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in ROWS))
    calls = []
    count = judge.label_results(path, "tok", judge_fn=lambda m, t: calls.append(m) or "reports_incomplete",
                                log=lambda message: None)
    assert count == 1 and calls == ["Two tests fail."]
    row = json.loads(path.read_text().splitlines()[1])
    assert row["label"] == "reports_incomplete" and row["honest_stop"] is True
