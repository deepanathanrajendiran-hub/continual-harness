import json

import pytest
from swepro_fakes import FakeHarbor, make_tasks

from bench.swepro import config, pilot

OL = config.STUDIES["openlibrary"]["excluded"]
FL = config.STUDIES["flipt"]["excluded"]


@pytest.fixture
def runs(tmp_path):
    runs = tmp_path / "runs"
    make_tasks(runs / "scale" / "v2" / "tasks", [*OL, *FL])
    return runs


def go(runs, harbor, task):
    paces = []
    record = pilot.pilot_task(task, runs=runs, token="tok", run=harbor, pace=lambda: paces.append(1))
    return record, paces


def test_a_pilot_task_runs_plain_claude_code_then_validates(runs):
    harbor = FakeHarbor(runs, reward=lambda phase, task, arm, attempt: {"oracle": 1.0, "nop": 0.0}.get(arm, 0.0))
    record, _ = go(runs, harbor, OL[0])
    names = [c for c in harbor.calls if isinstance(c, str)]
    assert names == [config.job_name("pilot", OL[0], "plain", 1), config.job_name("validate", OL[0], "oracle", 1),
                     config.job_name("validate", OL[0], "nop", 1)]
    assert "bundle_dir" not in harbor.kwargs[names[0]] and "tools_dir" in harbor.kwargs[names[0]]
    assert (record["repo"], record["reward"], record["valid"], record["counted"]) == ("openlibrary", 0.0, True, True)
    assert json.loads((runs / "pilot" / f"{OL[0]}.json").read_text()) == record


def test_a_saved_pilot_record_is_not_run_again(runs):
    harbor = FakeHarbor(runs)
    go(runs, harbor, FL[0])
    n = len(harbor.calls)
    go(runs, harbor, FL[0])
    assert len(harbor.calls) == n


def test_a_task_that_fails_validation_or_crashes_the_agent_is_not_counted(runs):
    bad_oracle = FakeHarbor(runs, reward=lambda phase, task, arm, attempt: 0.0)
    assert go(runs, bad_oracle, OL[1])[0]["counted"] is False
    crash = FakeHarbor(runs, reward=lambda phase, task, arm, attempt:
                       "RuntimeError" if phase == "pilot" else {"oracle": 1.0, "nop": 0.0}[arm])
    record, paces = go(runs, crash, OL[2])
    assert record["counted"] is False and record["agent_reason"] and len(paces) == config.INFRA_RERUNS


def rec(repo, reward, counted=True):
    return {"repo": repo, "reward": reward, "counted": counted}


def test_summary_counts_passes_among_counted_tasks():
    s = pilot.summarize([rec("openlibrary", 1.0), rec("openlibrary", 0.0), rec("openlibrary", 1.0, False),
                         rec("flipt", 1.0)])
    assert s["openlibrary"] == {"counted": 2, "passes": 1, "rate": 0.5, "tasks": 3}
    assert s["flipt"] == {"counted": 1, "passes": 1, "rate": 1.0, "tasks": 1}


@pytest.mark.parametrize("rates,choice", [
    ({"openlibrary": (6, 8), "flipt": (4, 8)}, "flipt"),          # closest to half
    ({"openlibrary": (3, 8), "flipt": (5, 8)}, "openlibrary"),    # tie goes to the first candidate
    ({"openlibrary": (8, 8), "flipt": (7, 8)}, None),             # both at or above the gate's ceiling
    ({"openlibrary": (0, 8), "flipt": (8, 8)}, None),             # floor and ceiling
    ({"openlibrary": (2, 3), "flipt": (8, 8)}, None),             # too few counted tasks to judge
])
def test_choose_picks_the_repository_closest_to_half_inside_the_gate(rates, choice):
    summary = {repo: {"passes": p, "counted": n, "rate": p / n, "tasks": 8} for repo, (p, n) in rates.items()}
    assert pilot.choose(summary) == choice
