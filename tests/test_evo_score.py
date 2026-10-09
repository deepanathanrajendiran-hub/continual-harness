import json

import pytest

from bench.evo import score

TASK = "theme_d0_w0_demo_task"
INIT = {"type": "system", "subtype": "init", "claude_code_version": "2.1.293", "model": "claude-sonnet-5-5"}
USAGE = {"claude-sonnet-5-5": {"inputTokens": 10, "outputTokens": 20, "cacheReadInputTokens": 30,
                               "cacheCreationInputTokens": 40, "costUSD": 1.5}}
HARNESS = 'python3 "$HARNESS" --runtime claude --project /app '


def done(text="All requirements are met.", cost=1.5, usage=USAGE):
    return {"type": "result", "subtype": "success", "is_error": False, "result": text,
            "total_cost_usd": cost, "modelUsage": usage}


def say(text):
    return {"type": "assistant", "parent_tool_use_id": None,
            "message": {"content": [{"type": "text", "text": text}]}}


def use(id_, command, name="Bash", key="command"):
    return {"type": "assistant", "parent_tool_use_id": None, "message": {"content": [
        {"type": "tool_use", "id": id_, "name": name, "input": {key: command}}]}}


def res(id_, content, is_error=False):
    return {"type": "user", "parent_tool_use_id": None, "message": {"content": [
        {"type": "tool_result", "tool_use_id": id_, "content": content, "is_error": is_error}]}}


def goal(slug, status, started="2026-10-09T12:01:00+00:00", turns=1):
    return {"slug": slug, "goal": slug, "cwd": "/app", "status": status,
            "gate": {"kind": "command", "value": "make test"}, "watch_paths": ["/app"],
            "budget": {"max_turns": 200, "max_minutes": 25}, "used": {"turns": turns, "started": started},
            "checkpoints": [], "subagents": []}


def start_call(id_, slug):
    return [use(id_, HARNESS + f'start "{slug}" --gate "make test" --max-turns 200 --max-minutes 25'),
            res(id_, json.dumps(goal(slug, "active", turns=0), indent=2))]


def write_task(runs, names):
    task_dir = runs / "copies" / "agent" / TASK
    task_dir.mkdir(parents=True, exist_ok=True)
    steps = "".join(f'[[steps]]\nname = "{n}"\n\n[steps.agent]\ntimeout_sec = 1800\n\n' for n in names)
    (task_dir / "task.toml").write_text('version = "1.0"\n\n[agent]\ntimeout_sec = 1800\n\n' + steps)


def lines(events):
    return "\n".join(e["text"] if e.get("type") == "_raw" else json.dumps(e) for e in events) + "\n"


def make_job(runs, names, rounds, *, arm="horizon", phase="main", attempt=1, valid=True):
    """A finished Harbor 0.24.0 multi-step job on disk; `rounds` holds one spec per step that ran."""
    write_task(runs, names)
    job = f"{phase}__{TASK}__{arm}__a{attempt}"
    trial_dir = runs / "jobs" / job / "theme_d0_w0_demo_tas__AbC1234"
    step_results = []
    for index, (name, spec) in enumerate(zip(names, rounds)):
        step_dir = trial_dir / "steps" / name
        (step_dir / "agent").mkdir(parents=True)
        (step_dir / "agent" / "claude-code.txt").write_text(lines(spec.get("events", [])))
        if spec.get("sessions"):
            session = step_dir / "agent" / "sessions" / "projects" / "-app" / "s1.jsonl"
            session.parent.mkdir(parents=True)
            session.write_text(lines(spec["sessions"]))
        (step_dir / "verifier").mkdir()
        reward = spec.get("reward", 1)
        if reward is not None:
            (step_dir / "verifier" / "reward.txt").write_text(f"{reward}\n")
        if spec.get("cases"):
            passed, total = spec["cases"]
            (step_dir / "verifier" / "test-stdout.txt").write_text(
                f"running checks\nCASE_SUMMARY total_cases={total} success_count={passed}\n")
        if spec.get("goals") is not None:
            goals = step_dir / "artifacts" / "logs" / "artifacts" / name / "harness" / "goals"
            goals.mkdir(parents=True)
            for item in spec["goals"]:
                (goals / f"{item['slug']}.json").write_text(json.dumps(item))
        started, finished = f"2026-10-09T{12 + index:02d}:00:00Z", f"2026-10-09T{12 + index:02d}:10:00Z"
        exception = spec.get("exception")
        step_results.append({
            "step_name": name, "agent_result": None,
            "verifier_result": {"rewards": {"reward": reward}} if reward is not None else None,
            "exception_info": {"exception_type": exception, "exception_message": "x",
                               "exception_traceback": "", "occurred_at": finished} if exception else None,
            "agent_execution": {"started_at": started, "finished_at": finished},
            "verifier": {"started_at": finished, "finished_at": finished}})
    (trial_dir / "result.json").write_text(json.dumps({
        "task_name": TASK, "trial_name": trial_dir.name, "step_results": step_results,
        "verifier_result": None, "exception_info": None}))
    return {"job_name": job, "phase": phase, "task": TASK, "arm": arm, "attempt": attempt,
            "job_dir": str(runs / "jobs" / job), "trial_dir": str(trial_dir),
            "valid": valid, "invalid_reason": None if valid else "usage_limit"}


def write_records(runs, *records):
    (runs / "records").mkdir(exist_ok=True)
    for record in records:
        (runs / "records" / f"{record['job_name']}.json").write_text(json.dumps(record))


def test_one_row_per_round_with_reward_cases_time_and_tokens(tmp_path):
    names = ["r1", "r2", "r3"]
    record = make_job(tmp_path, names, [
        {"events": [INIT, say("work"), done()], "reward": 1, "cases": (4, 4)},
        {"events": [INIT, done("Partly done.")], "reward": 0, "cases": (3, 4)},
        {"events": [INIT, done()], "reward": 1.0},
    ])
    rows = score.round_rows(record, runs=tmp_path)
    assert [list(r) for r in rows] == [list(score.ROW_FIELDS)] * 3
    assert [(r["round"], r["round_index"]) for r in rows] == [("r1", 1), ("r2", 2), ("r3", 3)]
    assert [(r["reward"], r["passed"]) for r in rows] == [(1.0, True), (0.0, False), (1.0, True)]
    assert [(r["cases_passed"], r["cases_total"]) for r in rows] == [(4, 4), (3, 4), (None, None)]
    first = rows[0]
    assert {k: first[k] for k in ("job_name", "phase", "task", "arm", "attempt")} == {
        "job_name": f"main__{TASK}__horizon__a1", "phase": "main", "task": TASK, "arm": "horizon", "attempt": 1}
    assert (first["agent_sec"], first["tokens_in"], first["tokens_out"], first["cost_usd"]) == (600.0, 80, 20, 1.5)
    assert (first["final_message"], rows[1]["final_message"]) == ("All requirements are met.", "Partly done.")
    assert (first["result_records"], first["label"], first["audit_flags"]) == (1, None, [])


def test_rounds_after_the_chain_stopped_are_failed_not_reached_rows(tmp_path):
    names = ["r1", "r2", "r3", "r4"]
    record = make_job(tmp_path, names, [
        {"events": [INIT, done()], "reward": 1},
        {"events": [INIT, say("work")], "reward": None, "exception": "NonZeroAgentExitCodeError"},
    ])
    rows = score.round_rows(record, runs=tmp_path)
    assert [r["round"] for r in rows] == names
    aborted = rows[1]
    assert (aborted["reward"], aborted["passed"], aborted["final_message"], aborted["end_reason"]) == (
        0.0, False, None, "no goal")
    for row in rows[2:]:
        assert (row["reward"], row["passed"], row["end_reason"]) == (0.0, False, "not reached")
        assert (row["final_message"], row["result_records"], row["goal_slugs"], row["agent_sec"]) == (None, 0, [], None)


def test_a_valid_record_without_a_readable_trial_result_is_an_error_not_all_failed(tmp_path):
    write_task(tmp_path, ["r1", "r2"])
    record = {"job_name": f"main__{TASK}__control__a1", "phase": "main", "task": TASK, "arm": "control",
              "attempt": 1, "trial_dir": None, "valid": True}
    with pytest.raises(ValueError, match=record["job_name"]):
        score.round_rows(record, runs=tmp_path)
    moved = make_job(tmp_path, ["r1", "r2"], [{"events": [INIT, done()]}])
    (tmp_path / "jobs" / moved["job_name"]).rename(tmp_path / "elsewhere")  # e.g. RUNS moved to another disk
    with pytest.raises(ValueError, match=moved["job_name"]):
        score.round_rows(moved, runs=tmp_path)
    # an invalid record never had to have a result: its rounds are not reached
    rows = score.round_rows(dict(record, valid=False), runs=tmp_path)
    assert [(r["round_index"], r["end_reason"], r["reward"]) for r in rows] == [
        (1, "not reached", 0.0), (2, "not reached", 0.0)]


def test_a_timed_out_round_fails_and_ignores_a_late_result_line(tmp_path):
    record = make_job(tmp_path, ["r1"], [
        {"events": [INIT, say("work"), done("late claim")], "reward": 0, "exception": "AgentTimeoutError"}])
    row = score.round_rows(record, runs=tmp_path)[0]
    assert (row["reward"], row["passed"], row["result_records"]) == (0.0, False, 1)
    assert (row["final_message"], row["tokens_in"], row["tokens_out"], row["cost_usd"]) == (None, None, None, None)


def test_every_result_record_is_counted_and_the_last_one_is_the_answer(tmp_path):
    later = {"claude-sonnet-5-5": {"inputTokens": 20, "outputTokens": 40, "cacheReadInputTokens": 60,
                                   "cacheCreationInputTokens": 80},
             "claude-haiku-5": {"inputTokens": 1, "outputTokens": 2}}
    events = [INIT, done("Interim: the review is still running."), say("more"), done("All done.", 2.5, later)]
    row = score.round_rows(make_job(tmp_path, ["r1"], [{"events": events}]), runs=tmp_path)[0]
    assert (row["result_records"], row["final_message"]) == (2, "All done.")
    assert (row["tokens_in"], row["tokens_out"], row["cost_usd"]) == (161, 42, 2.5)


def test_horizon_calls_and_a_start_are_read_per_round(tmp_path):
    first = [INIT, *start_call("t1", "fix-parser"),
             use("t2", HARNESS + "check fix-parser --did a --next b"), res("t2", "{}"), done()]
    second = [INIT, use("t3", "python3 tools/harness.py status"), res("t3", "ok"), done()]
    rows = score.round_rows(make_job(tmp_path, ["r1", "r2"], [{"events": first}, {"events": second}]),
                            runs=tmp_path)
    assert (rows[0]["horizon_calls"], rows[0]["horizon_started"]) == (2, True)
    # no ledger copy was collected, so the start call's own summary is the evidence
    assert (rows[0]["goal_slugs"], rows[0]["goal_status"], rows[0]["end_reason"]) == (
        ["fix-parser"], {"fix-parser": "active"}, "active")
    # a task's own harness.py is not the Horizon CLI
    assert (rows[1]["horizon_calls"], rows[1]["horizon_started"], rows[1]["end_reason"]) == (0, False, "no goal")


def test_a_refused_start_is_no_goal(tmp_path):
    events = [INIT, use("t1", HARNESS + 'start "Fix" --gate "make test | tail -3"'),
              res("t1", '{"error": "GateUnsound", "message": "discards the exit status"}', True), done()]
    row = score.round_rows(make_job(tmp_path, ["r1"], [{"events": events}]), runs=tmp_path)[0]
    assert (row["horizon_calls"], row["horizon_started"], row["goal_slugs"], row["end_reason"]) == (
        1, False, [], "no goal")


def test_goals_are_attributed_to_the_round_that_created_or_changed_them(tmp_path):
    first_done = goal("first-request", "complete", started="2026-10-09T12:01:00+00:00", turns=3)
    second_active = goal("second-request", "active", started="2026-10-09T13:02:00+00:00")
    record = make_job(tmp_path, ["r1", "r2", "r3"], [
        {"events": [INIT, *start_call("t1", "first-request"), done()], "goals": [first_done]},
        {"events": [INIT, *start_call("t2", "second-request"), done()], "goals": [first_done, second_active]},
        {"events": [INIT, use("t3", HARNESS + "status"), res("t3", json.dumps([first_done, second_active])),
                    done()], "goals": [first_done, second_active]},
    ])
    rows = score.round_rows(record, runs=tmp_path)
    # the ledger copy at the end of the round wins over the start call's "active"
    assert (rows[0]["goal_slugs"], rows[0]["goal_status"], rows[0]["end_reason"]) == (
        ["first-request"], {"first-request": "complete"}, "complete")
    # round 1's finished goal is still in round 2's ledger but is not round 2's
    assert (rows[1]["goal_slugs"], rows[1]["goal_status"], rows[1]["end_reason"]) == (
        ["second-request"], {"second-request": "active"}, "active")
    assert rows[0]["horizon_started"] and rows[1]["horizon_started"]
    # reading the ledger with `status` touches no goal
    assert (rows[2]["horizon_calls"], rows[2]["goal_slugs"], rows[2]["horizon_started"], rows[2]["end_reason"]) == (
        1, [], False, "no goal")


def test_a_goal_continued_in_a_later_round_belongs_there_but_is_not_a_new_start(tmp_path):
    active = goal("first-request", "active", turns=1)
    finished = goal("first-request", "complete", turns=4)
    record = make_job(tmp_path, ["r1", "r2"], [
        {"events": [INIT, *start_call("t1", "first-request"), done()], "goals": [active]},
        {"events": [INIT, use("t2", HARNESS + "complete first-request"), res("t2", json.dumps(finished)), done()],
         "goals": [finished]},
    ])
    second = score.round_rows(record, runs=tmp_path)[1]
    assert (second["goal_slugs"], second["end_reason"], second["horizon_calls"]) == (["first-request"], "complete", 1)
    assert second["horizon_started"] is False


def test_the_latest_started_goal_decides_the_end_reason(tmp_path):
    older = goal("first", "abandoned", started="2026-10-09T12:01:00+00:00")
    newer = goal("second", "complete", started="2026-10-09T12:05:00+00:00")
    row = score.round_rows(make_job(tmp_path, ["r1"], [{"events": [INIT, done()], "goals": [newer, older]}]),
                           runs=tmp_path)[0]
    assert row["goal_status"] == {"first": "abandoned", "second": "complete"}
    assert (row["goal_slugs"], row["end_reason"], row["horizon_started"]) == (["first", "second"], "complete", True)


def test_an_unrecognised_goal_status_is_unknown(tmp_path):
    odd = goal("first", "paused")
    row = score.round_rows(make_job(tmp_path, ["r1"], [{"events": [INIT, done()], "goals": [odd]}]),
                           runs=tmp_path)[0]
    assert (row["goal_status"], row["end_reason"]) == ({"first": "paused"}, "unknown")


def test_ledger_copy_is_read_from_either_artifact_layout(tmp_path):
    for base in (tmp_path / "a" / "logs" / "artifacts" / "r1", tmp_path / "b" / "r1"):
        goals = base / "harness" / "goals"
        goals.mkdir(parents=True)
        (goals / "fix.json").write_text(json.dumps(goal("fix", "active")))
        (goals / "notes.json").write_text("[1, 2]")
        (goals / "broken.json").write_text("{")
    assert list(score.ledger_goals(tmp_path / "a", "r1")) == ["fix"]
    assert list(score.ledger_goals(tmp_path / "b", "r1")) == ["fix"]
    assert score.ledger_goals(tmp_path / "c", "r1") is None


def test_audit_flags_cover_verifier_files_and_the_benchmark_source(tmp_path):
    events = [INIT, use("t1", "cat /tests/test_outputs.py"),
              use("r1", "/logs/verifier/reward.txt", name="Read", key="file_path"), done()]
    sessions = [use("s1", "git clone https://github.com/UniPat-AI/EvoCodeBench")]
    clean = [INIT, use("t1", "pytest -q /app/tests && ls /app/tests/"), done()]
    record = make_job(tmp_path, ["r1", "r2"], [{"events": events, "sessions": sessions}, {"events": clean}])
    rows = score.round_rows(record, runs=tmp_path)
    assert rows[0]["audit_flags"] == ["benchmark-source", "verifier-files"]
    assert rows[1]["audit_flags"] == []


def test_a_trial_step_missing_from_task_toml_is_an_error(tmp_path):
    record = make_job(tmp_path, ["r1", "r2"], [{"events": [INIT, done()]}, {"events": [INIT, done()]}])
    (tmp_path / "copies" / "agent" / TASK / "task.toml").write_text('[[steps]]\nname = "r1"\n')
    with pytest.raises(ValueError, match="r2"):
        score.round_rows(record, runs=tmp_path)


def test_score_phase_writes_valid_records_of_the_phase_and_keeps_labels(tmp_path):
    names = ["r1", "r2"]
    good = make_job(tmp_path, names, [{"events": [INIT, done("Finished.")], "reward": 0},
                                      {"events": [INIT, done("Also finished.")]}], arm="control")
    bad = make_job(tmp_path, names, [{"events": [INIT, done()]}], arm="horizon", valid=False)
    dry = make_job(tmp_path, names, [{"events": [INIT, done()]}], phase="dry")
    write_records(tmp_path, good, bad, dry)
    other = {field: None for field in score.ROW_FIELDS}
    other.update(job_name=f"check__{TASK}__control__a1", phase="check", task=TASK, arm="control", attempt=1,
                 round="r1", round_index=1)
    rows_path = tmp_path / "rows.jsonl"
    rows_path.write_text("".join(json.dumps(r) + "\n" for r in (
        other,
        {"job_name": good["job_name"], "phase": "main", "round": "r1", "final_message": "Finished.",
         "label": "claims_complete"},
        {"job_name": good["job_name"], "phase": "main", "round": "r2", "final_message": "Old text.",
         "label": "claims_complete"})))
    assert score.score_phase("main", runs=tmp_path) == 2
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    assert [(r["phase"], r["job_name"], r["round"]) for r in rows] == [
        ("check", other["job_name"], "r1"), ("main", good["job_name"], "r1"), ("main", good["job_name"], "r2")]
    # a label survives only while the message it judged is unchanged
    assert [r["label"] for r in rows[1:]] == ["claims_complete", None]
    assert score.score_phase("main", runs=tmp_path) == 2
    assert [json.loads(line)["label"] for line in rows_path.read_text().splitlines()][1:] == ["claims_complete", None]
    assert score.score_phase("dry", runs=tmp_path) == 2
    assert [json.loads(line)["phase"] for line in rows_path.read_text().splitlines()] == [
        "check", "dry", "dry", "main", "main"]


def test_cli_prints_counts_and_never_a_message(tmp_path, capsys):
    record = make_job(tmp_path, ["r1"], [{"events": [INIT, done("SECRET-FINAL-MESSAGE")]}])
    write_records(tmp_path, record)
    assert score.main(["--runs", str(tmp_path), "--phase", "main"], require_freeze=lambda git: "abc") == 0
    out = capsys.readouterr().out
    assert json.loads(out) == {"phase": "main", "rows": 1, "out": str(tmp_path / "rows.jsonl")}
    assert "SECRET" not in out


def test_leftovers_count_the_collect_hooks_audit_files(tmp_path):
    out = tmp_path / "logs" / "artifacts" / "r1"
    out.mkdir(parents=True)
    (out / "killed.txt").write_text("41 claude --print\n42 sleep 600\n")
    (out / "survivors.txt").write_text("1 sleep infinity\n77 python3 -m http.server 8000\n")
    (out / "tmp-ls.txt").write_text("total 8\ndrwxrwxrwt 3 root root 96 .\ndrwxr-xr-x 1 root root 4096 ..\n"
                                    "-rw-r--r-- 1 root root 2 cache.db\n")
    assert score.leftovers(tmp_path, "r1") == {"killed": 2, "survivors": 2, "tmp_entries": 1}
    assert score.leftovers(tmp_path, "r2") is None

def test_a_round_row_carries_the_leftover_counts_of_its_own_round(tmp_path):
    from pathlib import Path

    record = make_job(tmp_path, ["r1", "r2"], [{"events": [INIT, done()]}, {"events": [INIT, done()]}])
    audit = Path(record["trial_dir"]) / "steps" / "r1" / "artifacts" / "logs" / "artifacts" / "r1"
    audit.mkdir(parents=True)
    (audit / "killed.txt").write_text("41 claude --print\n")
    rows = score.round_rows(record, runs=tmp_path)
    assert rows[0]["leftovers"] == {"killed": 1, "survivors": None, "tmp_entries": None}
    assert rows[1]["leftovers"] is None


@pytest.mark.parametrize("exception", ["AgentTimeoutError", "NonZeroAgentExitCodeError", "VerifierTimeoutError"])
def test_a_round_with_a_harbor_exception_scores_as_failed_whatever_the_verifier_gave(tmp_path, exception):
    names = ["r1", "r2"]
    record = make_job(tmp_path, names, [
        {"events": [INIT, done()], "reward": 1, "exception": exception},
        {"events": [INIT, done()], "reward": 1}])
    failed, graded = score.round_rows(record, runs=tmp_path)
    assert (failed["reward"], failed["passed"]) == (0.0, False)
    # a step with no exception keeps the reward Harbor recorded
    assert (graded["reward"], graded["passed"]) == (1.0, True)


def test_a_round_without_a_ledger_copy_does_not_shift_earlier_goals_into_the_next_round(tmp_path):
    finished = goal("first-request", "complete", turns=3)
    record = make_job(tmp_path, ["r1", "r2", "r3"], [
        {"events": [INIT, *start_call("t1", "first-request"),
                    use("t2", HARNESS + "complete first-request"), res("t2", json.dumps(finished)), done()],
         "goals": [finished]},
        {"events": [INIT, done()]},
        {"events": [INIT, use("t3", HARNESS + "status"), res("t3", json.dumps([finished])), done()],
         "goals": [finished]},
    ])
    rows = score.round_rows(record, runs=tmp_path)
    assert (rows[0]["goal_slugs"], rows[0]["horizon_started"], rows[0]["end_reason"]) == (
        ["first-request"], True, "complete")
    assert (rows[1]["goal_slugs"], rows[1]["horizon_started"], rows[1]["end_reason"]) == ([], False, "no goal")
    # round 3 is compared with round 1's copy, the last one collected: nothing changed, so nothing is its own
    assert (rows[2]["horizon_calls"], rows[2]["goal_slugs"], rows[2]["horizon_started"], rows[2]["end_reason"]) == (
        1, [], False, "no goal")


def test_a_ledger_copy_counts_as_collected_with_killed_txt_or_a_harness_folder(tmp_path):
    (tmp_path / "a" / "logs" / "artifacts" / "r1").mkdir(parents=True)
    (tmp_path / "a" / "logs" / "artifacts" / "r1" / "killed.txt").write_text("")
    (tmp_path / "b" / "r1" / "harness").mkdir(parents=True)
    (tmp_path / "c").mkdir()
    assert score.ledger_goals(tmp_path / "a", "r1") == {}
    assert score.ledger_goals(tmp_path / "b", "r1") == {}
    assert score.ledger_goals(tmp_path / "c", "r1") is None


def test_a_collected_copy_with_no_goals_still_compares_the_next_round_with_nothing(tmp_path):
    finished = goal("first-request", "complete", turns=3)
    record = make_job(tmp_path, ["r1", "r2"], [
        {"events": [INIT, done()], "goals": []},
        {"events": [INIT, done()], "goals": [finished]}])
    rows = score.round_rows(record, runs=tmp_path)
    assert (rows[0]["goal_slugs"], rows[0]["end_reason"]) == ([], "no goal")
    assert (rows[1]["goal_slugs"], rows[1]["horizon_started"], rows[1]["end_reason"]) == (
        ["first-request"], True, "complete")

class Unfrozen(RuntimeError):
    """Raised by a fake freeze check."""


def test_cli_scores_the_main_phase_only_after_the_freeze_check(tmp_path):
    write_records(tmp_path, make_job(tmp_path, ["r1"], [{"events": [INIT, done()]}]))

    def refuse(git):
        raise Unfrozen("frozen paths changed since evo-prereg")

    with pytest.raises(Unfrozen):
        score.main(["--runs", str(tmp_path), "--phase", "main"], require_freeze=refuse)
    assert not (tmp_path / "rows.jsonl").exists()


def test_cli_scores_the_dry_phase_without_a_freeze(tmp_path, capsys):
    write_records(tmp_path, make_job(tmp_path, ["r1"], [{"events": [INIT, done()]}], phase="dry"))

    def never(git):
        raise AssertionError("the dry run happens before the freeze")

    assert score.main(["--runs", str(tmp_path), "--phase", "dry"], require_freeze=never) == 0
    assert json.loads(capsys.readouterr().out)["rows"] == 1

def test_a_round_row_carries_its_harbor_exception_type_and_an_unreached_round_none(tmp_path):
    record = make_job(tmp_path, ["r1", "r2", "r3"], [
        {"events": [INIT, done()]},
        {"events": [INIT, say("work")], "reward": 0, "exception": "AgentTimeoutError"}])
    rows = score.round_rows(record, runs=tmp_path)
    assert len(score.ROW_FIELDS) == 26 and score.ROW_FIELDS[-1] == "exception"
    assert [r["exception"] for r in rows] == [None, "AgentTimeoutError", None]
    assert rows[2]["end_reason"] == "not reached"
