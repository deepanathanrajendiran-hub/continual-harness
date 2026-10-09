import re
from pathlib import Path

import pytest

from bench.evo import config
from bench.tb4 import bundle
from bench.tb4 import config as tb4

SPEC = config.REPO_ROOT / "docs/superpowers/specs/2026-10-09-evocode-horizon-design.md"
CONTROL_30 = (
    "You have 30 minutes for this request. Keep working until it is fully complete; do not stop early. "
    "Before finishing, verify your work against the request with your own tests or checks. "
    "If you cannot finish within 30 minutes, stop and state exactly what is complete and what is incomplete."
)
HORIZON_60 = (
    "You have 60 minutes for this request. Keep working until it is fully complete; do not stop early. "
    "Before finishing, verify your work against the request with your own tests or checks. "
    "If you cannot finish within 60 minutes, stop and state exactly what is complete and what is incomplete."
    "\n\n"
    "Use the horizon skill for this request with `--max-turns 200`, and give the goal "
    "the minutes that remain of your 60 when you create it."
)
# Docker's reference grammar: lowercase path components, then a tag.
DOCKER_REF = re.compile(r"^[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*(?:/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*)*"
                        r":[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")


def _flat(text: str) -> str:
    """Join the spec's wrapped lines and blockquotes into single spaces."""
    return re.sub(r"\s+", " ", re.sub(r"\n>\s?", "\n", text))


def test_paths():
    assert config.REPO_ROOT == Path(config.__file__).resolve().parents[2]
    assert (config.REPO_ROOT / "bench" / "tb4" / "test.sh").is_file()
    assert config.RUNS == Path.home() / "Documents" / "evocode-horizon-runs"
    assert config.DOCS == config.REPO_ROOT / "docs" / "evaluations" / "evocode-horizon"
    assert config.REPO_ROOT not in config.RUNS.parents


def test_dataset_and_code_pins():
    assert config.DATASET_REPO == "UnipatAI/EvoCodeBench"
    assert config.DATASET_REVISION == "9fcae3e5539d1c0e85e2481fe06bd6af42cc4bc6"
    assert config.ARCHIVE_PATH == "archives/evocodebench_wotraj.tar.zst"
    assert config.ARCHIVE_LFS_OID == "a13d0cb47574282372c59366217ac68d895ff49d1387c81098b058f739906184"
    assert config.EVO_CODE_URL == "https://github.com/UniPat-AI/EvoCodeBench"
    assert config.EVO_CODE_COMMIT == "f8fcfaa1c9ad1c5b0bbc433323b587e4ddea2f32"


def test_versions_model_and_timeouts_match_the_spec_and_tb4():
    assert config.HARBOR_VERSION == tb4.HARBOR_VERSION == "0.24.0"
    assert config.CLAUDE_CODE_VERSION == tb4.CLAUDE_CODE_VERSION == "2.1.293"
    assert config.MODEL == tb4.MODEL == "anthropic/claude-sonnet-5-5"
    assert config.EFFORT == tb4.EFFORT == "high"
    assert config.MAX_OUTPUT_TOKENS == tb4.MAX_OUTPUT_TOKENS == "128000"
    assert config.AGENT_TIMEOUT_MULTIPLIER == 1.0
    assert config.AGENT_SETUP_TIMEOUT_MULTIPLIER == 2.0


def test_bundle_pin_and_modules():
    assert config.BUNDLE_COMMIT == "f73975ad6db67b8d9ac0d822ed569a807e9eae59"
    assert config.BUNDLE_MODULES == bundle.MODULES + ("reviewing",)
    assert bundle.MODULES == ("filelock", "gate", "goal", "paths", "refine_log", "steps", "task_state",
                              "tree_hash")


def test_draw_constants():
    assert config.SEED == 20261009
    assert config.DOMAINS == ("d1", "d5", "d8", "d9", "d10", "d11", "d12")
    assert len(config.POOL) == 13 == len(set(config.POOL))
    assert config.POOL == tuple(sorted(config.POOL))
    assert config.EXCLUDED_PREFIX == "theme_d11_w2_"
    assert config.WALKTHROUGH == "theme_d11_w2_scientific_numerical_brownfield_modification__not_1234"
    assert config.WALKTHROUGH.startswith(config.EXCLUDED_PREFIX)
    assert not any(t.startswith(config.EXCLUDED_PREFIX) for t in config.POOL)
    domains = [re.match(r"theme_(d\d+)_w\d+_", t).group(1) for t in config.POOL]
    assert set(domains) == set(config.DOMAINS)


def test_pool_matches_the_spec_list():
    shorts = []
    for task in config.POOL:
        m = re.fullmatch(r"theme_(d\d+_w\d+)_[a-z0-9_]+?(__not_1234)?", task)
        assert m, task
        shorts.append(m.group(1) + (m.group(2) or ""))
    assert ", ".join(shorts) + "." in _flat(SPEC.read_text())


def test_arms_n_rule_reused_names_and_freeze():
    assert config.ARMS == ("control", "horizon")
    assert config.PHASES == ("check", "canary", "dry", "main")
    assert config.N_CHOICES == (10, 8, 6)
    assert config.BUDGET_AGENT_HOURS == 60.0
    assert config.ROUNDS_PER_TASK_PLAN == 10
    assert config.WEEKLY_CEILING == 0.9 and config.FIVE_HOUR_CEILING == 0.9
    assert config.KEYCHAIN_SERVICE == tb4.KEYCHAIN_SERVICE == "tb4-horizon-claude-token"
    assert config.JUDGE_MODEL == tb4.JUDGE_MODEL
    assert config.PROBE_MODEL == tb4.PROBE_MODEL
    assert config.FREEZE_TAG == "evo-prereg" != tb4.FREEZE_TAG


def test_prompt_text_for_both_arms_at_30_and_60():
    assert config.prompt_text("control", 30) == CONTROL_30
    assert config.prompt_text("horizon", 60) == HORIZON_60
    assert config.prompt_text("control", 60) == HORIZON_60.split("\n\n")[0]
    assert config.prompt_text("horizon", 30) == (
        CONTROL_30 + "\n\n" + config.HORIZON_SENTENCE.replace("{M}", "30"))
    for minutes in (30, 60):
        control = config.prompt_text("control", minutes)
        horizon = config.prompt_text("horizon", minutes)
        assert horizon.startswith(control + "\n\n")
        assert "{M}" not in horizon and "{" not in horizon


def test_prompt_text_rejects_unknown_arms_and_bad_minutes():
    with pytest.raises(ValueError):
        config.prompt_text("baseline", 30)
    for bad in (0, -5, 30.0, "30", True):
        with pytest.raises(ValueError):
            config.prompt_text("control", bad)


def test_spec_quotes_the_same_prompt_texts():
    spec = _flat(SPEC.read_text())
    assert config.SHARED_PROMPT.replace("{M}", "M") in spec
    assert config.HORIZON_SENTENCE.replace("{M}", "M") in spec


def test_prompts_never_mention_rounds_earlier_requests_or_the_benchmark():
    text = (config.SHARED_PROMPT + " " + config.HORIZON_SENTENCE).lower()
    for word in ("round", "earlier", "previous", "benchmark", "evocode", "step"):
        assert word not in text


def test_image_tag():
    assert config.image_tag("theme_d1_w2_code_build_brownfield_modification") == (
        "evo-local/theme_d1_w2_code_build_brownfield_modification:9fcae3e5539d")
    for task in (*config.POOL, config.WALKTHROUGH):
        assert DOCKER_REF.match(config.image_tag(task)), task


def test_job_name():
    assert config.job_name("main", config.POOL[1], "horizon", 1) == (
        "main__theme_d10_w4_ml_ai_mlops_migration_upgrade__not_1234__horizon__a1")
    assert config.job_name("dry", config.WALKTHROUGH, "control", 2) == (
        "dry__theme_d11_w2_scientific_numerical_brownfield_modification__not_1234__control__a2")
    for phase in config.PHASES:
        assert config.job_name(phase, "dummy", "control", 1).startswith(phase + "__")


def test_job_name_rejects_bad_parts():
    with pytest.raises(ValueError):
        config.job_name("pilot", "t", "control", 1)
    with pytest.raises(ValueError):
        config.job_name("main", "t", "control", 0)
    with pytest.raises(ValueError):
        config.job_name("main", "a/b", "control", 1)
    with pytest.raises(ValueError):
        config.job_name("main", "t", "con__trol", 1)
    with pytest.raises(ValueError):
        config.job_name("main", "t", "", 1)
