import json

import pytest
from swepro_fakes import FakeHarbor, make_tasks, write

from bench.swepro import bundle, config, regrade, run

T = [f"instance_ansible__ansible-{i:040d}-vt" for i in range(3)]


@pytest.fixture
def env(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    make_tasks(runs / "scale" / "v2" / "tasks", [*T, config.SMOKE_TASK])
    write(runs / "refine" / "state" / "app" / "CLAUDE.md", "frozen rule")
    bundle.export(runs / "refine" / "state", runs / "bundle")
    probes = []
    monkeypatch.setattr(run.probe, "run_probe", lambda runs, tasks, label, run: probes.append(label))
    return runs, probes


def go(runs, harbor, order=T):
    paces = []
    run.run_test(order, runs=runs, token="tok", freeze="abc", run=harbor, pace=lambda: paces.append(1))
    return paces


def test_each_task_runs_three_pairs_then_regrades_all_six(env):
    runs, probes = env
    harbor = FakeHarbor(runs)
    paces = go(runs, harbor, order=T[:1])
    names = [c for c in harbor.calls if isinstance(c, str)]
    tests = [n for n in names if n.startswith("test__")]
    assert sorted(tests) == sorted(config.job_name("test", T[0], arm, a) for a in (1, 2, 3) for arm in config.ARMS)
    assert sorted(names[-6:]) == sorted(config.job_name("regrade", T[0], arm, a) for a in (1, 2, 3)
                                        for arm in config.ARMS)
    assert len(paces) == 3 and probes == ["test start"]


def test_only_the_refined_arm_gets_the_bundle(env):
    runs, _ = env
    harbor = FakeHarbor(runs)
    go(runs, harbor, order=T[:1])
    assert harbor.kwargs[config.job_name("test", T[0], "refined", 1)]["bundle_dir"] == str(runs / "bundle")
    assert "bundle_dir" not in harbor.kwargs[config.job_name("test", T[0], "plain", 1)]
    rec = json.loads((runs / "records" / f"{config.job_name('test', T[0], 'refined', 2)}.json").read_text())
    assert rec["notes"]["hash"] == bundle.verify(runs / "bundle") and rec["freeze"] == "abc"


def test_regrade_points_the_replay_agent_at_the_final_try(env):
    runs, _ = env
    seen = {"n": 0}

    def reward(phase, task, arm, attempt):
        if phase == "test" and arm == "plain" and attempt == 1:
            seen["n"] += 1
            return "RuntimeError" if seen["n"] == 1 else 1.0
        return 1.0

    harbor = FakeHarbor(runs, reward=reward)
    go(runs, harbor, order=T[:1])
    job = config.job_name("test", T[0], "plain", 1)
    rec = json.loads((runs / "records" / f"{job}.json").read_text())
    assert rec["final_job"] == f"{job}-rerun1" and [t["reason"] for t in rec["tries"]] == ["infrastructure", None]
    replay = harbor.kwargs[config.job_name("regrade", T[0], "plain", 1)]
    assert replay["source_job"] == str(runs / "jobs" / f"{job}-rerun1")


def test_the_run_resumes_at_the_first_unfinished_task(env):
    runs, probes = env
    go(runs, FakeHarbor(runs), order=T[:1])
    harbor = FakeHarbor(runs)
    go(runs, harbor)
    names = [c for c in harbor.calls if isinstance(c, str)]
    assert not any(T[0] in n for n in names) and any(T[1] in n for n in names)
    assert probes == ["test start", "test after 1 tasks"]


def test_a_half_finished_task_reruns_only_its_missing_runs(env):
    runs, _ = env
    go(runs, FakeHarbor(runs), order=T[:1])
    (runs / "regrade" / f"{config.job_name('regrade', T[0], 'refined', 3)}.json").unlink()
    (runs / "records" / f"{config.job_name('test', T[0], 'plain', 2)}.json").unlink()
    harbor = FakeHarbor(runs)
    go(runs, harbor, order=T[:1])
    assert [c for c in harbor.calls if isinstance(c, str)] == []  # both job directories are read, not rerun
    assert (runs / "records" / f"{config.job_name('test', T[0], 'plain', 2)}.json").exists()


def test_a_job_killed_before_its_result_is_rerun_under_the_next_name(env):
    runs, _ = env
    job = config.job_name("test", T[0], "plain", 1)
    (runs / "jobs" / job).mkdir(parents=True)  # Harbor was killed: no result.json
    harbor = FakeHarbor(runs)
    go(runs, harbor, order=T[:1])
    rec = json.loads((runs / "records" / f"{job}.json").read_text())
    assert [t["job"] for t in rec["tries"]] == [job, f"{job}-rerun1"]
    assert rec["tries"][0]["reason"] == "infrastructure" and rec["valid"]


def test_images_are_removed_even_when_a_run_crashes(env):
    runs, _ = env

    class Boom(FakeHarbor):
        def __call__(self, cmd, **kw):
            if cmd[0] == "harbor":
                raise KeyboardInterrupt
            return super().__call__(cmd, **kw)

    harbor = Boom(runs)
    with pytest.raises(KeyboardInterrupt):
        go(runs, harbor, order=T[:1])
    assert harbor.calls[-1][:3] == ("docker", "image", "rm")


def test_regrade_records_reward_and_graded_counts(env):
    runs, _ = env
    harbor = FakeHarbor(runs, reward=lambda ph, t, a, n: 0.0)
    rec = regrade.regrade("test__x__plain__a1", T[0], "plain", 1, runs=runs, run=harbor)
    assert rec["reward"] == 0.0 and (rec["graded_failed"], rec["graded_total"]) == (1, 2)
    again = regrade.regrade("test__x__plain__a1", T[0], "plain", 1, runs=runs, run=lambda *a, **k: pytest.fail())
    assert again == rec
