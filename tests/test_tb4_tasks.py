import json

from bench.tb4 import tasks

TOML = """
[metadata]
category = "{category}"
expert_time_estimate_hours = {est}

[environment]
cpus = {cpus}
memory_mb = {mem}
{gpus}
{skills}

[verifier]
environment_mode = "separate"
{venv}
"""


def make(root, name, *, category="Software", est=4, cpus=2, mem=4096, gpus="gpus = 0",
         skills="", venv="", compose=False):
    d = root / "tasks" / name
    (d / "environment").mkdir(parents=True)
    (d / "task.toml").write_text(TOML.format(category=category, est=est, cpus=cpus, mem=mem,
                                             gpus=gpus, skills=skills, venv=venv))
    if compose:
        (d / "environment" / "docker-compose.yaml").write_text("services: {}\n")
    return d


def test_a_plain_task_survives(tmp_path):
    meta = tasks.load_meta(make(tmp_path, "plain"))
    assert tasks.exclusion_reasons(meta) == []
    assert meta["estimate_h"] == 4.0 and isinstance(meta["estimate_h"], float)


def test_each_predicate_excludes(tmp_path):
    cases = {
        "gpu": dict(gpus="gpus = 1"),
        "cpu": dict(cpus=16),
        "mem": dict(mem=16384),
        "compose": dict(compose=True),
        "net": dict(venv="[verifier.environment]\nallow_internet = false"),
        "netmode": dict(venv='[verifier.environment]\nnetwork_mode = "no-network"'),
        "skills": dict(skills='skills_dir = "/app/.agents/skills"'),
        "coq-block-bound": {},
    }
    for name, kwargs in cases.items():
        reasons = tasks.exclusion_reasons(tasks.load_meta(make(tmp_path, name, **kwargs)))
        assert reasons, name


def test_missing_gpus_key_means_no_gpu(tmp_path):
    meta = tasks.load_meta(make(tmp_path, "nogpu", gpus=""))
    assert meta["gpus"] == 0 and tasks.exclusion_reasons(meta) == []


def test_limits_are_inclusive(tmp_path):
    meta = tasks.load_meta(make(tmp_path, "edge", cpus=8, mem=8192))
    assert tasks.exclusion_reasons(meta) == []


def test_band_is_inclusive_and_float(tmp_path):
    assert tasks.in_band(tasks.load_meta(make(tmp_path, "two", est=2)))
    assert tasks.in_band(tasks.load_meta(make(tmp_path, "eight", est="8.0")))
    assert not tasks.in_band(tasks.load_meta(make(tmp_path, "low", est=1.5)))
    assert not tasks.in_band(tasks.load_meta(make(tmp_path, "high", est=10)))


def test_survey_and_cli(tmp_path):
    make(tmp_path, "keep", est=4)
    make(tmp_path, "outside-band", est=1)
    make(tmp_path, "gpu", gpus="gpus = 1")
    result = tasks.survey(tmp_path)
    assert [m["name"] for m in result["survivors"]] == ["keep", "outside-band"]
    assert [m["name"] for m in result["band"]] == ["keep"]
    assert list(result["excluded"]) == ["gpu"]
    out = tmp_path / "survey.json"
    assert tasks.main(["--tb4", str(tmp_path), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["excluded"] == {"gpu": ["gpus=1"]}
