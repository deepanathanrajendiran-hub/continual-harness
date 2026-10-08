from bench.tb4 import config

SHARED = (
    "You have 105 minutes. Keep working until the task is fully complete; do not stop early. "
    "Before finishing, verify your work against the task's requirements with your own tests or checks. "
    "If you cannot finish within 105 minutes, stop and state exactly what is complete and what is incomplete."
)
HORIZON = (
    "Before other work, use the horizon skill to create a goal with a verification gate you write, "
    "a review criterion, and the budget `--max-minutes 100 --max-turns 200`; follow that goal until "
    "it completes or its budget runs out."
)
SPEC = config.REPO_ROOT / "docs/superpowers/specs/2026-10-07-tb4-horizon-benchmark-design.md"


def test_arm_texts_match_the_spec_verbatim():
    assert (config.PROMPTS / "control.md").read_text() == SHARED + "\n"
    assert (config.PROMPTS / "horizon.md").read_text() == SHARED + "\n\n" + HORIZON + "\n"


def test_arm_texts_differ_only_by_the_horizon_sentence():
    control = (config.PROMPTS / "control.md").read_text().rstrip("\n")
    horizon = (config.PROMPTS / "horizon.md").read_text().rstrip("\n")
    assert horizon.startswith(control)
    assert horizon[len(control):].strip() == HORIZON


def test_spec_quotes_the_same_arm_texts():
    spec = SPEC.read_text()
    assert SHARED in spec and HORIZON in spec


def test_spec_records_the_plan_stage_corrections():
    assert "## Plan-stage corrections (2026-10-07)" in SPEC.read_text()


def test_fixed_settings():
    assert config.AGENT_TIMEOUT_MULTIPLIER * 28800 == config.HARD_LIMIT_SEC == 7200
    assert config.MODEL == "anthropic/claude-sonnet-5-5"
    assert config.EFFORT == "high"
    assert config.CLAUDE_CODE_VERSION == "2.1.293"
    assert config.HARBOR_VERSION == "0.24.0"
    assert config.BUNDLE_COMMIT == "2f65f2a24d753b6875bd126fc989335baff82ed8"
    assert config.TB4_COMMIT == "452bf305c6daa62fc59061d22133a7cbc7c1572e"
    assert config.SEED == 20261007 and config.N_MEASURED == 10
    assert config.ARMS == ("control", "horizon")
    assert config.agent_tag("x") == "tb4-local/x:v4.0.0"
    assert config.verifier_tag("x") == "tb4-local/x-verifier:v4.0.0"
    assert config.DEADLINE_SENTENCE == "You have 28800 seconds to complete this task. "


def test_judge_rubric_is_arm_neutral():
    rubric = (config.PROMPTS / "judge.md").read_text()
    assert rubric.count("{{FINAL_MESSAGE}}") == 1
    lowered = rubric.lower()
    for word in ("control", "baseline", "treatment", "horizon"):
        assert word not in lowered
