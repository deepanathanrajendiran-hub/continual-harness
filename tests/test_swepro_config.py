import pytest

from bench.swepro import config


def test_pins_match_the_spec():
    assert config.SCALE_COMMIT == "66f92766bba642462d4bbe5479e83f91f9211862"
    assert config.HARBOR_VERSION == "0.24.0"
    assert config.CLAUDE_CODE_VERSION == "2.1.293"
    assert config.MODEL == "anthropic/claude-sonnet-5-5"
    assert config.EFFORT == "high"
    assert config.CLAUDE_ARM_SHA256 == "00755ae106b6925c1adb2b17e4c6d9b0c41eb4cc55bcad3581345b0aa3176c85"
    assert config.ALLOW_HOST == "api.anthropic.com"
    assert (config.SPLIT_SEED, config.ORDER_SEED, config.PERM_SEED) == (20261014, 20261015, 20261016)
    assert (config.N_PRACTICE, config.MIN_TEST, config.ATTEMPTS, config.PERM_DRAWS) == (30, 40, 3, 100_000)
    assert (config.GATE_HIGH, config.GATE_LOW) == (26, 4)


def test_the_smoke_and_flaky_tasks_are_excluded():
    assert config.SMOKE_TASK.startswith("instance_ansible__ansible-0ea40e09")
    assert config.FLAKY_TASK.startswith("instance_ansible__ansible-40ade1f8")
    assert set(config.EXCLUDED) == {config.SMOKE_TASK, config.FLAKY_TASK}


def test_runs_live_under_home_because_colima_shares_only_home(tmp_path):
    from pathlib import Path
    assert config.RUNS.is_relative_to(Path.home())


def test_job_name_round_trips():
    task = config.SMOKE_TASK
    name = config.job_name("test", task, "refined", 2)
    assert name == f"test__{task}__refined__a2"
    assert config.parse_job_name(name) == ("test", task, "refined", 2)


@pytest.mark.parametrize("args", [
    ("nope", "t", "plain", 1),
    ("test", "t", "nope", 1),
    ("test", "t", "plain", 0),
    ("test", "t", "plain", True),
    ("test", "a/b", "plain", 1),
    ("test", "", "plain", 1),
])
def test_job_name_refuses_bad_parts(args):
    with pytest.raises(ValueError):
        config.job_name(*args)


def test_practice_and_validation_arms_are_named():
    assert config.job_name("practice", "t", "refined", 1) == "practice__t__refined__a1"
    assert config.job_name("validate", "t", "oracle", 1) == "validate__t__oracle__a1"
    assert config.job_name("refine", "t", "refine", 1) == "refine__t__refine__a1"
    assert config.job_name("regrade", "t", "plain", 3) == "regrade__t__plain__a3"
