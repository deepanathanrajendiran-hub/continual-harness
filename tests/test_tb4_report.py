import json

from bench.tb4 import report


def row(task, arm, passed, attempt=1, valid=True, timed_out=False, **extra):
    base = {"task": task, "arm": arm, "attempt": attempt, "valid": valid, "passed": passed, "timed_out": timed_out,
            "invalid_reasons": [] if valid else ["exception ApiUsageLimitError"], "final_message": "msg",
            "label": "claims_complete", "false_done": not passed, "honest_stop": False, "tokens": 1000,
            "cost_usd": 2.0, "wall_s": 3600.0, "horizon_started": arm == "horizon", "horizon_calls": 3 if arm == "horizon" else 0,
            "horizon_end": "complete" if arm == "horizon" else "no goal", "horizon_reviewed": arm == "horizon",
            "subagents_dispatched": 1, "audit_flags": []}
    base.update(extra)
    return base


def pilot(control_passes=5, horizon_started=10):
    rows = []
    for i in range(10):
        rows.append(row(f"t{i}", "control", i < control_passes))
        rows.append(row(f"t{i}", "horizon", True, horizon_started=i < horizon_started))
    return rows


def test_all_conditions_met():
    d = report.decision(pilot())
    assert (d["valid_pairs"], d["control_passes"], d["horizon_started"]) == (10, 5, 10)
    assert d["condition_1"] and d["condition_2"] and d["condition_3"] and d["proceed"]


def test_condition_1_needs_nine_valid_pairs():
    rows = pilot()
    for task in ("t0", "t1"):
        rows += [row(task, "control", True, attempt=2), row(task, "horizon", True, attempt=2, valid=False)]
    d = report.decision(rows)
    assert d["valid_pairs"] == 8 and not d["condition_1"] and not d["proceed"]


def test_condition_2_is_inclusive_between_two_and_eight():
    assert not report.decision(pilot(control_passes=1))["condition_2"]
    assert report.decision(pilot(control_passes=2))["condition_2"]
    assert report.decision(pilot(control_passes=8))["condition_2"]
    assert not report.decision(pilot(control_passes=9))["condition_2"]


def test_condition_3_checks_fidelity_and_leakage():
    assert not report.decision(pilot(horizon_started=8))["condition_3"]
    assert report.decision(pilot(horizon_started=9))["condition_3"]
    rows = pilot()
    rows[0]["horizon_calls"] = 1
    d = report.decision(rows)
    assert d["control_invoked_horizon"] == ["t0"] and not d["condition_3"]


def test_condition_3_counts_control_invocations_in_any_attempt():
    rows = pilot()
    rows[0].update(valid=False, horizon_calls=2)
    rows += [row("t0", "control", True, attempt=2), row("t0", "horizon", True, attempt=2)]
    d = report.decision(rows)
    assert d["valid_pairs"] == 10 and d["control_invoked_horizon"] == ["t0"] and not d["condition_3"]


def test_arm_summary_rates_and_censored_wall_time():
    rows = [row("a", "control", False, timed_out=True, final_message=None, label=None, false_done=None),
            row("b", "control", False, timed_out=True, final_message=None, label=None, false_done=None),
            row("c", "control", False, label="reports_incomplete", false_done=False, honest_stop=True),
            row("d", "control", True, false_done=False)]
    s = report.arm_summary(rows)
    assert (s["timeouts"], s["labeled_failures"], s["false_done_rate"], s["honest_stop_rate"]) == (2, 1, 0.0, 1.0)
    assert s["wall_median_s"] == 5400.0 and not s["wall_censored"]
    rows.append(row("e", "control", False, timed_out=True, final_message=None, label=None))
    assert report.arm_summary(rows)["wall_censored"]


def test_flagged_pairs_drop_from_the_secondary_table():
    rows = pilot()
    rows[1]["audit_flags"] = ["benchmark-source"]
    s = report.summarize(rows)
    assert s["flagged"] == ["t0"]
    assert s["arms"]["horizon"]["n"] == 10 and s["arms_without_flagged"]["horizon"]["n"] == 9


def test_cli_refuses_unfinished_pairs(tmp_path):
    rows = pilot()
    rows[0]["valid"] = False
    results = tmp_path / "results.jsonl"
    results.write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = tmp_path / "report.md"
    assert report.main(["--results", str(results), "--out", str(out)]) == 2
    assert not out.exists()


def test_render_states_the_decision_and_limits():
    rows = pilot(control_passes=1)
    text = report.render(report.summarize(rows), report.decision(rows), {"n": 20, "agree": 19, "rate": 0.95})
    assert "Proceed to stage 2: **no**" in text and "Condition 2" in text and "| t0 |" in text
    assert "not comparable" in text and "0.95" in text
