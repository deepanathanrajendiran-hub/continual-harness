"""Fixed settings for the SWE-bench Pro refine study. Change nothing here after the freeze.

Spec: docs/superpowers/specs/2026-10-14-swepro-refine-design.md
"""
from pathlib import Path

from bench.tb4 import config as _tb4

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS = Path.home() / "swepro-runs"  # Colima shares only $HOME with containers
DOCS = REPO_ROOT / "docs" / "evaluations" / "swepro-refine"
SPEC = "docs/superpowers/specs/2026-10-14-swepro-refine-design.md"

SCALE_URL = "https://github.com/scaleapi/SWE-bench_Pro-os.git"
SCALE_COMMIT = "66f92766bba642462d4bbe5479e83f91f9211862"
REPLAY_SHA256 = "5c8b344de37164e9723f1724c2573013957fb644c3913a64c12c1718c737d876"  # v2/tooling/patch_replay.py
REPO_PREFIX = "instance_ansible__ansible-"
SMOKE_TASK = ("instance_ansible__ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8"
              "-v30a923fb5c164d6cd18280c02422f75e611e8fb2")
FLAKY_TASK = ("instance_ansible__ansible-40ade1f84b8bb10a63576b0ac320c13f57c87d34"
              "-v6382ea168a93d80a64aab1fbd8c4f02dc5ada5bf")  # timing-sensitive per Scale's GATE.md
EXCLUDED = (SMOKE_TASK, FLAKY_TASK)

HARBOR_VERSION = "0.24.0"
CLAUDE_CODE_VERSION = "2.1.293"
MODEL = "anthropic/claude-sonnet-5-5"
EFFORT = "high"
MAX_OUTPUT_TOKENS = "128000"
CLAUDE_ARM_URL = f"https://downloads.claude.ai/claude-code-releases/{CLAUDE_CODE_VERSION}/linux-arm64-musl/claude"
CLAUDE_ARM_SHA256 = "00755ae106b6925c1adb2b17e4c6d9b0c41eb4cc55bcad3581345b0aa3176c85"
ALPINE_IMAGE = "alpine:3.23.4@sha256:5b10f432ef3da1b8d4c7eb6c487f2f5a8f096bc91145e68878dd4a5019afde11"
REFINE_BASE_IMAGE = "python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1"
ALLOW_HOST = "api.anthropic.com"
KEYCHAIN_SERVICE = _tb4.KEYCHAIN_SERVICE

SPLIT_SEED = 20261014
ORDER_SEED = 20261015
PERM_SEED = 20261016
N_PRACTICE = 30
MIN_TEST = 40
ATTEMPTS = 3
PERM_DRAWS = 100_000
GATE_HIGH = 26  # practice passes at or above this stop the study (above 85%)
GATE_LOW = 4    # practice passes at or below this stop the study (below 15%)
INFRA_RERUNS = 2
PROBE_EVERY = 10
WEEKLY_CEILING = 0.9
FIVE_HOUR_CEILING = 0.9

FREEZE_TAG = "swepro-prereg"
PHASES = ("validate", "practice", "refine", "test", "regrade", "probe")
ARMS = ("plain", "refined")
JOB_ARMS = (*ARMS, "oracle", "nop", "refine", "probe")


def job_name(phase: str, task: str, arm: str, attempt: int) -> str:
    """`{phase}__{task}__{arm}__a{attempt}`."""
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase!r}")
    if arm not in JOB_ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError(f"attempt must be an int >= 1, not {attempt!r}")
    if not task or "/" in task or task.startswith("_") or task.endswith("_"):
        raise ValueError(f"bad task {task!r}")
    return f"{phase}__{task}__{arm}__a{attempt}"


def parse_job_name(name: str) -> tuple:
    """Task ids contain `__`, so split the phase off the left and the arm and attempt off the right."""
    phase, rest = name.split("__", 1)
    task, arm, attempt = rest.rsplit("__", 2)
    return phase, task, arm, int(attempt.removeprefix("a"))
