import itertools

import pytest

from bench.swepro import analysis, config

FROZEN = "f" * 64


def row(task, arm, attempt, score, **extra):
    base = {"task": task, "arm": arm, "attempt": attempt, "score": score, "valid": True, "reruns": 0,
            "reward_sandbox": float(score), "reward_regrade": float(score), "regrade_valid": True,
            "exception": None, "cost_usd": 1.0, "tokens_in": 100, "tokens_out": 10, "agent_sec": 120.0,
            "claude_version": config.CLAUDE_CODE_VERSION, "model": "claude-sonnet-5-5",
            "notes_hash": FROZEN if arm == "refined" else None, "claude_dir": arm == "refined",
            "audit_tests": False, "graded_failed": 0 if score else 2, "graded_total": 10, "job": f"{task}-{arm}-{attempt}"}
    base.update(extra)
    return base


def rows_for(task, plain, refined):
    return [row(task, "plain", a + 1, s) for a, s in enumerate(plain)] + \
           [row(task, "refined", a + 1, s) for a, s in enumerate(refined)]


def test_task_scores_are_pass_shares_and_incomplete_tasks_are_listed():
    rows = rows_for("a", (1, 0, 0), (1, 1, 0)) + rows_for("b", (1, 1, 1), (1, 1, 1))[:5]
    scores, incomplete = analysis.task_scores(rows)
    assert scores == {"a": {"plain": pytest.approx(1 / 3), "refined": pytest.approx(2 / 3)}}
    assert incomplete == ["b"]


def exact_p(diffs, delta=0.0):
    n, obs = len(diffs), abs(sum(diffs) - delta * len(diffs))
    hits = sum(1 for s in itertools.product((1, -1), repeat=n)
               if abs(sum(a * d for a, d in zip(s, diffs)) - delta * sum(s)) >= obs - 1e-9)
    return hits / 2 ** n


def test_the_monte_carlo_p_matches_exact_enumeration():
    diffs = [1 / 3, 2 / 3, 0, -1 / 3, 1 / 3, 1, 0, 1 / 3, 2 / 3, -1 / 3]
    r = analysis.permutation(diffs, draws=100_000, seed=config.PERM_SEED)
    assert r["p"] == pytest.approx(exact_p(diffs), abs=0.005)
    assert (r["wins"], r["losses"], r["ties"]) == (6, 2, 2)
    assert r["mean"] == pytest.approx(sum(diffs) / 10)


def test_the_interval_contains_the_mean_and_excludes_far_shifts():
    diffs = [0.33, 0.67, 0.0, 0.33, 0.33, 1.0, 0.0, 0.33, 0.67, 0.33] * 3
    r = analysis.permutation(diffs, draws=20_000, seed=1)
    lo, hi = r["ci95"]
    assert lo < r["mean"] < hi and lo > 0 and hi < 1


def test_the_test_is_seeded():
    diffs = [0.33, -0.33, 0.67, 0, 0.33]
    assert analysis.permutation(diffs, draws=5_000, seed=7) == analysis.permutation(diffs, draws=5_000, seed=7)


def test_no_tasks_gives_no_result():
    assert analysis.permutation([], draws=10, seed=1)["p"] is None


def test_secondary_outcomes_per_arm():
    rows = rows_for("a", (1, 0, 0), (1, 1, 0))
    s = analysis.secondary(rows)
    assert s["plain"]["passes"] == 1 and s["refined"]["passes"] == 2 and s["refined"]["runs"] == 3
    assert s["plain"]["mean_graded_failed"] == pytest.approx(4 / 3)
    assert s["plain"]["median_agent_min"] == 2.0 and s["plain"]["cost_usd"] == 3.0


def test_disagreements_between_sandbox_and_regrade_are_counted():
    rows = rows_for("a", (1, 1, 1), (1, 1, 1))
    rows[0]["reward_sandbox"] = 0.0
    assert analysis.secondary(rows)["plain"]["sandbox_regrade_disagree"] == 1


def test_validity_checks_pass_on_clean_rows():
    rows = rows_for("a", (1, 0, 0), (1, 1, 0))
    checks = analysis.validity(rows, probes=[{"passed": True}], frozen_hash=FROZEN)
    assert all(ok for _, ok, _ in checks), checks


@pytest.mark.parametrize("change,label", [
    ({"notes_hash": "other"}, "frozen bundle"),
    ({"claude_version": "2.1.299"}, "Claude Code"),
    ({"audit_tests": True}, "/tests"),
    ({"regrade_valid": False}, "re-grade"),
])
def test_validity_flags_each_problem(change, label):
    rows = rows_for("a", (1, 0, 0), (1, 1, 0))
    rows[4].update(change)
    failed = [name for name, ok, _ in analysis.validity(rows, probes=[{"passed": True}], frozen_hash=FROZEN)
              if not ok]
    assert any(label in name for name in failed), failed


def test_validity_flags_a_plain_run_that_found_notes():
    rows = rows_for("a", (1, 0, 0), (1, 1, 0))
    rows[0]["claude_dir"] = True
    failed = [n for n, ok, _ in analysis.validity(rows, probes=[], frozen_hash=FROZEN) if not ok]
    assert any("plain" in n for n in failed)


def test_render_shows_the_result_and_every_task():
    rows = rows_for("a", (1, 0, 0), (1, 1, 0)) + rows_for("b", (1, 1, 1), (1, 1, 0))
    summary = analysis.summarize(rows, probes=[{"passed": True}], frozen_hash=FROZEN, draws=1000)
    text = analysis.render(summary, practice={"passes": 15, "runs": 30, "edits": 9}, learned="It learned X.",
                           deviations="- 2026-10-20: none")
    for needle in ("Mean d", "| a |", "| b |", "It learned X.", "2026-10-20", "sign-flip", "Limits"):
        assert needle in text, needle


def test_render_names_the_study_repository(monkeypatch):
    monkeypatch.setattr(config, "REPO_LABEL", "flipt")
    summary = analysis.summarize(rows_for("a", (1, 0, 0), (1, 1, 0)), probes=[{"passed": True}],
                                 frozen_hash=FROZEN, draws=100)
    text = analysis.render(summary, practice={"passes": 15, "runs": 30}, learned="", deviations="")
    assert "30 flipt practice tasks" in text and "unseen flipt tasks" in text
