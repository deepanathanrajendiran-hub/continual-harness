import inspect
import itertools
import json
from fractions import Fraction

import pytest

from bench.evo import analysis, config
from bench.tb4 import judge


def row(task, arm, index, passed, *, phase="main", attempt=1, **extra):
    base = {"job_name": f"{phase}__{task}__{arm}__a{attempt}", "phase": phase, "task": task, "arm": arm,
            "attempt": attempt, "round": f"round-{index}", "round_index": index,
            "reward": 1.0 if passed else 0.0, "passed": passed, "cases_passed": 4 if passed else 2,
            "cases_total": 4, "agent_sec": 600.0, "tokens_in": 1000, "tokens_out": 100, "cost_usd": 0.5,
            "result_records": 1, "horizon_calls": 3 if arm == "horizon" else 0,
            "horizon_started": arm == "horizon", "goal_slugs": ["g"] if arm == "horizon" else [],
            "goal_status": {"g": "complete"} if arm == "horizon" else {},
            "end_reason": "complete" if arm == "horizon" else "no goal",
            "final_message": f"{task} {arm} round {index} message", "label": "claims_complete"}
    base.update(extra)
    return base


def missing(task, arm, index, **extra):
    """A round the chain never reached, as score.round_rows writes it."""
    return row(task, arm, index, False, reward=0.0, cases_passed=None, cases_total=None, agent_sec=None,
               tokens_in=None, tokens_out=None, cost_usd=None, result_records=0, horizon_calls=0,
               horizon_started=False, goal_slugs=[], goal_status={}, end_reason="not reached",
               final_message=None, label=None, **extra)


def record(task, arm, *, phase="main", attempt=1, valid=True, reason=None):
    return {"job_name": f"{phase}__{task}__{arm}__a{attempt}", "phase": phase, "task": task, "arm": arm,
            "attempt": attempt, "valid": valid, "invalid_reason": reason, "freeze": "abc123"}


def naive_p(diffs, delta=Fraction(0)):
    """Two-sided sign-flip p of the diffs shifted by delta, by enumeration in exact Fractions: no tolerance."""
    shifted = [d - delta for d in diffs]
    observed = abs(sum(shifted))
    sums = [abs(sum(s * d for s, d in zip(signs, shifted)))
            for signs in itertools.product((1, -1), repeat=len(shifted))]
    return Fraction(sum(total >= observed for total in sums), len(sums))


def test_permutation_all_positive_gives_two_over_two_to_the_n():
    result = analysis.permutation([0.1, 0.2, 0.3, 0.1, 0.4, 0.2, 0.5, 0.3])
    assert result["p"] == 2 / 256
    assert (result["n"], result["wins"], result["losses"], result["ties"]) == (8, 8, 0, 0)
    assert result["mean"] == pytest.approx(0.2625)


def test_permutation_counts_float_ties_with_the_observed_statistic():
    # d is built as h/R - c/R, the way summarize builds it. Exactly, the signed sums are +-1/2 (four), +-7/6 (two) and
    # +-1/6 (two), so six reach the observed |1/2|. In floats two of the four 1/2 sums land one ulp below it, so
    # without the tolerance they are lost and p is 0.5 instead of 0.75
    diffs = [0 / 2 - 1 / 2, 1 / 3 - 0 / 3, 2 / 3 - 3 / 3]
    assert analysis.permutation(diffs)["p"] == 6 / 8


def test_permutation_matches_a_naive_enumeration_and_its_interval_holds_the_mean():
    diffs = [Fraction(tenths, 10) for tenths in (1, 3, -1, 2, 0, 4, 1, 2)]
    result = analysis.permutation(diffs)
    assert Fraction(result["p"]) == naive_p(diffs)
    steps = [Fraction(k, 100) for k in range(-100, 101)]
    kept = [delta for delta in steps if naive_p(diffs, delta) >= Fraction(1, 20)]
    assert result["ci95"] == (float(min(kept)), float(max(kept)))
    lo, hi = result["ci95"]
    assert -1 <= lo < result["mean"] < hi <= 1


def test_permutation_interval_is_a_point_when_every_task_moves_the_same_amount():
    result = analysis.permutation([0.5] * 8)
    assert result["ci95"] == (0.5, 0.5) and result["p"] == 2 / 256


def test_permutation_ties_and_too_few_tasks():
    result = analysis.permutation([0.0, 0.2, -0.1, 0.0])
    assert (result["wins"], result["losses"], result["ties"]) == (1, 1, 2)
    flat = analysis.permutation([0.0, 0.0, 0.0])
    assert flat["p"] == 1.0 and flat["mean"] == 0.0 and flat["ci95"] == (-1.0, 1.0)
    assert analysis.permutation([]) == {"n": 0, "mean": None, "ci95": (None, None), "p": None,
                                        "wins": 0, "losses": 0, "ties": 0}


def test_task_scores_count_missing_rounds_as_failed_and_use_the_latest_attempt():
    rows = [row("a", "control", 1, True), row("a", "control", 2, True), row("a", "control", 3, False)]
    rows += [row("a", "horizon", i, True) for i in range(1, 6)]  # superseded by attempt 2
    rows += [row("a", "horizon", i, True, attempt=2) for i in (1, 2, 3)]
    rows += [missing("a", "horizon", 4, attempt=2), missing("a", "horizon", 5, attempt=2)]
    rows += [row("b", "control", 1, True)]
    scores = analysis.task_scores(rows, {"a": 5, "b": 2})
    assert scores == {"a": {"control": 0.4, "horizon": 0.6}, "b": {"control": 0.5, "horizon": None}}
    with pytest.raises(ValueError):
        analysis.task_scores([row("a", "control", i, True) for i in (1, 2, 3)], {"a": 2})


def test_secondary_rates_per_arm():
    rows = [
        row("a", "control", 1, True, label="reports_incomplete", agent_sec=600.0),
        row("a", "control", 2, False, label="claims_complete", agent_sec=1200.0, cases_passed=1, cases_total=4),
        row("a", "control", 3, False, label="reports_incomplete", agent_sec=1800.0, horizon_calls=1,
            cases_passed=None, cases_total=None),
        missing("a", "control", 4),
        row("a", "horizon", 1, True, label="claims_complete", result_records=2),
        row("a", "horizon", 2, False, label="neither", horizon_started=False, end_reason="no goal"),
        row("a", "horizon", 3, False, final_message=None, label=None, result_records=0, end_reason="active"),
        missing("a", "horizon", 4),
    ]
    s = analysis.secondary(rows)
    c, h = s["control"], s["horizon"]
    assert (c["rounds"], c["reached"], c["passed"]) == (4, 3, 1)
    assert c["case_score"] == pytest.approx((1.0 + 0.25) / 2) and (c["case_rounds"], c["case_missing"]) == (2, 2)
    assert (c["false_done"], c["labeled_failed"], c["false_done_rate"]) == (1, 2, 0.5)
    assert (c["under_claim"], c["labeled_passed"], c["under_claim_rate"]) == (1, 1, 1.0)
    assert c["agent_minutes_median"] == 20.0 and c["cost_usd_total"] == pytest.approx(1.5)
    assert (c["tokens_total"], c["token_rounds"], c["tokens_per_round"]) == (3300, 3, 1100.0)
    assert (c["horizon_calls"], c["horizon_started"]) == (1, 0)
    assert (h["false_done_rate"], h["under_claim_rate"]) == (0.0, 0.0)
    assert (h["horizon_started"], h["reached"]) == (2, 3) and h["horizon_start_rate"] == pytest.approx(2 / 3)
    assert (h["extra_result_records"], h["no_result_record"]) == (1, 1)


TASKS = ["t1", "t2", "t3"]
ROUNDS = {"t1": 3, "t2": 2, "t3": 2}


def study():
    """t1: control 1/3, horizon 2/3. t2: control 2/2 on its rerun, horizon 1/2. t3: horizon dropped."""
    records = [record("t1", "control"), record("t1", "horizon"),
               record("t2", "control", valid=False, reason="usage_limit"), record("t2", "control", attempt=2),
               record("t2", "horizon"),
               record("t3", "control"), record("t3", "horizon", valid=False, reason="api_error"),
               record("t3", "horizon", attempt=2, valid=False, reason="infrastructure")]
    rows = [row("t1", "control", 1, True), row("t1", "control", 2, False), missing("t1", "control", 3),
            row("t1", "horizon", 1, True), row("t1", "horizon", 2, True), row("t1", "horizon", 3, False),
            row("t2", "control", 1, True, attempt=2), row("t2", "control", 2, True, attempt=2),
            row("t2", "horizon", 1, True), row("t2", "horizon", 2, False),
            row("t3", "control", 1, True), row("t3", "control", 2, False)]
    return rows, records


def test_run_status_and_problems_block_an_unfinished_study():
    rows, records = study()
    assert analysis.run_status(records, TASKS) == {"t1": "valid", "t2": "valid", "t3": "dropped"}
    assert analysis.problems(rows, records, TASKS) == {}
    records += [record("t4", "control", valid=False, reason="usage_limit"), record("t4", "horizon"),
                record("t7", "control"), record("t7", "horizon")]
    rows.append(row("t5", "control", 1, True))
    rows[0]["label"] = None
    found = analysis.problems(rows, records, TASKS + ["t4", "t6", "t7"])
    assert found == {"pending": ["t4", "t6"], "not_scored": ["t7"],
                     "unlabeled": ["main__t1__control__a1 round 1"], "not_planned": ["t5"]}


def test_summarize_pairs_valid_tasks_and_reports_validity():
    rows, records = study()
    s = analysis.summarize(rows, records, TASKS, ROUNDS)
    assert [t["status"] for t in s["tasks"]] == ["valid", "valid", "dropped"]
    assert s["tasks"][0]["passed"] == {"control": 1, "horizon": 2}
    assert s["tasks"][2]["d"] is None and s["tasks"][2]["passed"] == {"control": 1, "horizon": None}
    p = s["primary"]
    assert p["n"] == 2 and p["mean"] == pytest.approx((1 / 3 - 0.5) / 2) and (p["wins"], p["losses"]) == (1, 1)
    v = s["validity"]
    assert v["dropped"] == ["t3"] and v["retried"] == ["main__t2__control__a2", "main__t3__horizon__a2"]
    assert v["invalid_reasons"] == {"api_error": 1, "infrastructure": 1, "usage_limit": 1}
    assert v["runs"] == {"control": {"valid": 3, "invalid": 1}, "horizon": {"valid": 2, "invalid": 2}}
    assert v["control_horizon"] == [] and v["extra_result_records"] == [] and v["audit"] is None
    assert v["freezes"] == ["abc123"]
    assert s["secondary"]["control"]["rounds"] == 5  # t1 and t2 only: the dropped task's rows are left out


def test_render_shows_every_task_and_never_quotes_messages():
    rows, records = study()
    text = analysis.render(analysis.summarize(rows, records, TASKS, ROUNDS), "- t3 dropped after two invalid runs\n")
    for task in TASKS:
        assert f"| {task} |" in text
    assert "1/3 (0.33)" in text and "2/3 (0.67)" in text and "+0.33" in text and "-0.50" in text
    assert "first look" in text and "| dropped |" in text and "- t3 dropped after two invalid runs" in text
    assert "## Limits" in text and "CC-BY-NC-4.0" in text and analysis.ANALYSIS in text
    assert not any(r["final_message"] in text for r in rows if r["final_message"])
    assert "None recorded." in analysis.render(analysis.summarize(rows, records, TASKS, ROUNDS))


def test_label_rows_labels_main_messages_blind_and_defaults_to_the_tb4_judge(tmp_path):
    assert inspect.signature(analysis.label_rows).parameters["judge_fn"].default is judge.judge
    path = tmp_path / "rows.jsonl"
    rows = [row("t1", "control", 1, False, label=None),
            row("t1", "horizon", 1, True, label="claims_complete"),
            missing("t1", "horizon", 2),
            row("w", "horizon", 1, True, phase="dry", label=None),
            row("t1", "horizon", 3, False, label=None)]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    seen = []

    def judge_fn(message, token):
        seen.append((message, token))
        return "reports_incomplete"

    assert analysis.label_rows(path, "tok", judge_fn=judge_fn, log=lambda message: None) == 2
    assert seen == [("t1 control round 1 message", "tok"), ("t1 horizon round 3 message", "tok")]
    labels = [json.loads(line)["label"] for line in path.read_text().splitlines()]
    assert labels == ["reports_incomplete", "claims_complete", None, None, "reports_incomplete"]


def test_label_rows_keeps_labels_written_before_a_judge_failure(tmp_path):
    path = tmp_path / "rows.jsonl"
    rows = [row("t1", "control", 1, False, label=None), row("t1", "horizon", 1, False, label=None)]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    answers = iter(["claims_complete"])

    def judge_fn(message, token):
        for answer in answers:
            return answer
        raise judge.JudgeError("judge failed")

    with pytest.raises(judge.JudgeError):
        analysis.label_rows(path, "tok", judge_fn=judge_fn, log=lambda message: None)
    assert [json.loads(line)["label"] for line in path.read_text().splitlines()] == ["claims_complete", None]


def write_runs(root, rows, records, deviations=None):
    runs = root / "runs"
    (runs / "records").mkdir(parents=True)
    (runs / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    for r in records:
        (runs / "records" / f"{r['job_name']}.json").write_text(json.dumps(r))
    if deviations:
        (runs / "deviations.md").write_text(deviations)
    return runs


def test_timing_reports_mean_minutes_and_the_n_rule(tmp_path, capsys):
    rows = [row("w", "control", i, True, phase="dry", agent_sec=1200.0) for i in (1, 2)]
    rows += [row("w", "horizon", 1, True, phase="dry", agent_sec=1200.0),
             row("w", "horizon", 2, True, phase="dry", agent_sec=1800.0), missing("w", "horizon", 3, phase="dry")]
    rows += [row("t1", "control", 1, True, agent_sec=60.0)]  # main rows never enter the timing
    runs = write_runs(tmp_path, rows, [])
    assert analysis.main(["timing", "--runs", str(runs)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["m_control"], out["m_horizon"], out["n"], out["rounds"]) == (20.0, 25.0, 8, {"control": 2, "horizon": 2})
    slow = write_runs(tmp_path / "slow", [row("w", arm, 1, True, phase="dry", agent_sec=2400.0) for arm in config.ARMS], [])
    assert analysis.main(["timing", "--runs", str(slow)]) == 1
    assert json.loads(capsys.readouterr().out)["n"] is None


def test_report_cli_writes_the_report_and_refuses_unfinished_work(tmp_path, monkeypatch, capsys):
    rows, records = study()
    runs = write_runs(tmp_path, rows, records, deviations="- t3 dropped\n")
    prereg = tmp_path / "prereg.json"
    prereg.write_text(json.dumps({"tasks": TASKS}))
    seen = []

    def list_tasks(root):
        seen.append(root)
        return [{"task": t, "rounds": n} for t, n in {**ROUNDS, "other": 9}.items()]

    monkeypatch.setattr(analysis.dataset, "list_tasks", list_tasks)
    out = tmp_path / "docs" / "report.md"
    args = ["report", "--runs", str(runs), "--prereg", str(prereg), "--out", str(out)]
    assert analysis.main(args) == 0
    assert seen == [runs / "dataset" / config.DATASET_REVISION / "tasks"]
    assert "| t3 |" in out.read_text() and "- t3 dropped" in out.read_text()
    assert json.loads(capsys.readouterr().out)["primary"]["n"] == 2
    out.unlink()
    rows[0]["label"] = None
    again = write_runs(tmp_path / "again", rows, records)
    assert analysis.main(["report", "--runs", str(again), "--prereg", str(prereg), "--out", str(out)]) == 2
    assert not out.exists() and json.loads(capsys.readouterr().out)["unlabeled"] == ["main__t1__control__a1 round 1"]


def test_report_cli_plans_the_reserve_a_drop_brought_in_and_shows_the_dropped_task(tmp_path, monkeypatch, capsys):
    rows, records = study()  # t3's horizon arm was invalid twice, so the runner dropped t3
    records += [record("t4", "control"), record("t4", "horizon")]
    rows += [row("t4", "control", 1, False), row("t4", "control", 2, False),
             row("t4", "horizon", 1, True), row("t4", "horizon", 2, False)]
    drop = "- main t3: dropped after two invalid runs of the horizon arm (a1: api_error; a2: infrastructure)\n"
    runs = write_runs(tmp_path, rows, records, deviations=drop)
    prereg = tmp_path / "prereg.json"
    prereg.write_text(json.dumps({"tasks": TASKS, "reserve": ["t4", "t5"]}))
    rounds = {**ROUNDS, "t4": 2, "t5": 2}
    monkeypatch.setattr(analysis.dataset, "list_tasks",
                        lambda root: [{"task": t, "rounds": n} for t, n in rounds.items()])
    out = tmp_path / "docs" / "report.md"
    assert analysis.main(["report", "--runs", str(runs), "--prereg", str(prereg), "--out", str(out)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["statuses"] == {"t1": "valid", "t2": "valid", "t3": "dropped", "t4": "valid"}
    assert printed["primary"]["n"] == 3
    text = out.read_text()
    assert "3 of 4 planned tasks" in text and "| t4 |" in text and "| t5 |" not in text
    assert "| t3 | 2 | 1/2 (0.50) | n/a | n/a | dropped |" in text


def test_a_task_the_runner_dropped_is_never_paired():
    rows, records = study()
    assert analysis.run_status(records, TASKS, dropped=["t1"]) == {"t1": "dropped", "t2": "valid", "t3": "dropped"}
    s = analysis.summarize(rows, records, TASKS, ROUNDS, dropped=["t1"])
    assert [t["status"] for t in s["tasks"]] == ["dropped", "valid", "dropped"] and s["tasks"][0]["d"] is None
    assert s["primary"]["n"] == 1 and s["validity"]["dropped"] == ["t1", "t3"]
    assert analysis.problems(rows, records, TASKS, dropped=["t1"]) == {}


def test_label_cli_uses_the_keychain_token_and_the_tb4_judge(tmp_path, monkeypatch):
    runs = write_runs(tmp_path, [row("t1", "control", 1, False, label=None)], [])
    monkeypatch.setattr(analysis.runner, "read_token", lambda: "tok")
    monkeypatch.setattr(judge, "judge", lambda message, token: "neither")
    assert analysis.main(["label", "--runs", str(runs)]) == 0
    assert json.loads((runs / "rows.jsonl").read_text())["label"] == "neither"


def test_usage_consumed_sums_valid_jobs_and_counts_reset_straddlers():
    rows, records = study()
    for r in records:
        r["usage_before"] = {"seven_day": 0.10, "seven_day_resets_at": 100}
        r["usage_after"] = {"seven_day": 0.15, "seven_day_resets_at": 100}
    records[1]["usage_after"] = {"seven_day": 0.01, "seven_day_resets_at": 200}  # t1 horizon spans a reset
    use = analysis.summarize(rows, records, TASKS, ROUNDS)["usage"]
    assert use["control"]["jobs"] == 2 and use["control"]["seven_day"] == pytest.approx(0.10)
    assert (use["horizon"]["jobs"], use["horizon"]["straddled"]) == (1, 1)
    assert "Seven-day usage consumed" in analysis.render(analysis.summarize(rows, records, TASKS, ROUNDS))

def test_the_leftover_audit_counts_rounds_by_what_the_hook_found():
    rows, records = study()
    rows[0]["leftovers"] = {"killed": 1, "survivors": 0, "tmp_entries": 0}
    rows[1]["leftovers"] = {"killed": 0, "survivors": 1, "tmp_entries": 1}
    rows[3]["leftovers"] = {"killed": 0, "survivors": 0, "tmp_entries": 2}
    summary = analysis.summarize(rows, records, TASKS, ROUNDS)
    left = summary["validity"]["leftovers"]
    assert (left["audited"], left["killed"], left["survivors"], left["tmp"]) == (3, 1, 1, 2)
    assert "rounds audited 3 of" in analysis.render(summary)
