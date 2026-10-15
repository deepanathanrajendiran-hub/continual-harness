"""Fixed settings for the SWE-bench Pro refine study. Change nothing here after the freeze.

Spec: docs/superpowers/specs/2026-10-14-swepro-refine-design.md
"""
import os
from pathlib import Path

from bench.tb4 import config as _tb4

STUDY = os.environ.get("SWEPRO_STUDY", "ansible")  # which repository's study; ansible keeps the bare names
_SUFFIX = "" if STUDY == "ansible" else f"-{STUDY}"

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS = Path.home() / f"swepro-runs{_SUFFIX}"  # Colima shares only $HOME with containers
DOCS = REPO_ROOT / "docs" / "evaluations" / f"swepro-refine{_SUFFIX}"
SPEC = "docs/superpowers/specs/2026-10-14-swepro-refine-design.md"

SCALE_URL = "https://github.com/scaleapi/SWE-bench_Pro-os.git"
SCALE_COMMIT = "66f92766bba642462d4bbe5479e83f91f9211862"
REPLAY_SHA256 = "5c8b344de37164e9723f1724c2573013957fb644c3913a64c12c1718c737d876"  # v2/tooling/patch_replay.py
SMOKE_TASK = ("instance_ansible__ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8"
              "-v30a923fb5c164d6cd18280c02422f75e611e8fb2")
FLAKY_TASK = ("instance_ansible__ansible-40ade1f84b8bb10a63576b0ac320c13f57c87d34"
              "-v6382ea168a93d80a64aab1fbd8c4f02dc5ada5bf")  # timing-sensitive per Scale's GATE.md

# Pilot tasks: random.Random(PILOT_SEED).sample(sorted repo tasks, 8). Plain Claude Code ran them once to
# pick a repository after ansible stopped at the ceiling, so they are excluded from that repository's study.
# The Haiku pilot drew from the committed ansible practice list instead; practice tasks are never scored.
PILOT_SEED = 20261017
OPENLIBRARY_PILOT = tuple(f"instance_internetarchive__openlibrary-{t}" for t in (
    "09865f5fb549694d969f0a8e49b9d204ef1853ca-ve8c8d62a2b60610a3c4631f5f23ed866bada9818",
    "308a35d6999427c02b1dbf5211c033ad3b352556-ve8c8d62a2b60610a3c4631f5f23ed866bada9818",
    "431442c92887a3aece3f8aa771dd029738a80eb1-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c",
    "630221ab686c64e75a2ce253c893c033e4814b2e-v93c53c13d5f9b383ebb411ee7750b49dcd1a34c6",
    "9cd47f4dc21e273320d9e30d889c864f8cb20ccf-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4",
    "bdba0af0f6cbaca8b5fc3be2a3080f38156d9c92-ve8c8d62a2b60610a3c4631f5f23ed866bada9818",
    "c8996ecc40803b9155935fd7ff3b8e7be6c1437c-ve8fc82d8aae8463b752a211156c5b7b59f349237",
    "e8084193a895d8ee81200f49093389a3887479ce-ve8c8d62a2b60610a3c4631f5f23ed866bada9818"))
FLIPT_PILOT = tuple(f"instance_flipt-io__flipt-{t}" for t in (
    "0fd09def402258834b9d6c0eaa6d3b4ab93b4446", "3d5a345f94c2adc8a0eaa102c189c08ad4c0f8e8",
    "5af0757e96dec4962a076376d1bedc79de0d4249", "9d25c18b79bc7829a6fb08ec9e8793d5d17e2868",
    "c6a7b1fd933e763b1675281b30077e161fa115a1", "dae029cba7cdb98dfb1a6b416c00d324241e6063",
    "e594593dae52badf80ffd27878d2275c7f0b20e9", "ea9a2663b176da329b3f574da2ce2a664fc5b4a1"))
ANSIBLE_HAIKU_PILOT = tuple(f"instance_ansible__ansible-{t}" for t in (
    "106909db8b730480615f4a33de0eb5b710944e78-v0f01c69f1e2528b935359cfe578530722bca2c59",
    "1c06c46cc14324df35ac4f39a45fb3ccd602195d-v0f01c69f1e2528b935359cfe578530722bca2c59",
    "29aea9ff3466e4cd2ed00524b9e56738d568ce8b-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5",
    "415e08c2970757472314e515cb63a51ad825c45e-v7eee2454f617569fd6889f2211f75bc02a35f9f8",
    "83fb24b923064d3576d473747ebbe62e4535c9e3-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5",
    "942424e10b2095a173dbd78e7128f52f7995849b-v30a923fb5c164d6cd18280c02422f75e611e8fb2",
    "984216f52e76b904e5b0fa0fb956ab4f1e0a7751-v1055803c3a812189a1133297f7f5468579283f86",
    "c1f2df47538b884a43320f53e787197793b105e8-v906c969b551b346ef54a2c0b41e04f632b7b73c2"))
SONNET = ("anthropic/claude-sonnet-5-5", "Sonnet 5.5")
HAIKU = ("anthropic/claude-haiku-5-5", "Haiku 5.5")
DEEPSEEK = ("deepseek-v4-flash", "DeepSeek V4 Flash")
PROVIDERS = {  # where Claude Code sends model calls; anthropic uses the subscription token
    "anthropic": {"host": "api.anthropic.com", "base_url": None, "keychain": None, "litellm_key_env": None},
    "deepseek": {"host": "api.deepseek.com", "base_url": "https://api.deepseek.com/anthropic",
                 "keychain": "swepro-deepseek-key", "litellm_key_env": "DEEPSEEK_API_KEY"},
}
STUDIES = {
    "ansible": {"repo": "ansible", "prefix": "instance_ansible__ansible-", "github": "ansible/ansible",
                "excluded": (SMOKE_TASK, FLAKY_TASK), "pilot": (), "model": SONNET},
    "openlibrary": {"repo": "openlibrary", "prefix": "instance_internetarchive__openlibrary-",
                    "github": "internetarchive/openlibrary", "excluded": OPENLIBRARY_PILOT,
                    "pilot": OPENLIBRARY_PILOT, "model": SONNET},
    "flipt": {"repo": "flipt", "prefix": "instance_flipt-io__flipt-", "github": "flipt-io/flipt",
              "excluded": FLIPT_PILOT, "pilot": FLIPT_PILOT, "model": SONNET},
    "ansible-haiku": {"repo": "ansible", "prefix": "instance_ansible__ansible-", "github": "ansible/ansible",
                      "excluded": (SMOKE_TASK, FLAKY_TASK), "pilot": ANSIBLE_HAIKU_PILOT, "model": HAIKU},
    "openlibrary-haiku": {"repo": "openlibrary", "prefix": "instance_internetarchive__openlibrary-",
                          "github": "internetarchive/openlibrary", "excluded": OPENLIBRARY_PILOT,
                          "pilot": OPENLIBRARY_PILOT, "model": HAIKU},
    "openlibrary-deepseek": {"repo": "openlibrary", "prefix": "instance_internetarchive__openlibrary-",
                             "github": "internetarchive/openlibrary", "excluded": OPENLIBRARY_PILOT,
                             "pilot": OPENLIBRARY_PILOT, "model": DEEPSEEK, "provider": "deepseek"},
    "openlibrary-mini": {"repo": "openlibrary", "prefix": "instance_internetarchive__openlibrary-",
                         "github": "internetarchive/openlibrary", "excluded": OPENLIBRARY_PILOT,
                         "pilot": OPENLIBRARY_PILOT, "model": DEEPSEEK, "provider": "deepseek",
                         "harness": "mini", "agent_model": "deepseek/deepseek-v4-flash"},
}
if STUDY not in STUDIES:
    raise ValueError(f"unknown SWEPRO_STUDY {STUDY!r}: choose one of {sorted(STUDIES)}")
REPO_LABEL = STUDIES[STUDY]["repo"]
REPO_PREFIX = STUDIES[STUDY]["prefix"]
REPO_GITHUB = STUDIES[STUDY]["github"]
EXCLUDED = STUDIES[STUDY]["excluded"]
PILOT = STUDIES[STUDY]["pilot"]
MODEL, MODEL_NAME = STUDIES[STUDY]["model"]
_PROVIDER = PROVIDERS[STUDIES[STUDY].get("provider", "anthropic")]
ALLOW_HOST = _PROVIDER["host"]
BASE_URL = _PROVIDER["base_url"]
PROVIDER_KEYCHAIN = _PROVIDER["keychain"]
LITELLM_KEY_ENV = _PROVIDER["litellm_key_env"]
HARNESS = STUDIES[STUDY].get("harness", "claude")  # the agent under test; refine is always Claude Code
HARNESS_NAME = {"claude": "Claude Code", "mini": "mini-swe-agent"}[HARNESS]
AGENT_MODEL = STUDIES[STUDY].get("agent_model", MODEL)  # what the agent under test is called with
MINI_VERSION = "2.4.6"
MINI_STEP_LIMIT = 100
MINI_UV_VERSION = "0.12.20"
MINI_EXCLUDE_NEWER = "2026-10-01T00:00:00Z"
MINI_PYTHON_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/20260929/"
                   "cpython-3.12.14%2B20260929-x86_64-unknown-linux-gnu-install_only.tar.gz")
MINI_PYTHON_SHA256 = "06c90b93f419b63371c18f20fed0558a1a901f6518c3c24f755077e048447e7f"

HARBOR_VERSION = "0.24.0"
CLAUDE_CODE_VERSION = "2.1.293"
EFFORT = "high"
MAX_OUTPUT_TOKENS = "128000"
CLAUDE_ARM_URL = f"https://downloads.claude.ai/claude-code-releases/{CLAUDE_CODE_VERSION}/linux-arm64-musl/claude"
CLAUDE_ARM_SHA256 = "00755ae106b6925c1adb2b17e4c6d9b0c41eb4cc55bcad3581345b0aa3176c85"
ALPINE_IMAGE = "alpine:3.23.4@sha256:5b10f432ef3da1b8d4c7eb6c487f2f5a8f096bc91145e68878dd4a5019afde11"
REFINE_BASE_IMAGE = "python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1"
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

FREEZE_TAG = f"swepro-prereg{_SUFFIX}"
PHASES = ("validate", "practice", "refine", "test", "regrade", "probe", "pilot")
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
