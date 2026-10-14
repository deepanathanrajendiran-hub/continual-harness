import hashlib
import subprocess

import pytest

from bench.swepro import config, dataset

OTHER = "instance_flipt-io__flipt-02e21636c58e86c51119b63e0fb5ca7b813b07b1"
A1 = "instance_ansible__ansible-1111111111111111111111111111111111111111-vaaaa"
A2 = "instance_ansible__ansible-2222222222222222222222222222222222222222-vbbbb"


def make_task(tasks, name, image=None):
    d = tasks / name
    (d / "environment").mkdir(parents=True)
    (d / "task.toml").write_text(
        f'[agent]\nnetwork_mode = "no-network"\n\n[environment]\n'
        f'docker_image = "{image or "ghcr.io/scaleapi/swe-bench_pro-v2:" + name}"\n')
    return d


@pytest.fixture
def tree(tmp_path):
    tasks = tmp_path / "scale" / "v2" / "tasks"
    for name in (A2, A1, OTHER, *config.EXCLUDED):
        make_task(tasks, name)
    (tasks / "instance_ansible__ansible-no-toml").mkdir()
    return tasks


def test_repo_tasks_are_sorted_and_need_a_task_toml(tree):
    assert dataset.repo_tasks(tree) == sorted([A1, A2, *config.EXCLUDED])


def test_the_study_pool_drops_the_smoke_and_flaky_tasks(tree):
    assert dataset.study_pool(tree) == [A1, A2]


def test_the_pool_refuses_a_tree_missing_an_excluded_task(tree):
    import shutil
    shutil.rmtree(tree / config.FLAKY_TASK)
    with pytest.raises(dataset.DatasetError, match="40ade1f8"):
        dataset.study_pool(tree)


def test_docker_image_comes_from_task_toml(tree):
    assert dataset.docker_image(tree / A1) == f"ghcr.io/scaleapi/swe-bench_pro-v2:{A1}"


def test_docker_image_refuses_a_task_without_one(tmp_path):
    d = tmp_path / "t"
    d.mkdir()
    (d / "task.toml").write_text("[environment]\n")
    with pytest.raises(dataset.DatasetError):
        dataset.docker_image(d)


def git_ok(commit=config.SCALE_COMMIT):
    def run(cmd, **kw):
        out = commit + "\n" if cmd[-2:] == ["rev-parse", "HEAD"] else ""
        return subprocess.CompletedProcess(cmd, 0, out, "")
    return run


def test_fetch_clones_sparsely_and_checks_the_pinned_commit(tmp_path):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        if cmd[:2] == ["git", "clone"]:
            (tmp_path / "scale" / ".git").mkdir(parents=True)
        out = config.SCALE_COMMIT + "\n" if cmd[-2:] == ["rev-parse", "HEAD"] else ""
        return subprocess.CompletedProcess(cmd, 0, out, "")

    tasks = dataset.fetch(tmp_path / "scale", run=run)
    assert tasks == tmp_path / "scale" / "v2" / "tasks"
    flat = [" ".join(c) for c in calls]
    assert any("clone" in c and "--filter=blob:none" in c and "--no-checkout" in c for c in flat)
    assert any("sparse-checkout set v2" in c for c in flat)
    assert any(c.endswith(f"checkout {config.SCALE_COMMIT}") for c in flat)


def test_fetch_reuses_a_clone_at_the_pinned_commit(tmp_path):
    (tmp_path / "scale" / ".git").mkdir(parents=True)
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return git_ok()(cmd, **kw)

    dataset.fetch(tmp_path / "scale", run=run)
    assert not any(c[:2] == ["git", "clone"] for c in calls)


def test_fetch_refuses_a_clone_at_another_commit(tmp_path):
    (tmp_path / "scale" / ".git").mkdir(parents=True)
    with pytest.raises(dataset.DatasetError, match="commit"):
        dataset.fetch(tmp_path / "scale", run=git_ok("0" * 40))


def test_install_replay_copies_the_pinned_file(tmp_path, monkeypatch):
    src = tmp_path / "scale" / "v2" / "tooling" / "patch_replay.py"
    src.parent.mkdir(parents=True)
    src.write_text("print('replay')\n")
    monkeypatch.setattr(config, "REPLAY_SHA256", hashlib.sha256(src.read_bytes()).hexdigest())
    out = dataset.install_replay(tmp_path / "scale", tmp_path / "tools")
    assert out.read_text() == "print('replay')\n"


def test_install_replay_refuses_a_changed_file(tmp_path):
    src = tmp_path / "scale" / "v2" / "tooling" / "patch_replay.py"
    src.parent.mkdir(parents=True)
    src.write_text("tampered\n")
    with pytest.raises(dataset.DatasetError, match="sha256"):
        dataset.install_replay(tmp_path / "scale", tmp_path / "tools")
    assert not (tmp_path / "tools" / "patch_replay.py").exists()
