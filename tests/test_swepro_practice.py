import json

import pytest
from swepro_fakes import FakeHarbor, make_tasks, write

from bench.swepro import config, practice

P = [f"instance_ansible__ansible-{i:040d}-vp" for i in range(4)]


@pytest.fixture
def env(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    tasks = make_tasks(runs / "scale" / "v2" / "tasks", [*P, config.SMOKE_TASK])
    write(tmp_path / "skill" / "SKILL.md", "refine")
    probes = []
    monkeypatch.setattr(practice.probe, "run_probe", lambda runs, tasks, label, run: probes.append(label))
    return runs, tasks, tmp_path / "skill", probes


def go(env, harbor, order=P, **kw):
    runs, tasks, skill, _ = env
    return practice.run_practice(order, runs=runs, skill=skill, token="tok", run=harbor,
                                 pace=lambda: {"seven_day": 0.1}, **kw)


def test_each_practice_task_runs_with_the_notes_so_far_then_refines(env):
    runs, tasks, skill, probes = env
    harbor = FakeHarbor(runs, reward=lambda ph, t, a, n: 0.0 if t == P[1] else 1.0)
    records = go(env, harbor)
    names = [c for c in harbor.calls if isinstance(c, str)]
    assert names == [x for t in P for x in (config.job_name("practice", t, "refined", 1),
                                            config.job_name("refine", t, "refine", 1))]
    assert [r["feedback"] for r in records] == ["passed", "failed: 1 of 2 graded tests failed", "passed", "passed"]
    first, second = (harbor.kwargs[config.job_name("practice", t, "refined", 1)]["bundle_dir"] for t in P[:2])
    assert json.loads((runs / "practice" / "bundles" / "001" / "manifest.json").read_text())["files"] == {}
    assert ".claude/CLAUDE.md" in json.loads((runs / "practice" / "bundles" / "002" / "manifest.json").read_text())["files"]
    assert records[1]["bundle_hash"] == json.loads((runs / "practice" / "bundles" / "002" / "manifest.json").read_text())["hash"]
    assert records[0]["refine"]["entries_added"] == [f"{P[0][-4:]}-e1"]
    assert probes == ["practice start"]


def test_a_probe_runs_every_ten_tasks(env, monkeypatch):
    monkeypatch.setattr(config, "PROBE_EVERY", 2)
    go(env, FakeHarbor(env[0]))
    assert env[3] == ["practice start", "practice after 2 tasks"]


def test_practice_resumes_after_the_last_recorded_task(env):
    runs = env[0]
    go(env, FakeHarbor(runs), order=P[:2])
    harbor = FakeHarbor(runs)
    records = go(env, harbor)
    assert len(records) == 4
    assert [c for c in harbor.calls if isinstance(c, str)][0] == config.job_name("practice", P[2], "refined", 1)
    assert env[3] == ["practice start", "practice after 2 tasks"]


def test_a_record_with_a_different_task_at_its_index_stops_the_run(env):
    go(env, FakeHarbor(env[0]), order=P[:1])
    with pytest.raises(practice.PracticeError, match="order"):
        go(env, FakeHarbor(env[0]), order=list(reversed(P)))


def test_images_are_pulled_before_and_removed_after_each_task(env):
    harbor = FakeHarbor(env[0])
    go(env, harbor, order=P[:1])
    docker = [c for c in harbor.calls if isinstance(c, tuple)]
    assert docker[0][:2] == ("docker", "pull") and docker[-1][:3] == ("docker", "image", "rm")


@pytest.mark.parametrize("passes,decision", [(26, "stop_high"), (30, "stop_high"), (25, "ask_user"),
                                              (5, "ask_user"), (4, "stop_low"), (0, "stop_low")])
def test_gate(passes, decision):
    records = [{"reward": 1.0 if i < passes else 0.0, "valid": True, "cost_usd": 1.0, "tokens_in": 10,
                "tokens_out": 1, "refine": {"cost_usd": 0.5}} for i in range(30)]
    g = practice.gate(records, usage_start={"seven_day": 0.10}, usage_end={"seven_day": 0.40})
    assert g["passes"] == passes and g["decision"] == decision
    assert g["mean_agent_cost_usd"] == 1.0 and g["mean_refine_cost_usd"] == 0.5
    assert g["seven_day_used"] == pytest.approx(0.30)
    # 0.30 over 30 tasks; the agent's share of cost is 2/3; the test phase has 300 agent runs
    assert g["projected_test_seven_day"] == pytest.approx(0.30 / 30 * (2 / 3) * 300)


def test_gate_refuses_an_incomplete_practice():
    with pytest.raises(practice.PracticeError):
        practice.gate([{"reward": 1.0, "valid": True}] * 29, usage_start={}, usage_end={})


def test_a_resumed_task_keeps_the_bundle_it_ran_with(env):
    runs = env[0]
    go(env, FakeHarbor(runs), order=P[:1])
    first = json.loads((runs / "practice" / "bundles" / "001" / "manifest.json").read_text())["hash"]
    (runs / "practice" / "records" / "001.json").unlink()  # crashed after refine, before the record
    records = go(env, FakeHarbor(runs), order=P[:1])
    assert records[0]["bundle_hash"] == first


def test_gate_counts_edits_by_layer_and_sessions_that_changed_nothing():
    changes = [[".claude/CLAUDE.md"], ["memory/MEMORY.md", "memory/a.md"], [".claude/skills/x/SKILL.md"],
               [".claude/agents/r.md"], []] + [[]] * 25
    records = [{"reward": 1.0 if i < 10 else 0.0, "valid": True, "cost_usd": 1.0,
                "refine": {"cost_usd": 0.5, "changed": c, "entries_added": ["e"] if c else []}}
               for i, c in enumerate(changes)]
    g = practice.gate(records, usage_start={}, usage_end={})
    assert g["edits_by_layer"] == {"rho": 1, "M": 1, "G": 1, "K": 1}
    assert g["sessions_without_change"] == 26 and g["edits"] == 4
    assert g["projected_test_seven_day"] is None

def test_a_crash_after_a_later_tasks_refine_resumes_from_the_saved_refine_record(env):
    runs = env[0]
    first = go(env, FakeHarbor(runs), order=P[:2])
    (runs / "practice" / "records" / "002.json").unlink()  # crashed after refine 2 absorbed, before the record
    records = go(env, FakeHarbor(runs), order=P[:2])
    assert records[1]["refine"]["entries_added"] == first[1]["refine"]["entries_added"] != []
    assert records[1]["refine"]["changed"] == first[1]["refine"]["changed"]
