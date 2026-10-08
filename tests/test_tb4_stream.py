import json

from bench.tb4 import stream

SUMMARY = {"slug": "fix-parser", "status": "active", "gate": {"kind": "command", "value": "pytest -q"},
           "budget": {"max_turns": 200, "max_minutes": 100},
           "used": {"turns": 0, "started": "2026-10-07T12:00:00+00:00"}, "budget_exhausted": False}


def use(id_, command, parent=None):
    return {"type": "assistant", "parent_tool_use_id": parent, "message": {"content": [
        {"type": "tool_use", "id": id_, "name": "Bash", "input": {"command": command}}]}}


def res(id_, content, is_error=False, parent=None):
    return {"type": "user", "parent_tool_use_id": parent, "message": {"content": [
        {"type": "tool_result", "tool_use_id": id_, "content": content, "is_error": is_error}]}}


def say(text, parent=None):
    return {"type": "assistant", "parent_tool_use_id": parent,
            "message": {"content": [{"type": "text", "text": text}]}}


def limit(status="allowed", five=0.5, seven=0.2):
    return {"type": "rate_limit_event", "rate_limit_info": {"status": status, "unifiedWindows": {
        "five_hour": {"utilization": five, "resetsAt": 1000}, "seven_day": {"utilization": seven, "resetsAt": 9000}}}}


START = 'python3 "$HARNESS" --runtime claude --project "/app" start "Fix" --gate "pytest -q" --max-turns 200 --max-minutes 100'


def test_parse_lines_keeps_raw_lines():
    events = stream.parse_lines('{"type": "system", "subtype": "init", "claude_code_version": "2.1.293", "model": "m"}\nnpm WARN x\n\n')
    assert events[1] == {"type": "_raw", "text": "npm WARN x"}
    assert stream.init_info(events) == {"version": "2.1.293", "model": "m"}


def test_result_record_is_the_first_result():
    events = [{"type": "result", "result": "first"}, {"type": "result", "result": "late"}]
    assert stream.result_record(events)["result"] == "first"
    assert stream.result_record([say("x")]) is None


def test_rate_limit_info_reads_the_last_event():
    info = stream.rate_limit_info([limit(five=0.1), limit(five=0.7, seven=0.3)])
    assert info == {"status": "allowed", "five_hour": 0.7, "five_hour_resets_at": 1000,
                    "seven_day": 0.3, "seven_day_resets_at": 9000}
    assert stream.rate_limit_info([say("x")]) is None


def test_json_objects_finds_top_level_objects_only():
    text = 'Exit code 2\n{"a": {"b": 1}} trailing {not json} {"c": 2}'
    assert stream.json_objects(text) == [{"a": {"b": 1}}, {"c": 2}]


def test_horizon_start_via_variable_and_flags():
    calls = stream.horizon_calls([use("t1", START), res("t1", json.dumps(SUMMARY, indent=2))])
    assert len(calls) == 1
    assert calls[0]["subcommands"] == ["start"]
    assert calls[0]["summaries"][0]["slug"] == "fix-parser" and calls[0]["errors"] == []


def test_refused_start_piped_through_tail_is_not_a_goal():
    command = START + " 2>&1 | tail -n 5"
    refusal = 'Exit code 2\n{"error": "GateUnsound", "message": "gate discards the exit status"}'
    calls = stream.horizon_calls([use("t1", command), res("t1", refusal, is_error=True)])
    assert calls[0]["summaries"] == []
    assert calls[0]["errors"][0]["error"] == "GateUnsound"


def test_argparse_usage_text_yields_nothing():
    calls = stream.horizon_calls([use("t1", "python3 /x/scripts/harness.py --runtime claude start"),
                                  res("t1", "usage: harness.py start [-h] ...\nerror: one of the arguments --gate --coverage is required", True)])
    assert calls[0]["summaries"] == [] and calls[0]["errors"] == []


def test_check_exit_two_summary_still_counts_and_literal_path_works():
    body = dict(SUMMARY, error="gate timed out after 600s: pytest -q")
    calls = stream.horizon_calls([use("t1", "python3 /logs/agent/sessions/skills/horizon/scripts/harness.py --runtime claude --project /app check fix-parser --did x --next y"),
                                  res("t1", json.dumps(body, indent=2), True)])
    assert calls[0]["subcommands"] == ["check"] and calls[0]["summaries"][0]["error"].startswith("gate timed out")


def test_unrelated_commands_and_subagent_flag():
    events = [use("t1", "git status && pytest -q"), res("t1", "ok"),
              use("t2", 'python3 "$HARNESS" --runtime claude --project /app status fix-parser', parent="toolu_p"),
              res("t2", json.dumps(SUMMARY), parent="toolu_p")]
    calls = stream.horizon_calls(events)
    assert len(calls) == 1 and calls[0]["subagent"] is True


def test_retried_api_error_is_not_terminal():
    events = [{"type": "_raw", "text": "API Error: 529 overloaded, retrying"}, say("continuing"), {"type": "result", "is_error": False}]
    assert stream.terminal_api_error(events) is None


def test_trailing_rejected_rate_limit_is_terminal():
    events = [say("working"), limit(status="rejected")]
    assert "rejected" in stream.terminal_api_error(events)


def test_trailing_usage_limit_line_is_terminal_even_after_subagent_text():
    events = [say("working"), {"type": "_raw", "text": "You've hit your usage limit · resets 4pm"},
              say("subagent still talking", parent="toolu_p")]
    assert "usage limit" in stream.terminal_api_error(events)


def test_clean_run_has_no_terminal_error():
    assert stream.terminal_api_error([say("done"), limit(), {"type": "result", "is_error": False}]) is None


def test_ledger_candidates_order_and_dedupe():
    doctor = {"runtime": "claude", "project": "/workspace", "implementation": "/x", "state": "/workspace/.claude/harness"}
    events = [use("t1", 'python3 "$HARNESS" --runtime claude --project /workspace doctor'), res("t1", json.dumps(doctor)),
              use("t2", 'PROJECT=/workspace; python3 "$HARNESS" --runtime claude --project "$PROJECT" status'), res("t2", "{}"),
              use("t3", 'python3 "$HARNESS" --runtime claude --project "$P" status'), res("t3", "{}")]
    assert stream.ledger_candidates(events, "/workspace") == ["/workspace/.claude/harness"]
    assert stream.ledger_candidates([], "/app/") == ["/app/.claude/harness"]
