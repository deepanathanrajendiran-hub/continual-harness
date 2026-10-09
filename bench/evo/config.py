"""Fixed settings for the EvoCode-Bench first look at Horizon v2. Change nothing here after the freeze.

Spec: docs/superpowers/specs/2026-10-09-evocode-horizon-design.md
"""
from pathlib import Path

from bench.tb4 import bundle as _tb4_bundle
from bench.tb4 import config as _tb4

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS = Path.home() / "Documents" / "evocode-horizon-runs"
DOCS = REPO_ROOT / "docs" / "evaluations" / "evocode-horizon"

DATASET_REPO = "UnipatAI/EvoCodeBench"
DATASET_REVISION = "9fcae3e5539d1c0e85e2481fe06bd6af42cc4bc6"
ARCHIVE_PATH = "archives/evocodebench_wotraj.tar.zst"
# The LFS oid (sha256) the HF paths-info API reported for ARCHIVE_PATH at DATASET_REVISION on 2026-10-09.
ARCHIVE_LFS_OID = "a13d0cb47574282372c59366217ac68d895ff49d1387c81098b058f739906184"
EVO_CODE_URL = "https://github.com/UniPat-AI/EvoCodeBench"
EVO_CODE_COMMIT = "f8fcfaa1c9ad1c5b0bbc433323b587e4ddea2f32"

HARBOR_VERSION = "0.24.0"
CLAUDE_CODE_VERSION = "2.1.293"
MODEL = "anthropic/claude-sonnet-5-5"
EFFORT = "high"
MAX_OUTPUT_TOKENS = "128000"
AGENT_TIMEOUT_MULTIPLIER = 1.0
AGENT_SETUP_TIMEOUT_MULTIPLIER = 2.0

BUNDLE_COMMIT = "f73975ad6db67b8d9ac0d822ed569a807e9eae59"
BUNDLE_MODULES = _tb4_bundle.MODULES + ("reviewing",)  # v2's cli.py imports reviewing

SEED = 20261009
DOMAINS = ("d1", "d5", "d8", "d9", "d10", "d11", "d12")
POOL = (
    "theme_d10_w11_ml_ai_mlops_automation_scripting",
    "theme_d10_w4_ml_ai_mlops_migration_upgrade__not_1234",
    "theme_d10_w9_ml_ai_mlops_reproducibility_verification",
    "theme_d11_w9_scientific_numerical_reproducibility_verification",
    "theme_d12_w1_automation_productivity_greenfield_implementation",
    "theme_d1_w11_code_build_automation_scripting",
    "theme_d1_w2_code_build_brownfield_modification",
    "theme_d1_w5_code_build_integration_e2e_wiring",
    "theme_d5_w1_data_engineering_greenfield_implementation",
    "theme_d5_w5_data_engineering_integration_e2e_wiring",
    "theme_d5_w9_data_engineering_reproducibility_verification",
    "theme_d8_w5_cloud_devops_integration_e2e_wiring",
    "theme_d9_w11_security_automation_scripting",
)
EXCLUDED_PREFIX = "theme_d11_w2_"
WALKTHROUGH = "theme_d11_w2_scientific_numerical_brownfield_modification__not_1234"

ARMS = ("control", "horizon")
PHASES = ("check", "canary", "dry", "main")

N_CHOICES = (10, 8, 6)
BUDGET_AGENT_HOURS = 60.0
ROUNDS_PER_TASK_PLAN = 10
WEEKLY_CEILING = 0.9
FIVE_HOUR_CEILING = 0.9

KEYCHAIN_SERVICE = _tb4.KEYCHAIN_SERVICE
JUDGE_MODEL = _tb4.JUDGE_MODEL
PROBE_MODEL = _tb4.PROBE_MODEL
FREEZE_TAG = "evo-prereg"

SHARED_PROMPT = (
    "You have {M} minutes for this request. Keep working until it is fully complete; do not stop early. "
    "Before finishing, verify your work against the request with your own tests or checks. "
    "If you cannot finish within {M} minutes, stop and state exactly what is complete and what is incomplete."
)
HORIZON_SENTENCE = (
    "Use the horizon skill for this request with `--max-turns 200`, and give the goal "
    "the minutes that remain of your {M} when you create it."
)


def prompt_text(arm: str, minutes: int) -> str:
    """The extra instruction for one arm: the shared paragraph, plus the Horizon sentence for horizon."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes <= 0:
        raise ValueError(f"minutes must be a positive int, not {minutes!r}")
    text = SHARED_PROMPT.replace("{M}", str(minutes))
    if arm == "horizon":
        text += "\n\n" + HORIZON_SENTENCE.replace("{M}", str(minutes))
    return text


def image_tag(task: str) -> str:
    return f"evo-local/{task}:{DATASET_REVISION[:12]}"


def job_name(phase: str, task: str, arm: str, attempt: int) -> str:
    """`{phase}__{task}__{arm}__a{attempt}`; task names may contain `__`, so arm and phase may not."""
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase!r}")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError(f"attempt must be an int >= 1, not {attempt!r}")
    if not task or not arm or "__" in arm or any("/" in part for part in (task, arm)):
        raise ValueError(f"bad task or arm: {task!r}, {arm!r}")
    return f"{phase}__{task}__{arm}__a{attempt}"
