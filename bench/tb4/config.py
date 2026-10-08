"""Fixed settings for the Terminal-Bench 4.0 Horizon pilot. Change nothing here after the freeze."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS = Path.home() / "Documents" / "tb4-horizon-runs"
PROMPTS = REPO_ROOT / "docs" / "evaluations" / "tb4-horizon-pilot" / "prompts"

TB4_URL = "https://github.com/harbor-framework/terminal-bench.git"
TB4_TAG = "v4.0.0"
TB4_COMMIT = "452bf305c6daa62fc59061d22133a7cbc7c1572e"
HARBOR_VERSION = "0.24.0"
CLAUDE_CODE_VERSION = "2.1.293"
MODEL = "anthropic/claude-sonnet-5-5"
EFFORT = "high"
MAX_OUTPUT_TOKENS = "128000"
AGENT_TIMEOUT_MULTIPLIER = 0.25          # every TB4 task sets [agent] timeout_sec = 28800
AGENT_SETUP_TIMEOUT_MULTIPLIER = 2.0
HARD_LIMIT_SEC = 7200

BUNDLE_COMMIT = "2f65f2a24d753b6875bd126fc989335baff82ed8"
SEED = 20261007
N_MEASURED = 10
BAND_HOURS = (2.0, 8.0)
MAX_CPUS = 8
MAX_MEMORY_MB = 8192
AMD64_ONLY = (  # terminal-bench issues #1802-#1806
    "coq-block-bound", "hof-topology-interpenetration", "math-eval-grader",
    "gsea-proteomics", "wdm-design",
)
DEADLINE_SENTENCE = "You have 28800 seconds to complete this task. "

JUDGE_MODEL = "claude-opus-5-5"
PROBE_MODEL = "claude-sonnet-5-5"  # the trial model, so the probe sees the same usage windows
KEYCHAIN_SERVICE = "tb4-horizon-claude-token"
ARMS = ("control", "horizon")
FREEZE_TAG = "tb4-pilot-freeze"
HOST_SLEPT = "host slept during trial"


def agent_tag(task: str) -> str:
    return f"tb4-local/{task}:{TB4_TAG}"


def verifier_tag(task: str) -> str:
    return f"tb4-local/{task}-verifier:{TB4_TAG}"
