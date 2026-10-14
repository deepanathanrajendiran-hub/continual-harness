# SWE-bench Pro Refine Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run the pre-registered SWE-bench Pro study of refine: practice on 30 ansible tasks with refine learning after each, freeze the notes, then compare plain Claude Code with Claude Code plus the frozen notes on the unseen ansible tasks, 3 attempts each, scored by pristine re-grades.

**Architecture:** A new package `bench/swepro` drives Harbor 0.24.0 on Colima. It reuses three things from earlier packages by import, without changing them:
- `bench/tb4`: the Keychain token, usage pacing, runner lock and stream-json reader;
- `bench/evo`: Harbor exception lists.

Two Harbor agent classes run Claude Code's arm64-musl build inside the amd64 task images:
- one installs a frozen notes bundle;
- one runs a refine session in its own offline container.

Every module takes a `run` callable, so its tests use fakes and need no Docker. Only the runbook (Task 15) touches Docker, Harbor jobs or subscription usage.

**Tech Stack:**
- Python 3.12 standard library;
- pytest, run with `sh bench/swepro/test.sh` (it wraps `uv run --with pytest --with harbor==0.24.0` with HOME isolated; bare `pytest` is not installed);
- Harbor 0.24.0;
- Colima 0.10.3 (`--vm-type vz --vz-rosetta`);
- Claude Code 2.1.293 (linux-arm64-musl build);
- SWE-bench Pro v2.

**Spec:** `docs/superpowers/specs/2026-10-14-swepro-refine-design.md`

**How the tasks were checked:** every task was written test-first in a scratch clone of this branch at `d889d8e`. The combined suite there ends at `1423 passed` under `bench/swepro/test.sh`, or `1412 passed, 1 skipped` under `bench/tb4/test.sh`, which cannot import Harbor and so skips the agent tests. Every code block that creates a file is byte-identical to the file in that clone. Every count in an `Expected:` line comes from replaying the tasks in order on a clean checkout.

Two pieces also ran for real on Colima, on the excluded smoke task:
- **`ArmClaudeCode` with a bundle.** Reward 1. `notes.json` carried the bundle hash, and memory reached `$CLAUDE_CONFIG_DIR/projects/-app/memory`. Both notes appeared in the session, and `model.patch` held only the repo change.
- **A full `refine.run_session`.** The session ran the snapshot CLI (`doctor`, `refine-count`, `refine-history`), applied nothing for an easy passed task, and the state round-tripped.

## Global Constraints

- **Worktree.** Every command runs from the worktree root, `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/swepro-refine`, on branch `eval/swepro-refine`. Set `WT="/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/swepro-refine"` and always quote it: the path has a trailing space in `fun `.
- **Dataset.** `https://github.com/scaleapi/SWE-bench_Pro-os.git` at `66f92766bba642462d4bbe5479e83f91f9211862`, directory `v2/tasks/`. Never Harbor's hub copy `scale-ai/swe-bench-pro`, which is the older v1. `v2/tooling/patch_replay.py` must have sha256 `5c8b344de37164e9723f1724c2573013957fb644c3913a64c12c1718c737d876`.
- **Pool.** The ansible tasks (`instance_ansible__ansible-*`), excluding:
  - the smoke task `instance_ansible__ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8-v30a923fb5c164d6cd18280c02422f75e611e8fb2`;
  - the timing-sensitive `instance_ansible__ansible-40ade1f84b8bb10a63576b0ac320c13f57c87d34-v6382ea168a93d80a64aab1fbd8c4f02dc5ada5bf`.
- **Versions and model.** Harbor `0.24.0`; Claude Code `2.1.293` from `https://downloads.claude.ai/claude-code-releases/2.1.293/linux-arm64-musl/claude` (sha256 `00755ae106b6925c1adb2b17e4c6d9b0c41eb4cc55bcad3581345b0aa3176c85`); model `anthropic/claude-sonnet-5-5`, effort `high`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000`, `--ak disable_web_search=true`.
- **Network.** The agent phase stays offline (`no-network` in every `task.toml`), opened only with `--allow-agent-host api.anthropic.com`.
- **Images.**
  - Musl loader from `alpine:3.23.4@sha256:5b10f432ef3da1b8d4c7eb6c487f2f5a8f096bc91145e68878dd4a5019afde11`.
  - Refine container base `python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1`.
  - Pull task images with `--platform linux/amd64`.
- **Seeds and sizes.**
  - Seeds: split `20261014`, test order `20261015`, permutation `20261016`.
  - Practice 30; at least 40 test tasks; 3 attempts per arm; 100,000 permutation draws.
  - Gate: stop at 26 or more passes, or 4 or fewer, out of 30.
  - At most 2 infrastructure reruns per run; a network probe every 10 tasks.
- **Run data** lives in `~/swepro-runs` (Colima shares only `$HOME`), never in the repo. The repo holds the split, the pre-registration, `learned.md` and the report under `docs/evaluations/swepro-refine/`.
- **Token.** The OAuth token comes from Keychain service `tb4-horizon-claude-token` and is never printed. Harbor receives it as `--ae CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}`, expanded from the job's environment.
- **Operator rules (contamination).**
  - Never open or print anything under a task's `tests/` or `solution/`, any `verifier/` output beyond `reward.txt` and the feedback counts, or the graded lists in `config.json`. Code reads these and prints counts only.
  - Never read test-phase transcripts or patches.
  - Never edit the bundle, the refine snapshot or the task copies to make a check pass.
  - Never move or recreate the `swepro-prereg` tag.
  - Never use the horizon or refine skills, or `/loop`, to run or monitor the study.
- **TB4 and EvoCode stay unchanged.** No file under `bench/tb4` or `bench/evo` changes.
- **Edits** to `.py`, `.json` and `.toml` files use the ast-editor MCP tools. The code blocks below create whole new files.
- **Commits** carry no attribution lines. No push and no tag push without the user's decision.

## Review Focus

These five inputs are implied by the spec but no spec-level test exercises them. Each now has a test in the task that owns the code:

1. **A Mac sleep, Ctrl-C or Colima restart mid-run** leaves a Harbor job directory with no record. On resume, that directory counts as the try. It is reused if it finished validly; otherwise the next rerun name is used. Without this, `run_job` would refuse to reuse the directory and the study could not resume.
   - Task 6: `test_an_existing_job_directory_is_read_not_run`.
   - Task 13: `test_a_job_killed_before_its_result_is_rerun_under_the_next_name` and `test_a_half_finished_task_reruns_only_its_missing_runs`.
2. **A crash after refine absorbed a lesson but before the practice record was written.** On resume, the task must keep the bundle it actually ran with, not a re-export that already holds its own lesson.
   - Task 11: `test_a_resumed_task_keeps_the_bundle_it_ran_with`.
3. **A test task whose image already has `/app/.claude`, or keeps its repo outside `/app`.** The refined arm's install refuses it while the plain arm runs, which would score only the refined arm 0. Validation now marks such tasks invalid before the split.
   - Task 8: `test_a_task_whose_image_has_its_own_claude_dir_or_no_app_repo_is_invalid`.
4. **Harbor's preflight rejects `--ak` options the agent's options model does not declare.** This was found on the real run. Both agents declare their options.
   - Task 5: `test_harbor_preflight_accepts_the_arm_options`, `test_harbor_preflight_accepts_the_refine_options` and `test_harbor_preflight_still_rejects_unknown_options`.
5. **`/refine` at the top of the prompt loads the skill without a Skill tool call.** This was found on the real run. `skill_used` also counts calls to the snapshot CLI.
   - Task 10: `test_running_the_snapshot_cli_counts_as_using_the_skill`.

## Rulings on the spec (decided while writing; each costs little if wrong)

- **CLAUDE.md placement.** The bundle installs CLAUDE.md as `/app/.claude/CLAUDE.md`, not `/app/CLAUDE.md`. All notes then sit in one directory hidden by `.git/info/exclude`, and the repo's own files stay untouched. Claude Code loads `./.claude/CLAUDE.md` the same way (verified on the real run).
- **Memory location.** Memory goes through Harbor's `memory_dir` option into `$CLAUDE_CONFIG_DIR/projects/-app/memory`. Harbor sets `CLAUDE_CONFIG_DIR=/logs/agent/sessions`, so `~/.claude/projects/-app/memory` would not be read.
- **Invalid runs.** A test run still invalid after 2 reruns scores 0 and is counted in the report's "Invalid after reruns" row. The spec does not say.
- **Invalid refine sessions.** An invalid refine session (after reruns) leaves the notes unchanged, and practice continues. The spec does not say.
- **Validation additions.**
  - Validation adds the repo-layout check from Review Focus 3.
  - It runs 2 tasks at a time, about 6 hours instead of 11.
- **Usage projection.** The gate's projection is the seven-day utilization used during practice, divided by 30, times the agent's share of practice cost, times 300 test runs.
- **Edits by layer.** The gate counts a refine session that changed files of a layer as one edit of that layer, read from the bundle diff. It also counts sessions that changed nothing; together these are the spec's "edits by layer" and "nothing to learn" numbers. Bundle size is the file list in `prereg.md`.

## File Structure

| File | Responsibility | Task |
| --- | --- | --- |
| `bench/swepro/__init__.py` | package marker | 1 |
| `bench/swepro/test.sh` | pytest with HOME isolated and Harbor 0.24.0 importable | 1 |
| `bench/swepro/config.py` | every pinned value; job names | 1 |
| `bench/swepro/dataset.py` | fetch v2 at the pinned commit; list the pool; install `patch_replay.py` | 2 |
| `bench/swepro/tools.py` | arm64 Claude Code build, musl loader, tools manifest | 3 |
| `bench/swepro/bundle.py` | refine state to notes bundle; manifest; refine snapshot | 4 |
| `bench/swepro/install.py` | container steps as data: Claude Code, bundle, refine layout, patch capture | 5 |
| `bench/swepro/agent.py` | Harbor agents `ArmClaudeCode` and `RefineClaudeCode` | 5 |
| `bench/swepro/jobs.py` | Harbor command, trial reading, classification, reruns, image pull/remove | 6 |
| `bench/swepro/feedback.py` | counts-only result line | 7 |
| `bench/swepro/validate.py` | layout, oracle and nop validation | 8 |
| `bench/swepro/split.py` | seeded split and test order | 8 |
| `bench/swepro/probe.py` | agent-phase network probe | 9 |
| `bench/swepro/refine.py` | refine task, inputs, sessions, state absorption | 10 |
| `bench/swepro/practice.py` | practice loop and go/no-go gate | 11 |
| `tests/swepro_fakes.py` | fake Harbor/docker `run` for practice and test-phase tests | 11 |
| `bench/swepro/prereg.py` | bundle export, pre-registration, freeze checks | 12 |
| `bench/swepro/regrade.py` | pristine re-grade with Scale's PatchReplayAgent | 13 |
| `bench/swepro/run.py` | test phase in concurrent pairs | 13 |
| `bench/swepro/score.py` | rows | 14 |
| `bench/swepro/analysis.py` | permutation test, secondary outcomes, validity, report | 14 |
| `tests/test_swepro_*.py` | one test file per module | 1-14 |
| `docs/evaluations/swepro-refine/{split.json,prereg.json,prereg.md,learned.md,report.md,deviations.md}` | written by the runbook | 15 |

## Who does what

- **Tasks 1-14** are code, written test-first. They need no Docker, no Harbor job and no subscription usage.
- **Task 15** is the runbook. An agent can run it end to end. The user is needed only:
  - to refresh the Claude token in their own terminal when a step reports an authentication failure;
  - to answer at each **STOP**: the practice gate, the frozen notes, and publishing;
  - to decide whether to push the branch and tag.

## Run directory layout (`config.RUNS` = `~/swepro-runs`)

- `scale/` (the v2 clone; read-only by convention), `tools/` (Claude Code, loader, `patch_replay.py`, `manifest.json`)
- `validation/<task>.json`, `valid.json`
- `refine/skill/` (snapshot), `refine/task/`, `refine/state/`, `refine/inputs/NNN/`, `refine/out/<job>/`, `refine/history/NNN/`, `refine/records/NNN.json`
- `practice/bundles/NNN/`, `practice/records/NNN.json`, `practice/usage_start.json`, `practice/usage_end.json`, `practice/gate.json`
- `bundle/` (the frozen notes)
- `jobs/<job>/`: Harbor job directories; reruns are `<job>-rerun1`, `<job>-rerun2`
- `records/test__*.json`, `regrade/regrade__*.json`, `probes/NNN.json`, `probe-task/`
- `logs/<job>.log`, `rows.jsonl`, `summary.json`, `deviations.md`, `runner.lock`

**Job name:** `{phase}__{task}__{arm}__a{attempt}`. Phase is one of `validate`, `practice`, `refine`, `test`, `regrade`, `probe`. Arm is one of `plain`, `refined`, `oracle`, `nop`, `refine`, `probe`. Task ids contain `__`, so parse a name by splitting the phase off the left and the arm and attempt off the right (`config.parse_job_name`).

---


### Task 1: Config, package and test runner

Pins every value the spec fixes, and adds a test runner that makes Harbor 0.24.0 importable (the agent tests need it) while keeping HOME isolated like `bench/tb4/test.sh`.

**Files:**
- Create: `bench/swepro/test.sh`
- Create: `bench/swepro/__init__.py`
- Create: `bench/swepro/config.py`
- Test: `tests/test_swepro_config.py`

**Interfaces:**
- Consumes: `bench.tb4.config.KEYCHAIN_SERVICE`
- Produces: `config.RUNS`, `config.DOCS`, `config.SPEC`, every pin, `config.EXCLUDED`, `config.ARMS`, `config.job_name(phase, task, arm, attempt) -> str`, `config.parse_job_name(name) -> (phase, task, arm, attempt)`; `sh bench/swepro/test.sh <pytest args>`

- [ ] **Step 1: Add the test runner**

Create `bench/swepro/test.sh`:

```sh
#!/bin/sh
# Run pytest with HOME isolated (no test may touch the live ~/.claude) and Harbor 0.24.0 importable.
set -eu
cd "$(dirname "$0")/../.."
iso="$(mktemp -d)"
cache="$(uv cache dir)"
pythons="$(uv python dir)"
HOME="$iso" CODEX_HOME="$iso/.codex" UV_CACHE_DIR="$cache" UV_PYTHON_INSTALL_DIR="$pythons" PYTHONDONTWRITEBYTECODE=1 \
  exec uv run --no-project --python 3.12 --with pytest --with harbor==0.24.0 python -m pytest -p no:cacheprovider "$@"
```

Then run: `chmod +x bench/swepro/test.sh`

- [ ] **Step 2: Write the failing test `test_swepro_config.py`**

Create `tests/test_swepro_config.py`:

```python
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
```

- [ ] **Step 3: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_config.py`
Expected: FAIL with `ImportError: cannot import name 'config' from 'bench.swepro'` (the runner's directory exists, the package does not yet)

- [ ] **Step 4: Write `__init__.py`**

Create `bench/swepro/__init__.py` as an empty file:

```bash
: > bench/swepro/__init__.py
```

- [ ] **Step 5: Write `config.py`**

Create `bench/swepro/config.py`:

```python
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
```

- [ ] **Step 6: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_config.py`
Expected: `11 passed`

- [ ] **Step 7: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1261 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 8: Commit**

```bash
git add bench/swepro/test.sh bench/swepro/__init__.py bench/swepro/config.py tests/test_swepro_config.py
git commit -m "feat(swepro): pinned config, job names and a Harbor-aware test runner"
```

---

### Task 2: Dataset

Sparse-clones Scale's v2 tree at the pinned commit, lists the ansible tasks from `task.toml` only, applies the two exclusions, and installs Scale's `patch_replay.py` after checking its sha256.

**Files:**
- Create: `bench/swepro/dataset.py`
- Test: `tests/test_swepro_dataset.py`

**Interfaces:**
- Consumes: Task 1 `config`
- Produces: `dataset.fetch(dest, *, run) -> Path` (v2/tasks), `dataset.ansible_tasks(tasks_dir) -> list`, `dataset.study_pool(tasks_dir) -> list`, `dataset.docker_image(task_dir) -> str`, `dataset.install_replay(scale_repo, tools_dir) -> Path`, `dataset.DatasetError`

- [ ] **Step 1: Write the failing test `test_swepro_dataset.py`**

Create `tests/test_swepro_dataset.py`:

```python
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


def test_ansible_tasks_are_sorted_and_need_a_task_toml(tree):
    assert dataset.ansible_tasks(tree) == sorted([A1, A2, *config.EXCLUDED])


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
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_dataset.py`
Expected: FAIL with `ImportError: cannot import name 'dataset'`

- [ ] **Step 3: Write `dataset.py`**

Create `bench/swepro/dataset.py`:

```python
"""Fetch SWE-bench Pro v2 at the pinned commit and list the study's ansible tasks.

Reads only task.toml. Never opens a task's tests/, solution/ or instruction.md.
"""
import argparse
import hashlib
import shutil
import subprocess
import tomllib
from pathlib import Path

from bench.swepro import config


class DatasetError(RuntimeError):
    pass


def _git(repo: Path, *args, run=subprocess.run) -> str:
    proc = run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise DatasetError(f"git {' '.join(args)} failed: {(proc.stderr or '')[-300:]}")
    return proc.stdout or ""


def fetch(dest: Path = config.RUNS / "scale", *, run=subprocess.run) -> Path:
    """Sparse-clone v2/ at SCALE_COMMIT (or reuse a clone already there) and return v2/tasks."""
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        proc = run(["git", "clone", "--filter=blob:none", "--no-checkout", config.SCALE_URL, str(dest)],
                   capture_output=True, text=True)
        if proc.returncode != 0:
            raise DatasetError(f"clone failed: {(proc.stderr or '')[-300:]}")
        _git(dest, "sparse-checkout", "set", "v2", run=run)
        _git(dest, "checkout", config.SCALE_COMMIT, run=run)
    head = _git(dest, "rev-parse", "HEAD", run=run).strip()
    if head != config.SCALE_COMMIT:
        raise DatasetError(f"{dest} is at commit {head}, not {config.SCALE_COMMIT}")
    return dest / "v2" / "tasks"


def ansible_tasks(tasks_dir: Path) -> list:
    return sorted(p.name for p in tasks_dir.iterdir()
                  if p.name.startswith(config.REPO_PREFIX) and (p / "task.toml").is_file())


def study_pool(tasks_dir: Path) -> list:
    """The ansible tasks minus the smoke and flaky tasks, which must both be present."""
    names = ansible_tasks(tasks_dir)
    missing = [t for t in config.EXCLUDED if t not in names]
    if missing:
        raise DatasetError(f"excluded tasks not in the tree: {missing}")
    return [t for t in names if t not in config.EXCLUDED]


def docker_image(task_dir: Path) -> str:
    data = tomllib.loads((task_dir / "task.toml").read_text())
    image = (data.get("environment") or {}).get("docker_image")
    if not image:
        raise DatasetError(f"{task_dir.name}: task.toml names no docker_image")
    return image


def install_replay(scale_repo: Path, tools_dir: Path) -> Path:
    """Copy Scale's patch_replay.py into tools/ after checking it against the pinned sha256."""
    src = scale_repo / "v2" / "tooling" / "patch_replay.py"
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    if digest != config.REPLAY_SHA256:
        raise DatasetError(f"patch_replay.py sha256 {digest} != pinned {config.REPLAY_SHA256}")
    tools_dir.mkdir(parents=True, exist_ok=True)
    out = tools_dir / "patch_replay.py"
    shutil.copyfile(src, out)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch SWE-bench Pro v2 and list the ansible pool.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    args = parser.parse_args(argv)
    tasks = fetch(args.runs / "scale")
    install_replay(args.runs / "scale", args.runs / "tools")
    pool = study_pool(tasks)
    print(f"{len(ansible_tasks(tasks))} ansible tasks; {len(pool)} in the study pool")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_dataset.py`
Expected: `10 passed`

- [ ] **Step 5: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1271 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 6: Commit**

```bash
git add bench/swepro/dataset.py tests/test_swepro_dataset.py
git commit -m "feat(swepro): fetch SWE-bench Pro v2 and list the ansible pool"
```

---

### Task 3: Tools: arm64 Claude Code and the musl loader

Downloads the linux-arm64-musl Claude Code build (sha256-checked) and copies Alpine's musl loader out of the pinned image, then writes a manifest of every tool.

**Files:**
- Create: `bench/swepro/tools.py`
- Test: `tests/test_swepro_tools.py`

**Interfaces:**
- Consumes: Task 1 `config`
- Produces: `tools.CLAUDE_REL`, `tools.LOADER_REL`, `tools.TOOLS`, `tools.fetch_claude(tools_dir, *, download) -> Path`, `tools.fetch_loader(tools_dir, *, run) -> Path`, `tools.write_manifest(tools_dir) -> dict`, `tools.sha256_file(path) -> str`, `tools.ToolError`

- [ ] **Step 1: Write the failing test `test_swepro_tools.py`**

Create `tests/test_swepro_tools.py`:

```python
import hashlib
import json
import subprocess

import pytest

from bench.swepro import config, tools

BINARY = b"\x7fELF fake claude"


def pin(monkeypatch, data=BINARY):
    monkeypatch.setattr(config, "CLAUDE_ARM_SHA256", hashlib.sha256(data).hexdigest())


def test_fetch_claude_downloads_and_verifies(tmp_path, monkeypatch):
    pin(monkeypatch)
    urls = []

    def download(url, dest):
        urls.append(url)
        dest.write_bytes(BINARY)

    out = tools.fetch_claude(tmp_path, download=download)
    assert urls == [config.CLAUDE_ARM_URL]
    assert out == tmp_path / "claude-arm64-musl" / "claude"
    assert out.read_bytes() == BINARY and out.stat().st_mode & 0o111


def test_fetch_claude_reuses_a_verified_copy(tmp_path, monkeypatch):
    pin(monkeypatch)
    tools.fetch_claude(tmp_path, download=lambda url, dest: dest.write_bytes(BINARY))
    tools.fetch_claude(tmp_path, download=lambda url, dest: pytest.fail("downloaded again"))


def test_fetch_claude_refuses_and_deletes_a_bad_download(tmp_path, monkeypatch):
    pin(monkeypatch)
    with pytest.raises(tools.ToolError, match="sha256"):
        tools.fetch_claude(tmp_path, download=lambda url, dest: dest.write_bytes(b"other"))
    assert not (tmp_path / "claude-arm64-musl" / "claude").exists()


def test_fetch_loader_copies_it_out_of_the_pinned_alpine_image(tmp_path):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        (tmp_path / "musl" / "ld-musl-aarch64.so.1").write_bytes(b"loader")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    out = tools.fetch_loader(tmp_path, run=run)
    assert out.read_bytes() == b"loader"
    cmd = calls[0]
    assert cmd[:3] == ["docker", "run", "--rm"] and "--platform" in cmd and "linux/arm64" in cmd
    assert config.ALPINE_IMAGE in cmd


def test_fetch_loader_refuses_an_empty_result(tmp_path):
    def run(cmd, **kw):
        (tmp_path / "musl").mkdir(exist_ok=True)
        (tmp_path / "musl" / "ld-musl-aarch64.so.1").write_bytes(b"")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with pytest.raises(tools.ToolError):
        tools.fetch_loader(tmp_path, run=run)


def test_manifest_hashes_every_tool(tmp_path):
    for rel, data in ((tools.CLAUDE_REL, b"c"), (tools.LOADER_REL, b"l"), ("patch_replay.py", b"r")):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(data)
    m = tools.write_manifest(tmp_path)
    assert m[tools.LOADER_REL] == hashlib.sha256(b"l").hexdigest()
    assert json.loads((tmp_path / "manifest.json").read_text()) == m
    assert set(m) == {tools.CLAUDE_REL, tools.LOADER_REL, "patch_replay.py"}
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_tools.py`
Expected: FAIL with `ImportError: cannot import name 'tools'`

- [ ] **Step 3: Write `tools.py`**

Create `bench/swepro/tools.py`:

```python
"""The files every container needs: the arm64-musl Claude Code build and Alpine's musl loader.

The SWE-bench Pro images are linux/amd64. Under Rosetta the x64 Claude Code build refuses to start
("CPU lacks AVX support"). The Colima VM is arm64, so the arm64 build runs natively inside the amd64
container once its loader is at /lib/ld-musl-aarch64.so.1.
"""
import argparse
import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

from bench.swepro import config

CLAUDE_REL = "claude-arm64-musl/claude"
LOADER_REL = "musl/ld-musl-aarch64.so.1"
TOOLS = config.RUNS / "tools"


class ToolError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _urlretrieve(url: str, dest: Path) -> None:
    urllib.request.urlretrieve(url, dest)  # noqa: S310 - pinned https URL, checked by sha256 below


def fetch_claude(tools_dir: Path = TOOLS, *, download=_urlretrieve) -> Path:
    out = tools_dir / CLAUDE_REL
    if out.exists() and sha256_file(out) == config.CLAUDE_ARM_SHA256:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    download(config.CLAUDE_ARM_URL, out)
    digest = sha256_file(out)
    if digest != config.CLAUDE_ARM_SHA256:
        out.unlink()
        raise ToolError(f"claude sha256 {digest} != pinned {config.CLAUDE_ARM_SHA256}")
    out.chmod(0o755)
    return out


def fetch_loader(tools_dir: Path = TOOLS, *, run=subprocess.run) -> Path:
    out = tools_dir / LOADER_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = run(["docker", "run", "--rm", "--platform", "linux/arm64", "-v", f"{out.parent}:/o",
                config.ALPINE_IMAGE, "cp", "-L", "/lib/ld-musl-aarch64.so.1", "/o/"],
               capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise ToolError(f"could not copy the musl loader: {(proc.stderr or '')[-300:]}")
    out.chmod(0o755)
    return out


def write_manifest(tools_dir: Path = TOOLS) -> dict:
    manifest = {rel: sha256_file(tools_dir / rel) for rel in (CLAUDE_REL, LOADER_REL, "patch_replay.py")}
    (tools_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch the arm64 Claude Code build and musl loader.")
    parser.add_argument("--tools", type=Path, default=TOOLS)
    args = parser.parse_args(argv)
    fetch_claude(args.tools)
    fetch_loader(args.tools)
    print(json.dumps(write_manifest(args.tools), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_tools.py`
Expected: `6 passed`

- [ ] **Step 5: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1277 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 6: Commit**

```bash
git add bench/swepro/tools.py tests/test_swepro_tools.py
git commit -m "feat(swepro): fetch the arm64 Claude Code build and musl loader"
```

---

### Task 4: Notes bundle and refine snapshot

Defines the refine state layout (`app/`, `memory/`) and the bundle exported from it, with a manifest hash; and snapshots the refine skill with its CLI made self-contained.

**Files:**
- Create: `bench/swepro/bundle.py`
- Test: `tests/test_swepro_bundle.py`

**Interfaces:**
- Consumes: nothing
- Produces: `bundle.export(state, dest) -> {'files': {rel: sha}, 'hash': str}`, `bundle.verify(bundle_dir) -> str`, `bundle.manifest(root) -> dict`, `bundle._write_manifest(root) -> dict`, `bundle.snapshot_refine(skill_src, harness_src, dest) -> dict`, `bundle.BundleError`

- [ ] **Step 1: Write the failing test `test_swepro_bundle.py`**

Create `tests/test_swepro_bundle.py`:

```python
import json
import os

import pytest

from bench.swepro import bundle


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def state(tmp_path):
    s = tmp_path / "state"
    write(s / "app" / "CLAUDE.md", "Run tests with bin/ansible-test units.\n")
    write(s / "app" / ".claude" / "skills" / "ansible-tests" / "SKILL.md", "skill")
    write(s / "app" / ".claude" / "skills" / "refine" / "SKILL.md", "the refine snapshot")
    write(s / "app" / ".claude" / "skills" / "horizon" / "SKILL.md", "never exported")
    write(s / "app" / ".claude" / "agents" / "reviewer.md", "agent")
    write(s / "app" / ".claude" / "harness" / "refine-log.jsonl", "{}")
    write(s / "memory" / "MEMORY.md", "- [Units](units.md) — how to run units\n")
    write(s / "memory" / "units.md", "note")
    return s


def files(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_export_keeps_only_the_four_note_layers(state, tmp_path):
    m = bundle.export(state, tmp_path / "b")
    assert files(tmp_path / "b") == [
        ".claude/CLAUDE.md", ".claude/agents/reviewer.md", ".claude/skills/ansible-tests/SKILL.md",
        "manifest.json", "memory/MEMORY.md", "memory/units.md"]
    assert (tmp_path / "b" / ".claude" / "CLAUDE.md").read_text().startswith("Run tests")
    assert set(m["files"]) == set(files(tmp_path / "b")) - {"manifest.json"}


def test_export_of_an_empty_state_is_an_empty_bundle_with_a_hash(tmp_path):
    m = bundle.export(tmp_path / "nothing", tmp_path / "b")
    assert m["files"] == {} and len(m["hash"]) == 64
    assert files(tmp_path / "b") == ["manifest.json"]


def test_export_replaces_an_old_bundle(state, tmp_path):
    write(tmp_path / "b" / "memory" / "stale.md")
    bundle.export(state, tmp_path / "b")
    assert not (tmp_path / "b" / "memory" / "stale.md").exists()


def test_export_refuses_a_second_claude_md(state, tmp_path):
    write(state / "app" / ".claude" / "CLAUDE.md", "two homes for rho")
    with pytest.raises(bundle.BundleError, match="CLAUDE.md"):
        bundle.export(state, tmp_path / "b")


def test_export_refuses_a_symlink_in_the_state(state, tmp_path):
    os.symlink("/etc/passwd", state / "memory" / "leak.md")
    with pytest.raises(bundle.BundleError, match="symlink"):
        bundle.export(state, tmp_path / "b")


def test_the_hash_changes_with_any_byte_and_verify_catches_edits(state, tmp_path):
    h1 = bundle.export(state, tmp_path / "b")["hash"]
    assert bundle.verify(tmp_path / "b") == h1
    write(tmp_path / "b" / "memory" / "units.md", "edited")
    with pytest.raises(bundle.BundleError, match="manifest"):
        bundle.verify(tmp_path / "b")
    write(state / "memory" / "units.md", "edited")
    assert bundle.export(state, tmp_path / "c")["hash"] != h1


def test_the_hash_ignores_where_the_bundle_lives(state, tmp_path):
    assert bundle.export(state, tmp_path / "b")["hash"] == bundle.export(state, tmp_path / "c")["hash"]


def test_snapshot_refine_resolves_symlinks_and_bundles_the_harness(tmp_path):
    repo = tmp_path / "repo"
    write(repo / "harness" / "cli.py", "cli")
    write(repo / "harness" / "refine_log.py", "log")
    write(repo / "harness" / "paths.py", "paths")
    skill = repo / ".claude" / "skills" / "refine"
    write(skill / "SKILL.md", "skill text")
    write(skill / "references" / "commands.md", "refs")
    (skill / "scripts").mkdir()
    os.symlink("../../../../harness/cli.py", skill / "scripts" / "harness.py")
    m = bundle.snapshot_refine(skill, repo / "harness", tmp_path / "snap")
    snap = tmp_path / "snap"
    assert files(snap) == ["SKILL.md", "manifest.json", "references/commands.md", "scripts/harness.py",
                           "scripts/paths.py", "scripts/refine_log.py"]
    assert (snap / "scripts" / "harness.py").read_text() == "cli"
    assert not any(p.is_symlink() for p in snap.rglob("*"))
    assert json.loads((snap / "manifest.json").read_text()) == m
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_bundle.py`
Expected: FAIL with `ImportError: cannot import name 'bundle'`

- [ ] **Step 3: Write `bundle.py`**

Create `bench/swepro/bundle.py`:

```python
"""The notes bundle refine builds, and the frozen refine snapshot that builds it.

A refine state is a directory with two parts:
- `app/`: the project as refine sees it at /app (CLAUDE.md, .claude/skills, .claude/agents, .claude/harness);
- `memory/`: the project memory directory (~/.claude/projects/-app/memory in the refine container).

A bundle holds only the four note layers, laid out for installing into a task container:
- `.claude/CLAUDE.md` (rho; refine writes /app/CLAUDE.md, the bundle installs it under .claude/ so it
  stays out of the repo's own files), `.claude/skills/*`, `.claude/agents/*`, and `memory/*`;
- `manifest.json`: sha256 of every file and one overall `hash`.
"""
import hashlib
import json
import shutil
from pathlib import Path

NOT_EXPORTED_SKILLS = ("refine", "horizon")
MANIFEST = "manifest.json"


class BundleError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refuse_symlinks(root: Path) -> None:
    if root.exists():
        for p in root.rglob("*"):
            if p.is_symlink():
                raise BundleError(f"symlink in refine state: {p}")


def manifest(root: Path) -> dict:
    """sha256 of every file under root except manifest.json, and one hash over the sorted list."""
    found = {p.relative_to(root).as_posix(): _sha(p) for p in sorted(root.rglob("*"))
             if p.is_file() and p.relative_to(root).as_posix() != MANIFEST}
    joined = "".join(f"{rel}\0{digest}\n" for rel, digest in sorted(found.items()))
    return {"files": found, "hash": hashlib.sha256(joined.encode()).hexdigest()}


def _write_manifest(root: Path) -> dict:
    m = manifest(root)
    (root / MANIFEST).write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    return m


def _copy_tree(src: Path, dst: Path, skip=()) -> None:
    if not src.is_dir():
        return
    for child in sorted(src.iterdir()):
        if child.name in skip:
            continue
        target = dst / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(child, target)


def export(state: Path, dest: Path) -> dict:
    """Write the bundle for `state` to `dest` (replacing it) and return its manifest."""
    app = state / "app"
    _refuse_symlinks(app / ".claude")
    _refuse_symlinks(state / "memory")
    if (app / "CLAUDE.md").is_symlink():
        raise BundleError(f"symlink in refine state: {app / 'CLAUDE.md'}")
    if (app / ".claude" / "CLAUDE.md").exists():
        raise BundleError("refine state has both CLAUDE.md and .claude/CLAUDE.md")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    if (app / "CLAUDE.md").is_file():
        (dest / ".claude").mkdir()
        shutil.copyfile(app / "CLAUDE.md", dest / ".claude" / "CLAUDE.md")
    _copy_tree(app / ".claude" / "skills", dest / ".claude" / "skills", skip=NOT_EXPORTED_SKILLS)
    _copy_tree(app / ".claude" / "agents", dest / ".claude" / "agents")
    _copy_tree(state / "memory", dest / "memory")
    return _write_manifest(dest)


def verify(bundle_dir: Path) -> str:
    """Return the bundle's hash if every file still matches manifest.json."""
    stored = json.loads((bundle_dir / MANIFEST).read_text())
    if manifest(bundle_dir) != stored:
        raise BundleError(f"{bundle_dir} no longer matches its manifest")
    return stored["hash"]


def snapshot_refine(skill_src: Path, harness_src: Path, dest: Path) -> dict:
    """Copy the refine skill with its CLI made self-contained: scripts/harness.py is harness/cli.py and
    every harness/*.py sits beside it (the CLI puts its own directory on sys.path)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copyfile(skill_src / "SKILL.md", dest / "SKILL.md")
    if (skill_src / "references").is_dir():
        shutil.copytree(skill_src / "references", dest / "references", symlinks=False)
    scripts = dest / "scripts"
    scripts.mkdir()
    for module in sorted(harness_src.glob("*.py")):
        shutil.copyfile(module, scripts / ("harness.py" if module.name == "cli.py" else module.name))
    return _write_manifest(dest)
```

- [ ] **Step 4: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_bundle.py`
Expected: `8 passed`

- [ ] **Step 5: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1285 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 6: Commit**

```bash
git add bench/swepro/bundle.py tests/test_swepro_bundle.py
git commit -m "feat(swepro): export the notes bundle and snapshot the refine skill"
```

---

### Task 5: Container steps and the Harbor agents

`install.py` holds what the agents do to a container as plain data; `agent.py` is the thin Harbor adapter. `ArmClaudeCode` installs the arm64 build, optionally a verified bundle (notes under `/app/.claude`, hidden from git; memory through Harbor's `memory_dir`), records `notes.json`, and captures `model.patch`. `RefineClaudeCode` lays out a refine container and copies the state back. Both declare an options model, because Harbor's preflight rejects unknown `--ak` options.

**Files:**
- Create: `bench/swepro/install.py`
- Create: `bench/swepro/agent.py`
- Test: `tests/test_swepro_install.py`
- Test: `tests/test_swepro_agent.py`

**Interfaces:**
- Consumes: Task 3 `tools.LOADER_REL`, `tools.CLAUDE_REL`, `tools.TOOLS`; Task 4 `bundle.verify`
- Produces: `install.NOTES`, `install.REFINE_MEMORY`, `install.REFINE_HISTORY`, `install.CAPTURE`, `install.NOTES_REPORT`, `install.Upload`, `install.Exec`, `install.claude_steps(tools_dir)`, `install.bundle_steps(bundle_dir)`, `install.refine_steps(state, skill, inputs)`, `install.refine_history_command()`; Harbor agents `bench.swepro.agent:ArmClaudeCode` (kwargs `tools_dir`, `bundle_dir`) and `bench.swepro.agent:RefineClaudeCode` (kwargs `tools_dir`, `state_dir`, `skill_dir`, `inputs_dir`, `out_dir`)

- [ ] **Step 1: Write the failing test `test_swepro_install.py`**

Create `tests/test_swepro_install.py`:

```python
import pytest

from bench.swepro import bundle, install, tools


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def make_bundle(tmp_path, *, notes=True, memory=True):
    state = tmp_path / "state"
    if notes:
        write(state / "app" / "CLAUDE.md", "rule")
    if memory:
        write(state / "memory" / "MEMORY.md", "- [a](a.md) — a")
    m = bundle.export(state, tmp_path / "bundle")
    return tmp_path / "bundle", m["hash"]


def test_claude_steps_put_the_loader_and_binary_in_place(tmp_path):
    steps = install.claude_steps(tmp_path)
    uploads = [s for s in steps if isinstance(s, install.Upload)]
    assert [(u.src, u.dst) for u in uploads] == [
        (tmp_path / tools.LOADER_REL, "/lib/ld-musl-aarch64.so.1"),
        (tmp_path / tools.CLAUDE_REL, "/usr/local/bin/claude")]
    assert any("libc.musl-aarch64.so.1" in s.command for s in steps if isinstance(s, install.Exec))


def test_bundle_steps_refuse_a_repo_that_already_has_a_claude_dir_and_hide_the_notes_from_git(tmp_path):
    b, h = make_bundle(tmp_path)
    steps = install.bundle_steps(b)
    first = steps[0]
    assert isinstance(first, install.Exec) and first.check
    assert "test ! -e /app/.claude" in first.command and "test -d /app/.git" in first.command
    uploads = [(s.src, s.dst) for s in steps if isinstance(s, install.Upload)]
    assert uploads == [(b / ".claude", "/app/.claude"), (b / "memory", f"{install.NOTES}/memory")]
    text = "\n".join(s.command for s in steps if isinstance(s, install.Exec))
    assert ".git/info/exclude" in text and ".claude/" in text
    assert f"echo {h} > {install.NOTES}/HASH" in text


def test_bundle_steps_for_an_empty_bundle_upload_nothing_but_still_record_the_hash(tmp_path):
    b, h = make_bundle(tmp_path, notes=False, memory=False)
    steps = install.bundle_steps(b)
    assert not [s for s in steps if isinstance(s, install.Upload)]
    assert any(h in s.command for s in steps if isinstance(s, install.Exec))


def test_bundle_steps_refuse_an_edited_bundle(tmp_path):
    b, _ = make_bundle(tmp_path)
    write(b / "memory" / "MEMORY.md", "edited after export")
    with pytest.raises(bundle.BundleError):
        install.bundle_steps(b)


def test_the_notes_report_records_hash_and_whether_notes_exist():
    cmd = install.NOTES_REPORT
    assert "/logs/agent/notes.json" in cmd and f"{install.NOTES}/HASH" in cmd and "/app/.claude" in cmd


def test_refine_steps_lay_out_state_skill_and_inputs(tmp_path):
    state, skill, inputs = tmp_path / "state", tmp_path / "skill", tmp_path / "inputs"
    write(state / "app" / "CLAUDE.md")
    write(state / "memory" / "MEMORY.md")
    write(skill / "SKILL.md")
    write(inputs / "result.txt", "passed")
    steps = install.refine_steps(state, skill, inputs)
    uploads = [(s.src, s.dst) for s in steps if isinstance(s, install.Upload)]
    assert uploads == [(state / "app", "/app"), (state / "memory", install.REFINE_MEMORY),
                       (skill, "/app/.claude/skills/refine"), (inputs, "/inputs")]
    assert install.REFINE_MEMORY == "/root/.claude/projects/-app/memory"


def test_refine_steps_for_a_fresh_state_upload_only_skill_and_inputs(tmp_path):
    skill, inputs = tmp_path / "skill", tmp_path / "inputs"
    write(skill / "SKILL.md")
    write(inputs / "result.txt")
    steps = install.refine_steps(tmp_path / "none", skill, inputs)
    assert [s.dst for s in steps if isinstance(s, install.Upload)] == ["/app/.claude/skills/refine", "/inputs"]


def test_capture_writes_the_staged_diff_to_model_patch():
    assert "git diff --cached > /logs/agent/model.patch" in install.CAPTURE
    assert install.CAPTURE.rstrip().endswith("true")
```

- [ ] **Step 2: Write the failing test `test_swepro_agent.py`**

Create `tests/test_swepro_agent.py`:

```python
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("harbor")

from bench.swepro import agent, bundle, install  # noqa: E402


class FakeEnv:
    def __init__(self, fail_on=None, version="2.1.293 (Claude Code)"):
        self.calls = []
        self.fail_on = fail_on
        self.version = version

    async def upload_file(self, source_path, target_path):
        self.calls.append(("upload_file", Path(source_path), target_path))

    async def upload_dir(self, source_dir, target_dir):
        self.calls.append(("upload_dir", Path(source_dir), target_dir))

    async def download_dir(self, source_dir, target_dir):
        self.calls.append(("download_dir", source_dir, Path(target_dir)))

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self.calls.append(("exec", command, user))
        rc = 1 if self.fail_on and self.fail_on in command else 0
        out = self.version if "--version" in command else ""
        return SimpleNamespace(return_code=rc, stdout=out, stderr="")


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def make(tmp_path, cls=agent.ArmClaudeCode, **kw):
    return cls(logs_dir=tmp_path / "logs", model_name="anthropic/claude-sonnet-5-5", version="2.1.293",
               tools_dir=str(tmp_path / "tools"), **kw)


def test_install_without_a_bundle_puts_claude_in_and_reports_no_notes(tmp_path):
    env = FakeEnv()
    asyncio.run(make(tmp_path).install(env))
    uploads = [c[2] for c in env.calls if c[0] == "upload_file"]
    assert uploads == ["/lib/ld-musl-aarch64.so.1", "/usr/local/bin/claude"]
    assert any(c[0] == "exec" and c[1] == install.NOTES_REPORT for c in env.calls)
    assert not any(c[0] == "upload_dir" for c in env.calls)


def test_install_with_a_bundle_uploads_it_and_points_harbor_memory_at_it(tmp_path):
    write(tmp_path / "state" / "memory" / "MEMORY.md", "- [a](a.md)")
    write(tmp_path / "state" / "app" / "CLAUDE.md", "rule")
    bundle.export(tmp_path / "state", tmp_path / "bundle")
    a = make(tmp_path, bundle_dir=str(tmp_path / "bundle"))
    assert a.options.memory_dir == f"{install.NOTES}/memory"
    env = FakeEnv()
    asyncio.run(a.install(env))
    dirs = [c[2] for c in env.calls if c[0] == "upload_dir"]
    assert dirs == ["/app/.claude", f"{install.NOTES}/memory"]
    report = [i for i, c in enumerate(env.calls) if c[0] == "exec" and c[1] == install.NOTES_REPORT]
    assert report and report[0] == len(env.calls) - 1


def test_a_bundle_without_memory_leaves_harbor_memory_unset(tmp_path):
    write(tmp_path / "state" / "app" / "CLAUDE.md", "rule")
    bundle.export(tmp_path / "state", tmp_path / "bundle")
    assert make(tmp_path, bundle_dir=str(tmp_path / "bundle")).options.memory_dir is None


def test_a_failed_check_stops_the_install(tmp_path):
    bundle.export(tmp_path / "nothing", tmp_path / "bundle")
    env = FakeEnv(fail_on="test ! -e /app/.claude")
    with pytest.raises(RuntimeError, match="/app/.claude"):
        asyncio.run(make(tmp_path, bundle_dir=str(tmp_path / "bundle")).install(env))


def test_a_wrong_claude_version_stops_the_install(tmp_path):
    with pytest.raises(RuntimeError, match="version"):
        asyncio.run(make(tmp_path).install(FakeEnv(version="2.1.299 (Claude Code)")))


def test_run_captures_the_patch_even_when_claude_fails(tmp_path, monkeypatch):
    async def boom(self, instruction, environment, context):
        raise RuntimeError("agent died")

    monkeypatch.setattr(agent.ClaudeCode, "run", boom)
    env = FakeEnv()
    with pytest.raises(RuntimeError, match="agent died"):
        asyncio.run(make(tmp_path).run("do it", env, SimpleNamespace()))
    assert env.calls[-1] == ("exec", install.CAPTURE, "root")


def test_refine_agent_lays_out_state_and_downloads_it_after(tmp_path, monkeypatch):
    ran = []

    async def fake_run(self, instruction, environment, context):
        ran.append(instruction)

    monkeypatch.setattr(agent.ClaudeCode, "run", fake_run)
    write(tmp_path / "skill" / "SKILL.md")
    write(tmp_path / "inputs" / "result.txt", "passed")
    a = make(tmp_path, cls=agent.RefineClaudeCode, state_dir=str(tmp_path / "state"),
             skill_dir=str(tmp_path / "skill"), inputs_dir=str(tmp_path / "inputs"), out_dir=str(tmp_path / "out"))
    env = FakeEnv()
    asyncio.run(a.install(env))
    assert [c[2] for c in env.calls if c[0] == "upload_dir"] == ["/app/.claude/skills/refine", "/inputs"]
    env.calls.clear()
    asyncio.run(a.run("refine it", env, SimpleNamespace()))
    assert ran == ["refine it"]
    assert any(c[0] == "exec" and "refine-history" in c[1] for c in env.calls)
    assert ("download_dir", "/app", tmp_path / "out" / "app") in env.calls
    assert ("download_dir", install.REFINE_MEMORY, tmp_path / "out" / "memory") in env.calls
    assert not any(c[0] == "exec" and c[1] == install.CAPTURE for c in env.calls)


def test_harbor_preflight_accepts_the_arm_options():
    agent.ArmClaudeCode.parse_options({"version": "2.1.293", "tools_dir": "/t", "bundle_dir": "/b"})


def test_harbor_preflight_accepts_the_refine_options():
    agent.RefineClaudeCode.parse_options({"version": "2.1.293", "tools_dir": "/t", "state_dir": "/s",
                                          "skill_dir": "/k", "inputs_dir": "/i", "out_dir": "/o"})


def test_harbor_preflight_still_rejects_unknown_options():
    with pytest.raises(ValueError, match="nonsense"):
        agent.ArmClaudeCode.parse_options({"nonsense": "1"})
```

- [ ] **Step 3: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_install.py tests/test_swepro_agent.py`
Expected: FAIL with `ImportError: cannot import name 'install'` (and `'agent'`)

- [ ] **Step 4: Write `install.py`**

Create `bench/swepro/install.py`:

```python
"""What the agent classes do to a container, as plain data so it can be tested without Harbor.

An `Upload` copies a host file or directory in; an `Exec` runs a command as root. `check=True` steps
must exit 0 or the trial fails before the agent starts.
"""
from dataclasses import dataclass
from pathlib import Path

from bench.swepro import bundle, tools

NOTES = "/opt/swepro-notes"
REFINE_MEMORY = "/root/.claude/projects/-app/memory"
REFINE_HISTORY = "/logs/agent/refine-history.json"

# From Scale's v2/tooling/locked_claude_code.py: stage everything, save the diff, unstage.
CAPTURE = (
    "mkdir -p /logs/agent; "
    "repo=$(git -C /app rev-parse --show-toplevel 2>/dev/null || git -C /testbed rev-parse --show-toplevel 2>/dev/null || echo /app); "
    'cd "$repo" && git add -A 2>/dev/null; git diff --cached > /logs/agent/model.patch 2>/dev/null; git reset -q 2>/dev/null; '
    "wc -c < /logs/agent/model.patch; true"
)

NOTES_REPORT = (
    "mkdir -p /logs/agent; "
    f"h=$(cat {NOTES}/HASH 2>/dev/null || echo); "
    "d=$(test -e /app/.claude && echo true || echo false); "
    f"n=$(ls {NOTES}/memory 2>/dev/null | wc -l | tr -d ' '); "
    'printf \'{"hash": "%s", "claude_dir": %s, "memory_files": %s}\\n\' "$h" "$d" "$n" > /logs/agent/notes.json'
)


@dataclass(frozen=True)
class Upload:
    src: Path
    dst: str
    is_dir: bool = False


@dataclass(frozen=True)
class Exec:
    command: str
    check: bool = True


def claude_steps(tools_dir: Path) -> list:
    return [
        Upload(tools_dir / tools.LOADER_REL, "/lib/ld-musl-aarch64.so.1"),
        Upload(tools_dir / tools.CLAUDE_REL, "/usr/local/bin/claude"),
        Exec("chmod 755 /lib/ld-musl-aarch64.so.1 /usr/local/bin/claude && "
             "ln -sf /lib/ld-musl-aarch64.so.1 /lib/libc.musl-aarch64.so.1 && /usr/local/bin/claude --version"),
    ]


def bundle_steps(bundle_dir: Path) -> list:
    """Install a verified bundle: notes under /app/.claude (hidden from git), memory for Harbor's memory_dir."""
    digest = bundle.verify(bundle_dir)
    steps = [Exec("test -d /app/.git && test ! -e /app/.claude && test -z \"$(git -C /app ls-files .claude)\"")]
    if (bundle_dir / ".claude").is_dir():
        steps.append(Upload(bundle_dir / ".claude", "/app/.claude", is_dir=True))
    if (bundle_dir / "memory").is_dir():
        steps += [Exec(f"mkdir -p {NOTES}"), Upload(bundle_dir / "memory", f"{NOTES}/memory", is_dir=True)]
    steps += [
        Exec("mkdir -p /app/.git/info && printf '\\n.claude/\\n' >> /app/.git/info/exclude"),
        Exec(f"mkdir -p {NOTES} && echo {digest} > {NOTES}/HASH"),
    ]
    return steps


def refine_steps(state: Path, skill: Path, inputs: Path) -> list:
    """Lay out a refine container: the notes state at /app and in memory, the snapshot skill, the inputs."""
    steps = [Exec(f"mkdir -p /app/.claude/skills {REFINE_MEMORY} /inputs")]
    if (state / "app").is_dir():
        steps.append(Upload(state / "app", "/app", is_dir=True))
    if (state / "memory").is_dir():
        steps.append(Upload(state / "memory", REFINE_MEMORY, is_dir=True))
    steps += [Upload(skill, "/app/.claude/skills/refine", is_dir=True), Upload(inputs, "/inputs", is_dir=True)]
    return steps


def refine_history_command() -> str:
    return ("python3 /app/.claude/skills/refine/scripts/harness.py --runtime claude --project /app "
            f"refine-history > {REFINE_HISTORY} 2>/logs/agent/refine-history.err; true")
```

- [ ] **Step 5: Write `agent.py`**

Create `bench/swepro/agent.py`:

```python
"""Harbor agents: Claude Code from the arm64-musl build, with an optional notes bundle, and the refine agent.

Use with `PYTHONPATH=<worktree> harbor run -a bench.swepro.agent:ArmClaudeCode --ak tools_dir=... [--ak bundle_dir=...]`.
The container steps themselves live in bench.swepro.install.
"""
from __future__ import annotations

from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode, ClaudeCodeOptions
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from bench.swepro import install, tools


class ArmClaudeCodeOptions(ClaudeCodeOptions):
    """Harbor checks every --ak against the agent's options model before a job starts."""
    tools_dir: str | None = None
    bundle_dir: str | None = None


class RefineClaudeCodeOptions(ArmClaudeCodeOptions):
    state_dir: str | None = None
    skill_dir: str | None = None
    inputs_dir: str | None = None
    out_dir: str | None = None


class ArmClaudeCode(ClaudeCode):
    options_model = ArmClaudeCodeOptions

    def __init__(self, logs_dir: Path, *args, tools_dir: str | None = None, bundle_dir: str | None = None,
                 **kwargs):
        self._tools = Path(tools_dir) if tools_dir else tools.TOOLS
        self._bundle = Path(bundle_dir) if bundle_dir else None
        if self._bundle is not None and (self._bundle / "memory").is_dir():
            kwargs["memory_dir"] = f"{install.NOTES}/memory"
        super().__init__(logs_dir, *args, **kwargs)

    @staticmethod
    def name() -> str:
        return "claude-code-arm"

    async def _apply(self, environment: BaseEnvironment, steps) -> None:
        for step in steps:
            if isinstance(step, install.Upload):
                if step.is_dir:
                    await environment.upload_dir(step.src, step.dst)
                else:
                    await environment.upload_file(step.src, step.dst)
                continue
            result = await environment.exec(command=step.command, user="root", timeout_sec=300)
            if step.check and result.return_code != 0:
                raise RuntimeError(f"install step failed ({result.return_code}): {step.command}")

    async def _install_claude(self, environment: BaseEnvironment) -> None:
        await self._apply(environment, install.claude_steps(self._tools))
        if not await self._installed_claude_satisfies_version(environment):
            raise RuntimeError(f"arm64 Claude Code does not report version {self._version}")

    async def install(self, environment: BaseEnvironment) -> None:
        await self._install_claude(environment)
        if self._bundle is not None:
            await self._apply(environment, install.bundle_steps(self._bundle))
        await self._apply(environment, [install.Exec(install.NOTES_REPORT, check=False)])

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        try:
            await super().run(instruction, environment, context)
        finally:
            try:
                await environment.exec(command=install.CAPTURE, user="root", timeout_sec=300)
            except Exception as error:  # never mask the trial outcome
                self.logger.warning(f"patch capture failed: {error}")


class RefineClaudeCode(ArmClaudeCode):
    """A refine session: the notes state, refine snapshot and inputs go in; the state comes back out."""

    options_model = RefineClaudeCodeOptions

    def __init__(self, logs_dir: Path, *args, state_dir: str, skill_dir: str, inputs_dir: str, out_dir: str,
                 **kwargs):
        self._state, self._skill = Path(state_dir), Path(skill_dir)
        self._inputs, self._out = Path(inputs_dir), Path(out_dir)
        super().__init__(logs_dir, *args, **kwargs)

    @staticmethod
    def name() -> str:
        return "claude-code-refine"

    async def install(self, environment: BaseEnvironment) -> None:
        await self._install_claude(environment)
        await self._apply(environment, install.refine_steps(self._state, self._skill, self._inputs))

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        try:
            await ClaudeCode.run(self, instruction, environment, context)
        finally:
            await environment.exec(command=install.refine_history_command(), user="root", timeout_sec=300)
            self._out.mkdir(parents=True, exist_ok=True)
            await environment.download_dir("/app", self._out / "app")
            await environment.download_dir(install.REFINE_MEMORY, self._out / "memory")
```

- [ ] **Step 6: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_install.py tests/test_swepro_agent.py`
Expected: `18 passed`

- [ ] **Step 7: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1303 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 8: Commit**

```bash
git add bench/swepro/install.py bench/swepro/agent.py tests/test_swepro_install.py tests/test_swepro_agent.py
git commit -m "feat(swepro): arm64 Claude Code agent with notes bundle, and the refine agent"
```

---

### Task 6: Harbor jobs: command, trial reading, classification, reruns

One Harbor job per run. Builds the command, reads the job's single trial (reward, exception, cost, tokens, versions, timing, notes report, patch size, an audit flag for `/tests` paths), classifies it (reusing EvoCode's exception lists), and reruns invalid runs under new names. A job directory left by a killed process counts as that try.

**Files:**
- Create: `bench/swepro/jobs.py`
- Test: `tests/test_swepro_jobs.py`

**Interfaces:**
- Consumes: Task 1 `config`; `bench.evo.run.API_EXCEPTIONS`, `MODEL_OUTCOMES`; `bench.tb4.run.STRIP_ENV`, `USAGE_EXCEPTIONS`; `bench.tb4.stream`
- Produces: `jobs.ARM_AGENT`, `jobs.REFINE_AGENT`, `jobs.REPLAY_AGENT`, `jobs.harbor_command(task_dir, job, jobs_dir, agent, kwargs, *, claude, model=None, allow_host=None) -> list`, `jobs.job_env(token, base=None, extra_path=()) -> dict`, `jobs.read_trial(job_dir) -> dict | None`, `jobs.classify(read) -> str | None`, `jobs.run_job(cmd, job_dir, *, env, log_path, run, fresh)`, `jobs.run_with_reruns(job, make_cmd, *, jobs_dir, logs_dir, env, run, before_rerun, reruns) -> (read, tries)`, `jobs.pull_image(image, run)`, `jobs.remove_image(image, run)`, `jobs.JobError`

- [ ] **Step 1: Write the failing test `test_swepro_jobs.py`**

Create `tests/test_swepro_jobs.py`:

```python
import json
import subprocess

import pytest

from bench.swepro import config, jobs

TASK = config.SMOKE_TASK


def trial(tmp_path, *, reward=1.0, exception=None, events=None, notes=None, patch=b"diff", verifier=True):
    job = tmp_path / "job"
    t = job / f"{TASK[:30]}__abc1234"
    (t / "agent").mkdir(parents=True)
    result = {
        "task_name": f"swebench-pro/{TASK}",
        "exception_info": {"exception_type": exception} if exception else None,
        "verifier_result": {"rewards": {"reward": reward}} if verifier else None,
        "agent_execution": {"started_at": "2026-10-14T05:25:36Z", "finished_at": "2026-10-14T05:26:06Z"},
        "verifier": {"started_at": "2026-10-14T05:26:06Z", "finished_at": "2026-10-14T05:29:46Z"},
    }
    (t / "result.json").write_text(json.dumps(result))
    lines = events if events is not None else [
        {"type": "system", "subtype": "init", "claude_code_version": "2.1.293", "model": "claude-sonnet-5-5"},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash",
                                                       "input": {"command": "pytest test/units"}}]}},
        {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.25,
         "modelUsage": {"claude-sonnet-5-5": {"inputTokens": 10, "cacheReadInputTokens": 5,
                                              "cacheCreationInputTokens": 1, "outputTokens": 7}}},
    ]
    (t / "agent" / "claude-code.txt").write_text("".join(json.dumps(e) + "\n" for e in lines))
    if notes is not None:
        (t / "agent" / "notes.json").write_text(json.dumps(notes))
    if patch is not None:
        (t / "agent" / "model.patch").write_bytes(patch)
    return job, t


def test_claude_command_pins_model_version_network_and_kwargs(tmp_path):
    cmd = jobs.harbor_command(tmp_path / "task", "test__t__plain__a1", tmp_path / "jobs", jobs.ARM_AGENT,
                              {"tools_dir": "/x/tools", "bundle_dir": "/x/b"}, claude=True)
    joined = " ".join(cmd)
    assert cmd[:4] == ["harbor", "run", "-p", str(tmp_path / "task")]
    for part in (f"-a {jobs.ARM_AGENT}", f"-m {config.MODEL}", f"--effort {config.EFFORT}",
                 f"--ak version={config.CLAUDE_CODE_VERSION}", "--ak disable_web_search=true",
                 "--ae CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}",
                 f"--ae CLAUDE_CODE_MAX_OUTPUT_TOKENS={config.MAX_OUTPUT_TOKENS}",
                 f"--allow-agent-host {config.ALLOW_HOST}", "--ak bundle_dir=/x/b", "--ak tools_dir=/x/tools",
                 "-n 1 -k 1 -r 0", "--job-name test__t__plain__a1", "-y"):
        assert part in joined, part


def test_oracle_command_has_no_model_or_token(tmp_path):
    cmd = jobs.harbor_command(tmp_path / "task", "validate__t__oracle__a1", tmp_path / "jobs", "oracle", {},
                              claude=False)
    assert "-m" not in cmd and not any("OAUTH" in c for c in cmd)


def test_job_env_strips_api_keys_and_adds_the_repo_to_pythonpath(tmp_path):
    env = jobs.job_env("tok", base={"ANTHROPIC_API_KEY": "k", "PATH": "/bin"}, extra_path=[tmp_path])
    assert "ANTHROPIC_API_KEY" not in env and env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"
    assert env["PYTHONPATH"].split(":") == [str(config.REPO_ROOT), str(tmp_path)]


def test_read_trial_collects_reward_cost_tokens_versions_and_timing(tmp_path):
    job, t = trial(tmp_path, notes={"hash": "abc", "claude_dir": True, "memory_files": 2})
    r = jobs.read_trial(job)
    assert r["trial_dir"] == str(t)
    assert (r["reward"], r["exception"], r["cost_usd"]) == (1.0, None, 0.25)
    assert (r["tokens_in"], r["tokens_out"]) == (16, 7)
    assert (r["claude_version"], r["model"]) == ("2.1.293", "claude-sonnet-5-5")
    assert (r["agent_sec"], r["verifier_sec"]) == (30.0, 220.0)
    assert r["notes"] == {"hash": "abc", "claude_dir": True, "memory_files": 2}
    assert r["patch_bytes"] == 4 and r["audit_tests"] is False


def test_read_trial_without_a_result_is_none(tmp_path):
    (tmp_path / "job").mkdir()
    assert jobs.read_trial(tmp_path / "job") is None


def test_a_timed_out_run_has_no_final_cost_but_keeps_its_reward(tmp_path):
    job, _ = trial(tmp_path, reward=0.0, exception="AgentTimeoutError")
    r = jobs.read_trial(job)
    assert r["cost_usd"] is None and r["reward"] == 0.0 and r["exception"] == "AgentTimeoutError"


def test_reading_a_test_or_solution_path_raises_the_audit_flag(tmp_path):
    events = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": "/tests/config.json"}}]}}]
    job, _ = trial(tmp_path, events=events)
    assert jobs.read_trial(job)["audit_tests"] is True


@pytest.mark.parametrize("exception,expected", [
    (None, None),
    ("AgentTimeoutError", None),
    ("NonZeroAgentExitCodeError", None),
    ("VerifierTimeoutError", None),
    ("ApiOverloadedError", "api_error"),
    ("ApiUsageLimitError", "usage_limit"),
    ("CancelledError", "interrupted"),
    ("RuntimeError", "infrastructure"),
    ("EnvironmentStartTimeoutError", "infrastructure"),
])
def test_classify_reruns_only_what_is_not_the_models_doing(tmp_path, exception, expected):
    job, _ = trial(tmp_path, exception=exception)
    assert jobs.classify(jobs.read_trial(job)) == expected


def test_classify_a_missing_result_as_infrastructure():
    assert jobs.classify(None) == "infrastructure"


def test_usage_limit_text_in_the_stream_is_a_usage_stop(tmp_path):
    events = [{"type": "result", "is_error": True, "result": "You've hit your usage limit"}]
    job, _ = trial(tmp_path, exception="NonZeroAgentExitCodeError", events=events)
    assert jobs.classify(jobs.read_trial(job)) == "usage_limit"


def test_pull_asks_for_amd64(tmp_path):
    calls = []
    jobs.pull_image("img:tag", run=lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0))
    assert calls == [["docker", "pull", "-q", "--platform", "linux/amd64", "img:tag"]]


def test_a_failed_pull_raises():
    with pytest.raises(jobs.JobError):
        jobs.pull_image("img:tag", run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "nope"))


def test_run_job_writes_the_log_and_returns_the_trial(tmp_path):
    made = []

    def run(cmd, **kw):
        kw["stdout"].write("harbor output\n")
        made.append(trial(tmp_path))
        return subprocess.CompletedProcess(cmd, 0)

    log = tmp_path / "logs" / "x.log"
    r = jobs.run_job(["harbor", "run"], tmp_path / "job", env={}, log_path=log, run=run)
    assert r["trial_dir"] == str(made[0][1]) and "harbor output" in log.read_text()


def test_run_job_refuses_to_reuse_a_job_directory(tmp_path):
    job, _ = trial(tmp_path)
    with pytest.raises(jobs.JobError, match="exists"):
        jobs.run_job(["harbor"], job, env={}, log_path=tmp_path / "l.log",
                     run=lambda *a, **k: pytest.fail("ran"), fresh=True)


def fake_harbor(tmp_path, exceptions):
    """A run() that leaves one trial per call, raising the next exception type in `exceptions`."""
    seq = list(exceptions)

    def run(cmd, **kw):
        name = cmd[cmd.index("--job-name") + 1]
        t = tmp_path / "jobs" / name / "trial__x"
        (t / "agent").mkdir(parents=True)
        exc = seq.pop(0)
        (t / "result.json").write_text(json.dumps({
            "task_name": TASK, "exception_info": {"exception_type": exc} if exc else None,
            "verifier_result": {"rewards": {"reward": 1.0}}}))
        return subprocess.CompletedProcess(cmd, 0)
    return run


def make_cmd(name):
    return ["harbor", "run", "--job-name", name]


def test_a_valid_first_try_is_not_rerun(tmp_path):
    read, tries = jobs.run_with_reruns("validate__t__oracle__a1", make_cmd, jobs_dir=tmp_path / "jobs",
                                       logs_dir=tmp_path / "logs", env={}, run=fake_harbor(tmp_path, [None]))
    assert tries == [{"job": "validate__t__oracle__a1", "reason": None}] and read["reward"] == 1.0


def test_infrastructure_errors_are_rerun_under_new_names(tmp_path):
    waits = []
    read, tries = jobs.run_with_reruns("j", make_cmd, jobs_dir=tmp_path / "jobs", logs_dir=tmp_path / "logs",
                                       env={}, run=fake_harbor(tmp_path, ["RuntimeError", "ApiUsageLimitError", None]),
                                       before_rerun=waits.append)
    assert [t["job"] for t in tries] == ["j", "j-rerun1", "j-rerun2"]
    assert [t["reason"] for t in tries] == ["infrastructure", "usage_limit", None]
    assert waits == ["infrastructure", "usage_limit"]


def test_reruns_stop_after_the_limit(tmp_path):
    read, tries = jobs.run_with_reruns("j", make_cmd, jobs_dir=tmp_path / "jobs", logs_dir=tmp_path / "logs",
                                       env={}, run=fake_harbor(tmp_path, ["RuntimeError"] * 3))
    assert len(tries) == 3 and tries[-1]["reason"] == "infrastructure"


def test_a_model_outcome_is_never_rerun(tmp_path):
    read, tries = jobs.run_with_reruns("j", make_cmd, jobs_dir=tmp_path / "jobs", logs_dir=tmp_path / "logs",
                                       env={}, run=fake_harbor(tmp_path, ["AgentTimeoutError"]))
    assert tries == [{"job": "j", "reason": None}]


def test_a_probe_opens_the_model_endpoint_without_claude(tmp_path):
    cmd = jobs.harbor_command(tmp_path / "t", "probe__t__probe__a1", tmp_path / "jobs", "oracle", {},
                              claude=False, allow_host=True)
    assert "--allow-agent-host" in cmd and "-m" not in cmd


def test_an_existing_job_directory_is_read_not_run(tmp_path):
    fake = fake_harbor(tmp_path, [None])
    fake(make_cmd("j"))
    read, tries = jobs.run_with_reruns("j", make_cmd, jobs_dir=tmp_path / "jobs", logs_dir=tmp_path / "logs",
                                       env={}, run=lambda *a, **k: pytest.fail("ran again"))
    assert tries == [{"job": "j", "reason": None}] and read["reward"] == 1.0
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_jobs.py`
Expected: FAIL with `ImportError: cannot import name 'jobs'`

- [ ] **Step 3: Write `jobs.py`**

Create `bench/swepro/jobs.py`:

```python
"""One Harbor job per run: build the command, run it, read the single trial it leaves, classify it.

Reads only result.json, the agent's own logs and the verifier's reward. Never prints verifier output.
"""
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from bench.evo.run import API_EXCEPTIONS, MODEL_OUTCOMES
from bench.swepro import config
from bench.tb4 import stream
from bench.tb4.run import STRIP_ENV, USAGE_EXCEPTIONS

ARM_AGENT = "bench.swepro.agent:ArmClaudeCode"
REFINE_AGENT = "bench.swepro.agent:RefineClaudeCode"
REPLAY_AGENT = "patch_replay:PatchReplayAgent"
RESULT_EXCEPTIONS = (*MODEL_OUTCOMES, "NonZeroAgentExitCodeError")  # the model's outcome, not a rerun
INPUT_FIELDS = ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")
AUDIT = re.compile(r"(?<![\w.-])/(?:tests|solution|logs/verifier)(?![\w.-])")


class JobError(RuntimeError):
    pass


def harbor_command(task_dir: Path, job: str, jobs_dir: Path, agent: str, kwargs: dict, *, claude: bool,
                   model: str | None = None, allow_host: bool | None = None) -> list:
    """`allow_host` (default: same as `claude`) opens the model endpoint during the offline agent phase."""
    cmd = ["harbor", "run", "-p", str(task_dir), "-a", agent]
    if claude:
        cmd += ["-m", config.MODEL, "--effort", config.EFFORT,
                "--ak", f"version={config.CLAUDE_CODE_VERSION}", "--ak", "disable_web_search=true",
                "--ae", "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}",
                "--ae", f"CLAUDE_CODE_MAX_OUTPUT_TOKENS={config.MAX_OUTPUT_TOKENS}"]
    elif model:
        cmd += ["-m", model]
    if claude if allow_host is None else allow_host:
        cmd += ["--allow-agent-host", config.ALLOW_HOST]
    for key, value in sorted(kwargs.items()):
        cmd += ["--ak", f"{key}={value}"]
    return cmd + ["-n", "1", "-k", "1", "-r", "0", "-o", str(jobs_dir), "--job-name", job, "-y"]


def job_env(token: str | None, base=None, extra_path=()) -> dict:
    env = {k: v for k, v in (os.environ if base is None else base).items() if k not in STRIP_ENV}
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    env["PYTHONPATH"] = ":".join([str(config.REPO_ROOT), *map(str, extra_path)])
    return env


def _trial_dir(job_dir: Path):
    found = sorted(job_dir.glob("*/result.json")) if job_dir.is_dir() else []
    return found[0].parent if len(found) == 1 else None


def _seconds(phase) -> float | None:
    if not phase or not phase.get("started_at") or not phase.get("finished_at"):
        return None
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
    return (parse(phase["finished_at"]) - parse(phase["started_at"])).total_seconds()


def _json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def read_trial(job_dir: Path):
    """The job's one trial as a flat dict, or None when Harbor left no single result.json."""
    trial = _trial_dir(job_dir)
    if trial is None:
        return None
    result = json.loads((trial / "result.json").read_text())
    exception = (result.get("exception_info") or {}).get("exception_type")
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    agent = trial / "agent"
    events = stream.read_events(agent / "claude-code.txt")
    final = None if exception == "AgentTimeoutError" else stream.final_result(events)
    usage = (final or {}).get("modelUsage") or {}
    init = stream.init_info(events)
    tool_text = " ".join(str(v) for _, b in stream.tool_uses(events) for v in (b.get("input") or {}).values())
    patch = agent / "model.patch"
    return {
        "trial_dir": str(trial),
        "task_name": str(result.get("task_name") or "").split("/")[-1],
        "reward": rewards.get("reward"),
        "exception": exception,
        "cost_usd": (final or {}).get("total_cost_usd"),
        "tokens_in": sum(int(m.get(k) or 0) for m in usage.values() for k in INPUT_FIELDS) if final else None,
        "tokens_out": sum(int(m.get("outputTokens") or 0) for m in usage.values()) if final else None,
        "claude_version": init.get("version"),
        "model": init.get("model"),
        "agent_sec": _seconds(result.get("agent_execution")),
        "verifier_sec": _seconds(result.get("verifier")),
        "notes": _json(agent / "notes.json"),
        "patch_bytes": patch.stat().st_size if patch.exists() else None,
        "audit_tests": bool(AUDIT.search(tool_text)),
        "usage_evidence": bool(stream.usage_limit_evidence(events)),
        "api_error": bool(stream.terminal_api_error(events)) and exception not in RESULT_EXCEPTIONS,
    }


def classify(read) -> str | None:
    """None for a valid run; otherwise why it must be rerun."""
    if read is None:
        return "infrastructure"
    exception = read["exception"]
    if exception == "CancelledError":
        return "interrupted"
    if exception in USAGE_EXCEPTIONS or read["usage_evidence"]:
        return "usage_limit"
    if exception in API_EXCEPTIONS or read["api_error"]:
        return "api_error"
    if exception and exception not in RESULT_EXCEPTIONS:
        return "infrastructure"
    return None


def run_job(cmd: list, job_dir: Path, *, env: dict, log_path: Path, run=subprocess.run, fresh: bool = True):
    if fresh and job_dir.exists():
        raise JobError(f"{job_dir} exists; a job directory is never reused")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as log:
        run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, text=True)
    return read_trial(job_dir)


def pull_image(image: str, run=subprocess.run) -> None:
    proc = run(["docker", "pull", "-q", "--platform", "linux/amd64", image], capture_output=True, text=True)
    if proc.returncode != 0:
        raise JobError(f"docker pull {image} failed: {(proc.stderr or '')[-300:]}")


def remove_image(image: str, run=subprocess.run) -> None:
    run(["docker", "image", "rm", image], capture_output=True, text=True)


def run_with_reruns(job: str, make_cmd, *, jobs_dir: Path, logs_dir: Path, env: dict, run=subprocess.run,
                    before_rerun=lambda reason: None, reruns: int = config.INFRA_RERUNS):
    """Run `job`; rerun it as `{job}-rerun{k}` while the result is invalid, at most `reruns` times.

    A job directory left by an earlier process (killed before its record was written) counts as that
    try: it is read, not run again, and a valid one is kept.

    Returns (read, tries): the last try's read_trial result (None if Harbor left none) and one
    {"job", "reason"} per try, where reason is classify()'s verdict (None for the valid one)."""
    tries = []
    for k in range(reruns + 1):
        name = job if k == 0 else f"{job}-rerun{k}"
        if (jobs_dir / name).exists():
            read = read_trial(jobs_dir / name)
        else:
            read = run_job(make_cmd(name), jobs_dir / name, env=env, log_path=logs_dir / f"{name}.log", run=run)
        reason = classify(read)
        tries.append({"job": name, "reason": reason})
        if reason is None:
            break
        if k < reruns:
            before_rerun(reason)
    return read, tries
```

- [ ] **Step 4: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_jobs.py`
Expected: `28 passed`

- [ ] **Step 5: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1331 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 6: Commit**

```bash
git add bench/swepro/jobs.py tests/test_swepro_jobs.py
git commit -m "feat(swepro): run, read, classify and rerun Harbor jobs"
```

---

### Task 7: Practice feedback line

The one line refine sees: `passed`, `failed: K of N graded tests failed`, or a no-result line. Counts only; no test name leaves the module.

**Files:**
- Create: `bench/swepro/feedback.py`
- Test: `tests/test_swepro_feedback.py`

**Interfaces:**
- Consumes: nothing
- Produces: `feedback.counts(trial, task) -> (failed, graded) | None`, `feedback.line(trial, task, exception) -> str`

- [ ] **Step 1: Write the failing test `test_swepro_feedback.py`**

Create `tests/test_swepro_feedback.py`:

```python
import json

import pytest

from bench.swepro import feedback


def task_dir(tmp_path, f2p, p2p, *, literal=False):
    d = tmp_path / "task"
    (d / "tests").mkdir(parents=True)
    enc = repr if literal else json.dumps
    (d / "tests" / "config.json").write_text(json.dumps(
        {"fail_to_pass": enc(f2p), "pass_to_pass": enc(p2p), "selected_test_files_to_run": "[]"}))
    return d


def trial_dir(tmp_path, statuses, reward):
    t = tmp_path / "trial"
    (t / "verifier").mkdir(parents=True)
    (t / "verifier" / "output.json").write_text(json.dumps(
        {"tests": [{"name": n, "status": s} for n, s in statuses.items()]}))
    if reward is not None:
        (t / "verifier" / "reward.txt").write_text(f"{reward}\n")
    return t


def test_a_pass_is_just_passed(tmp_path):
    t = trial_dir(tmp_path, {"a": "PASSED", "b": "PASSED"}, 1)
    assert feedback.line(t, task_dir(tmp_path, ["a"], ["b"]), None) == "passed"


def test_a_fail_counts_graded_tests_that_did_not_pass_including_missing_ones(tmp_path):
    t = trial_dir(tmp_path, {"a": "FAILED", "b": "PASSED", "extra": "FAILED"}, 0)
    d = task_dir(tmp_path, ["a", "c"], ["b", "d"])
    assert feedback.line(t, d, None) == "failed: 3 of 4 graded tests failed"


def test_python_literal_lists_are_read_too(tmp_path):
    t = trial_dir(tmp_path, {"a": "PASSED", "b": "ERROR"}, 0)
    assert feedback.line(t, task_dir(tmp_path, ["a"], ["b"], literal=True), None) == \
        "failed: 1 of 2 graded tests failed"


def test_duplicates_across_lists_count_once(tmp_path):
    t = trial_dir(tmp_path, {"a": "FAILED"}, 0)
    assert feedback.line(t, task_dir(tmp_path, ["a"], ["a"]), None) == "failed: 1 of 1 graded tests failed"


def test_a_failed_reward_with_no_failing_graded_test_says_the_count_is_unavailable(tmp_path):
    t = trial_dir(tmp_path, {"a": "PASSED"}, 0)
    assert feedback.line(t, task_dir(tmp_path, ["a"], []), None) == "failed: graded test count unavailable"


def test_missing_output_json_says_the_count_is_unavailable(tmp_path):
    t = trial_dir(tmp_path, {}, 0)
    (t / "verifier" / "output.json").unlink()
    assert feedback.line(t, task_dir(tmp_path, ["a"], []), None) == "failed: graded test count unavailable"


@pytest.mark.parametrize("exception,text", [("AgentTimeoutError", "timeout"), ("RuntimeError", "error")])
def test_no_reward_names_the_reason(tmp_path, exception, text):
    t = trial_dir(tmp_path, {}, None)
    assert feedback.line(t, task_dir(tmp_path, ["a"], []), exception) == f"failed: no result ({text})"


def test_counts_never_include_a_test_name(tmp_path):
    t = trial_dir(tmp_path, {"test_secret_name": "FAILED"}, 0)
    out = feedback.line(t, task_dir(tmp_path, ["test_secret_name"], []), None)
    assert "secret" not in out


def test_counts_are_failed_and_graded(tmp_path):
    t = trial_dir(tmp_path, {"a": "FAILED", "b": "PASSED"}, 0)
    assert feedback.counts(t, task_dir(tmp_path, ["a"], ["b"])) == (1, 2)


def test_counts_without_output_are_none(tmp_path):
    assert feedback.counts(tmp_path / "nothing", tmp_path / "nothing") is None
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_feedback.py`
Expected: FAIL with `ImportError: cannot import name 'feedback'`

- [ ] **Step 3: Write `feedback.py`**

Create `bench/swepro/feedback.py`:

```python
"""The one line refine is told about a practice run: `passed` or `failed: K of N graded tests failed`.

Reads the verifier's reward and per-test statuses and the task's graded lists, and returns only counts.
No test name ever leaves this module.
"""
import ast
import json
from pathlib import Path

PASSED = "PASSED"
UNAVAILABLE = "failed: graded test count unavailable"


def _names(value) -> list:
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except ValueError:
        return ast.literal_eval(value)  # Scale stores some lists as Python literals


def _reward(trial: Path):
    try:
        return float((trial / "verifier" / "reward.txt").read_text().strip())
    except (OSError, ValueError):
        return None


def counts(trial: Path, task: Path):
    """(failed, graded) for a run whose verifier wrote per-test statuses, else None."""
    try:
        config = json.loads((task / "tests" / "config.json").read_text())
        graded = set(_names(config.get("fail_to_pass", "[]"))) | set(_names(config.get("pass_to_pass", "[]")))
        statuses = {t["name"]: t["status"]
                    for t in json.loads((trial / "verifier" / "output.json").read_text())["tests"]}
    except (OSError, ValueError, KeyError, TypeError, SyntaxError):
        return None
    if not graded:
        return None
    return sum(1 for name in graded if statuses.get(name) != PASSED), len(graded)


def line(trial: Path, task: Path, exception) -> str:
    reward = _reward(trial)
    if reward is None:
        return f"failed: no result ({'timeout' if exception == 'AgentTimeoutError' else 'error'})"
    if reward >= 1.0:
        return "passed"
    found = counts(trial, task)
    if found is None or found[0] == 0:
        return UNAVAILABLE
    return f"failed: {found[0]} of {found[1]} graded tests failed"
```

- [ ] **Step 4: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_feedback.py`
Expected: `11 passed`

- [ ] **Step 5: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1342 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 6: Commit**

```bash
git add bench/swepro/feedback.py tests/test_swepro_feedback.py
git commit -m "feat(swepro): counts-only feedback line for refine"
```

---

### Task 8: Local validation and the split

Validates each pool task on Colima: the repo layout the refined arm needs, oracle 1, nop 0. Then the seeded 30/rest split and the seeded test order.

**Files:**
- Create: `bench/swepro/validate.py`
- Create: `bench/swepro/split.py`
- Test: `tests/test_swepro_validate.py`

**Interfaces:**
- Consumes: Task 2 `dataset.docker_image`, `dataset.study_pool`; Task 6 `jobs.*`
- Produces: `validate.validate_task(task, tasks_dir, runs, *, run) -> dict`, `validate.summarize(runs, pool) -> {'valid', 'invalid'}`, `validate.layout_ok(image, run) -> bool`, `split.split(valid) -> {'seed', 'practice', 'test'}`, `split.test_order(test) -> list`, `split.SplitTooSmall`; files `RUNS/validation/<task>.json`, `RUNS/valid.json`, `DOCS/split.json`

- [ ] **Step 1: Write the failing test `test_swepro_validate.py`**

Create `tests/test_swepro_validate.py`:

```python
import json
import subprocess

import pytest

from bench.swepro import config, split, validate

A = [f"instance_ansible__ansible-{i:040d}-v0" for i in range(80)]


def harbor(tmp_path, rewards, layout_rc=0):
    """Fake harbor: reward by (task, agent) from `rewards`, default oracle 1 and nop 0."""
    calls = []

    def run(cmd, **kw):
        if cmd[0] == "docker":
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, layout_rc if cmd[1] == "run" else 0, "", "")
        name = cmd[cmd.index("--job-name") + 1]
        agent = cmd[cmd.index("-a") + 1]
        task = cmd[cmd.index("-p") + 1].rsplit("/", 1)[-1]
        calls.append((task, agent))
        value = rewards.get((task, agent), 1.0 if agent == "oracle" else 0.0)
        t = tmp_path / "runs" / "jobs" / name / "trial__x"
        (t / "agent").mkdir(parents=True)
        exc = value if isinstance(value, str) else None
        (t / "result.json").write_text(json.dumps({
            "task_name": task, "exception_info": {"exception_type": exc} if exc else None,
            "verifier_result": None if exc else {"rewards": {"reward": value}}}))
        return subprocess.CompletedProcess(cmd, 0)
    return run, calls


@pytest.fixture
def tasks(tmp_path):
    d = tmp_path / "tasks"
    for name in A[:3]:
        (d / name).mkdir(parents=True)
        (d / name / "task.toml").write_text(f'[environment]\ndocker_image = "img:{name}"\n')
    return d


def test_a_task_is_valid_when_oracle_passes_and_nop_fails(tmp_path, tasks):
    run, calls = harbor(tmp_path, {})
    rec = validate.validate_task(A[0], tasks, tmp_path / "runs", run=run)
    assert rec["valid"] is True and (rec["oracle"], rec["nop"]) == (1.0, 0.0)
    assert json.loads((tmp_path / "runs" / "validation" / f"{A[0]}.json").read_text()) == rec
    assert ["docker", "pull", "-q", "--platform", "linux/amd64", f"img:{A[0]}"] in calls


@pytest.mark.parametrize("rewards,reason", [
    ({(A[0], "oracle"): 0.0}, "oracle scored 0.0"),
    ({(A[0], "nop"): 1.0}, "nop scored 1.0"),
    ({(A[0], "oracle"): "RuntimeError"}, "oracle: infrastructure after 3 tries"),
])
def test_a_task_is_invalid_with_a_reason(tmp_path, tasks, rewards, reason):
    run, _ = harbor(tmp_path, rewards)
    rec = validate.validate_task(A[0], tasks, tmp_path / "runs", run=run)
    assert rec["valid"] is False and rec["reason"] == reason


def test_a_saved_record_is_not_run_again(tmp_path, tasks):
    run, calls = harbor(tmp_path, {})
    validate.validate_task(A[0], tasks, tmp_path / "runs", run=run)
    n = len(calls)
    validate.validate_task(A[0], tasks, tmp_path / "runs", run=run)
    assert len(calls) == n


def test_summary_lists_valid_and_invalid(tmp_path, tasks):
    run, _ = harbor(tmp_path, {(A[1], "nop"): 1.0})
    for name in A[:3]:
        validate.validate_task(name, tasks, tmp_path / "runs", run=run)
    s = validate.summarize(tmp_path / "runs", A[:3])
    assert s["valid"] == [A[0], A[2]] and s["invalid"] == {A[1]: "nop scored 1.0"}


def test_summary_refuses_unvalidated_tasks(tmp_path):
    with pytest.raises(validate.ValidationIncomplete):
        validate.summarize(tmp_path / "runs", A[:1])


def test_split_is_seeded_and_keeps_thirty_for_practice():
    s = split.split(A)
    assert len(s["practice"]) == 30 and len(s["test"]) == 50
    assert sorted(s["practice"] + s["test"]) == sorted(A)
    assert s == split.split(list(reversed(A)))
    assert s["seed"] == config.SPLIT_SEED


def test_split_refuses_fewer_than_forty_test_tasks():
    with pytest.raises(split.SplitTooSmall):
        split.split(A[:69])
    assert len(split.split(A[:70])["test"]) == 40


def test_test_order_is_seeded_and_covers_every_test_task():
    s = split.split(A)
    order = split.test_order(s["test"])
    assert sorted(order) == sorted(s["test"]) and order == split.test_order(list(reversed(s["test"])))
    assert order != sorted(s["test"])


def test_a_task_whose_image_has_its_own_claude_dir_or_no_app_repo_is_invalid(tmp_path, tasks):
    """The refined arm's install refuses such a repo, which would score only that arm 0."""
    run, calls = harbor(tmp_path, {}, layout_rc=1)
    rec = validate.validate_task(A[0], tasks, tmp_path / "runs", run=run)
    assert rec["valid"] is False and rec["reason"] == "repo layout: /app/.git missing or /app/.claude present"
    layout = [c for c in calls if isinstance(c, list) and c[1] == "run"]
    assert layout and "--platform" in layout[0] and f"img:{A[0]}" in layout[0]
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_validate.py`
Expected: FAIL with `ImportError: cannot import name 'split'`

- [ ] **Step 3: Write `validate.py`**

Create `bench/swepro/validate.py`:

```python
"""Local validation: on Colima, the oracle must score 1 and the empty patch (nop) must score 0."""
import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bench.swepro import config, dataset, jobs
from bench.tb4.run import hold_lock


class ValidationIncomplete(RuntimeError):
    pass


def _record_path(runs: Path, task: str) -> Path:
    return runs / "validation" / f"{task}.json"


LAYOUT = "test -d /app/.git && test ! -e /app/.claude"
LAYOUT_REASON = "repo layout: /app/.git missing or /app/.claude present"


def layout_ok(image: str, run=subprocess.run) -> bool:
    """The refined arm installs notes at /app/.claude and Harbor seeds memory for /app; both need this."""
    proc = run(["docker", "run", "--rm", "--platform", "linux/amd64", "--entrypoint", "sh", image, "-c", LAYOUT],
               capture_output=True, text=True)
    return proc.returncode == 0


def validate_task(task: str, tasks_dir: Path, runs: Path = config.RUNS, *, run=subprocess.run) -> dict:
    path = _record_path(runs, task)
    if path.exists():
        return json.loads(path.read_text())
    image = dataset.docker_image(tasks_dir / task)
    jobs.pull_image(image, run=run)
    record = {"task": task, "image": image, "tries": {}}
    try:
        if not layout_ok(image, run=run):
            record["reason"] = LAYOUT_REASON
        for agent in () if "reason" in record else ("oracle", "nop"):
            name = config.job_name("validate", task, agent, 1)
            read, tries = jobs.run_with_reruns(
                name, lambda n, a=agent: jobs.harbor_command(tasks_dir / task, n, runs / "jobs", a, {}, claude=False),
                jobs_dir=runs / "jobs", logs_dir=runs / "logs", env=jobs.job_env(None), run=run)
            record["tries"][agent] = tries
            reason = tries[-1]["reason"]
            record[agent] = None if reason else read["reward"]
            if reason:
                record["reason"] = f"{agent}: {reason} after {len(tries)} tries"
                break
    finally:
        jobs.remove_image(image, run=run)
    if "reason" not in record:
        if record["oracle"] != 1.0:
            record["reason"] = f"oracle scored {record['oracle']}"
        elif record["nop"] != 0.0:
            record["reason"] = f"nop scored {record['nop']}"
    record["valid"] = "reason" not in record
    record.setdefault("reason", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def summarize(runs: Path, pool) -> dict:
    missing = [t for t in pool if not _record_path(runs, t).exists()]
    if missing:
        raise ValidationIncomplete(f"{len(missing)} tasks not validated yet, e.g. {missing[0]}")
    records = [json.loads(_record_path(runs, t).read_text()) for t in pool]
    return {"valid": sorted(r["task"] for r in records if r["valid"]),
            "invalid": {r["task"]: r["reason"] for r in records if not r["valid"]}}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate the ansible pool with oracle and nop on Colima.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--only", nargs="*", help="validate just these tasks")
    parser.add_argument("--parallel", type=int, default=2, help="tasks validated at once (Colima has 10 GB)")
    args = parser.parse_args(argv)
    tasks_dir = args.runs / "scale" / "v2" / "tasks"
    pool = dataset.study_pool(tasks_dir)
    todo = args.only or pool

    def one(task):
        record = validate_task(task, tasks_dir, args.runs)
        print(f"{task}: {'valid' if record['valid'] else record['reason']}", flush=True)

    with hold_lock(args.runs / "runner.lock"), ThreadPoolExecutor(max_workers=args.parallel) as pool_exec:
        list(pool_exec.map(one, todo))
    if not args.only:
        summary = summarize(args.runs, pool)
        (args.runs / "valid.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        print(f"{len(summary['valid'])} valid, {len(summary['invalid'])} invalid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Write `split.py`**

Create `bench/swepro/split.py`:

```python
"""The seeded practice/test split of the valid tasks, and the seeded test order."""
import argparse
import json
import random
from pathlib import Path

from bench.swepro import config


class SplitTooSmall(RuntimeError):
    pass


def split(valid) -> dict:
    names = sorted(valid)
    random.Random(config.SPLIT_SEED).shuffle(names)
    practice, test = names[:config.N_PRACTICE], names[config.N_PRACTICE:]
    if len(test) < config.MIN_TEST:
        raise SplitTooSmall(f"only {len(test)} test tasks; the spec needs {config.MIN_TEST} (ask the user)")
    return {"seed": config.SPLIT_SEED, "practice": practice, "test": test}


def test_order(test) -> list:
    names = sorted(test)
    random.Random(config.ORDER_SEED).shuffle(names)
    return names


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write the practice/test split from valid.json.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--docs", type=Path, default=config.DOCS)
    args = parser.parse_args(argv)
    valid = json.loads((args.runs / "valid.json").read_text())
    result = split(valid["valid"])
    result["test_order"] = test_order(result["test"])
    result["invalid"] = valid["invalid"]
    args.docs.mkdir(parents=True, exist_ok=True)
    (args.docs / "split.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"practice {len(result['practice'])}, test {len(result['test'])}, invalid {len(result['invalid'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_validate.py`
Expected: `11 passed`

- [ ] **Step 6: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1353 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 7: Commit**

```bash
git add bench/swepro/validate.py bench/swepro/split.py tests/test_swepro_validate.py
git commit -m "feat(swepro): validate the pool locally and split it"
```

---

### Task 9: Network probe

Copies the (excluded) smoke task with a Python probe as its oracle solution and checks the agent phase reaches only the model endpoint.

**Files:**
- Create: `bench/swepro/probe.py`
- Test: `tests/test_swepro_probe.py`

**Interfaces:**
- Consumes: Task 2 `dataset.docker_image`; Task 6 `jobs.*`
- Produces: `probe.run_probe(runs, tasks_dir, label, *, run) -> dict` (raises `probe.ProbeFailed`), `probe.parse(text)`, `probe.passed(outcomes)`, `probe.make_probe_task(src, dest)`

- [ ] **Step 1: Write the failing test `test_swepro_probe.py`**

Create `tests/test_swepro_probe.py`:

```python
import json
import subprocess

import pytest

from bench.swepro import config, probe

GOOD = """=== NETWORK PROBE (agent phase, python) ===
NET https://api.github.com blocked URLError <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING]
NET https://raw.githubusercontent.com/ansible/ansible/devel/README.md blocked URLError x
NET https://pypi.org/simple/ blocked URLError x
NET https://www.google.com blocked URLError x
NET https://api.anthropic.com/v1/models http_error 401
"""


def test_parse_reads_each_url_outcome():
    out = probe.parse(GOOD)
    assert out["https://api.anthropic.com/v1/models"] == "http_error"
    assert out["https://pypi.org/simple/"] == "blocked"
    assert len(out) == 5


def test_good_output_passes():
    assert probe.passed(probe.parse(GOOD))


@pytest.mark.parametrize("text", [
    GOOD.replace("NET https://pypi.org/simple/ blocked", "NET https://pypi.org/simple/ status"),
    GOOD.replace("http_error 401", "blocked URLError"),
    GOOD.replace("NET https://www.google.com blocked URLError x\n", ""),
    "",
])
def test_any_open_host_a_closed_model_endpoint_or_a_missing_line_fails(text):
    assert not probe.passed(probe.parse(text))


def test_make_probe_task_replaces_only_the_solution(tmp_path):
    src = tmp_path / "src"
    (src / "solution").mkdir(parents=True)
    (src / "solution" / "solve.sh").write_text("gold")
    (src / "task.toml").write_text("[agent]\nnetwork_mode = \"no-network\"\n")
    out = probe.make_probe_task(src, tmp_path / "probe")
    assert (out / "solution" / "solve.sh").read_text() == probe.PROBE_SCRIPT
    assert (out / "task.toml").read_text() == (src / "task.toml").read_text()
    assert (src / "solution" / "solve.sh").read_text() == "gold"


def test_run_probe_records_and_raises_on_failure(tmp_path):
    task = tmp_path / "tasks" / config.SMOKE_TASK
    (task / "solution").mkdir(parents=True)
    (task / "task.toml").write_text('[environment]\ndocker_image = "img:smoke"\n')
    outputs = [GOOD, GOOD.replace("http_error 401", "blocked x")]

    def run(cmd, **kw):
        if cmd[0] == "docker":
            return subprocess.CompletedProcess(cmd, 0, "", "")
        assert "--allow-agent-host" in cmd
        name = cmd[cmd.index("--job-name") + 1]
        t = tmp_path / "runs" / "jobs" / name / "trial__x"
        (t / "agent").mkdir(parents=True)
        (t / "agent" / "oracle.txt").write_text(outputs.pop(0))
        (t / "result.json").write_text(json.dumps({"task_name": config.SMOKE_TASK, "exception_info": None,
                                                   "verifier_result": {"rewards": {"reward": 0.0}}}))
        return subprocess.CompletedProcess(cmd, 0)

    rec = probe.run_probe(tmp_path / "runs", tmp_path / "tasks", "start of practice", run=run)
    assert rec["passed"] and rec["label"] == "start of practice"
    with pytest.raises(probe.ProbeFailed):
        probe.run_probe(tmp_path / "runs", tmp_path / "tasks", "after 10 tasks", run=run)
    saved = sorted((tmp_path / "runs" / "probes").glob("*.json"))
    assert [json.loads(p.read_text())["passed"] for p in saved] == [True, False]
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_probe.py`
Expected: FAIL with `ImportError: cannot import name 'probe'`

- [ ] **Step 3: Write `probe.py`**

Create `bench/swepro/probe.py`:

```python
"""Check that the agent phase is offline except the model endpoint.

The probe is a copy of the smoke task (excluded from the study) whose oracle solution tries five URLs with
Python (the images have no curl). It must reach only api.anthropic.com.
"""
import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from bench.swepro import config, dataset, jobs

MODEL_URL = "https://api.anthropic.com/v1/models"
BLOCKED_URLS = ("https://api.github.com", "https://raw.githubusercontent.com/ansible/ansible/devel/README.md",
                "https://pypi.org/simple/", "https://www.google.com")
PROBE_SCRIPT = """#!/bin/bash
echo "=== NETWORK PROBE (agent phase, python) ==="
PY=$(command -v python3 || command -v python)
"$PY" - <<'PY'
import urllib.request
for u in %s:
    try:
        r = urllib.request.urlopen(u, timeout=8); print("NET", u, "status", r.status)
    except urllib.error.HTTPError as e:
        print("NET", u, "http_error", e.code)
    except Exception as e:
        print("NET", u, "blocked", type(e).__name__, str(e)[:80])
PY
""" % repr([*BLOCKED_URLS, MODEL_URL])


class ProbeFailed(RuntimeError):
    pass


def parse(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "NET":
            out[parts[1]] = parts[2]
    return out


def passed(outcomes: dict) -> bool:
    return (outcomes.get(MODEL_URL) in ("status", "http_error")
            and all(outcomes.get(u) == "blocked" for u in BLOCKED_URLS))


def make_probe_task(src: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    solve = dest / "solution" / "solve.sh"
    solve.parent.mkdir(parents=True, exist_ok=True)
    solve.write_text(PROBE_SCRIPT)
    solve.chmod(0o755)
    return dest


def run_probe(runs: Path, tasks_dir: Path, label: str, *, run=subprocess.run) -> dict:
    probes = runs / "probes"
    probes.mkdir(parents=True, exist_ok=True)
    # count job directories, not records: a probe cut off before its record must not reuse a job name
    n = len(list((runs / "jobs").glob("probe__*"))) + 1
    task = make_probe_task(tasks_dir / config.SMOKE_TASK, runs / "probe-task" / config.SMOKE_TASK)
    image = dataset.docker_image(task)
    jobs.pull_image(image, run=run)
    name = config.job_name("probe", config.SMOKE_TASK, "probe", n)
    read = jobs.run_job(jobs.harbor_command(task, name, runs / "jobs", "oracle", {}, claude=False,
                                            allow_host=True),
                        runs / "jobs" / name, env=jobs.job_env(None), log_path=runs / "logs" / f"{name}.log", run=run)
    text = ""
    if read is not None:
        out = Path(read["trial_dir"]) / "agent" / "oracle.txt"
        text = out.read_text(errors="replace") if out.exists() else ""
    outcomes = parse(text)
    record = {"n": n, "label": label, "job": name, "outcomes": outcomes, "passed": passed(outcomes),
              "at": datetime.now(timezone.utc).isoformat()}
    (probes / f"{n:03d}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    if not record["passed"]:
        raise ProbeFailed(f"network probe {n} ({label}) failed: {outcomes}")
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the agent-phase network probe.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--label", default="manual")
    args = parser.parse_args(argv)
    record = run_probe(args.runs, args.runs / "scale" / "v2" / "tasks", args.label)
    print(json.dumps(record["outcomes"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_probe.py`
Expected: `8 passed`

- [ ] **Step 5: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1361 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 6: Commit**

```bash
git add bench/swepro/probe.py tests/test_swepro_probe.py
git commit -m "feat(swepro): agent-phase network probe"
```

---

### Task 10: Refine sessions

Builds the offline refine task, assembles its three inputs, runs one session, and absorbs the state that comes back. What refine applied is read from disk (ledger entries and bundle diff).

**Files:**
- Create: `bench/swepro/refine.py`
- Test: `tests/test_swepro_refine.py`

**Interfaces:**
- Consumes: Task 4 `bundle.export`; Task 6 `jobs.*`; `bench.tb4.stream`
- Produces: `refine.PROMPT`, `refine.build_task(dest)`, `refine.make_inputs(task_dir, trial_dir, result_line, dest)`, `refine.history_ids(trial_dir)`, `refine.skill_used(trial_dir)`, `refine.absorb(out_dir, state, archive) -> list`, `refine.run_session(index, task, task_dir, trial_dir, result_line, *, runs, skill, token, run, before_rerun) -> dict`; files `RUNS/refine/state/`, `RUNS/refine/records/NNN.json`

- [ ] **Step 1: Write the failing test `test_swepro_refine.py`**

Create `tests/test_swepro_refine.py`:

```python
import json
import subprocess
import tomllib
from pathlib import Path

import pytest

from bench.swepro import config, refine

TASK = "instance_ansible__ansible-1111111111111111111111111111111111111111-vaaaa"


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_refine_task_is_offline_with_a_dummy_verifier(tmp_path):
    d = refine.build_task(tmp_path / "task")
    toml = tomllib.loads((d / "task.toml").read_text())
    assert toml["agent"]["network_mode"] == "no-network"
    assert (d / "environment" / "Dockerfile").read_text().startswith(f"FROM {config.REFINE_BASE_IMAGE}\n")
    assert "reward.txt" in (d / "tests" / "test.sh").read_text()
    assert (d / "instruction.md").read_text() == refine.PROMPT


def test_the_prompt_authorises_one_approved_apply_and_forbids_outcomes_and_copying():
    p = refine.PROMPT
    for needle in ("/refine", "--approved", "--override-cap", "at most one", "refine-outcome",
                   "/inputs/result.txt", "/inputs/transcript.jsonl", "/inputs/task.md", "PROJECT=/app"):
        assert needle in p, needle


def test_inputs_hold_statement_transcript_and_result_only(tmp_path):
    task = write(tmp_path / "task" / "instruction.md", "Fix the vars merge.").parent
    write(tmp_path / "task" / "tests" / "config.json", "{}")
    trial = tmp_path / "trial"
    write(trial / "agent" / "sessions" / "projects" / "-app" / "s1.jsonl", '{"a": 1}\n')
    write(trial / "agent" / "sessions" / "projects" / "-app" / "s2.jsonl", '{"b": 2}\n')
    d = refine.make_inputs(task, trial, "failed: 2 of 16 graded tests failed", tmp_path / "inputs")
    assert sorted(p.name for p in d.iterdir()) == ["result.txt", "task.md", "transcript.jsonl"]
    assert (d / "transcript.jsonl").read_text() == '{"a": 1}\n{"b": 2}\n'
    assert (d / "result.txt").read_text() == "failed: 2 of 16 graded tests failed\n"


def out_dir(out, *, claude_md="rule", memory=None, skill=True):
    write(out / "app" / "CLAUDE.md", claude_md)
    write(out / "app" / ".claude" / "harness" / "refine-log.jsonl", "{}")
    if skill:
        write(out / "app" / ".claude" / "skills" / "refine" / "SKILL.md", "snapshot")
    for rel, text in (memory or {}).items():
        write(out / "memory" / rel, text)
    return out


def test_absorb_replaces_the_state_without_the_snapshot_and_archives_the_old_one(tmp_path):
    state = tmp_path / "state"
    write(state / "app" / "CLAUDE.md", "old rule")
    out = out_dir(tmp_path / "out", memory={"MEMORY.md": "- [u](u.md)", "u.md": "units"})
    changed = refine.absorb(out, state, tmp_path / "history" / "001")
    assert (state / "app" / "CLAUDE.md").read_text() == "rule"
    assert not (state / "app" / ".claude" / "skills" / "refine").exists()
    assert (state / "memory" / "u.md").read_text() == "units"
    assert (tmp_path / "history" / "001" / "app" / "CLAUDE.md").read_text() == "old rule"
    assert changed == [".claude/CLAUDE.md", "memory/MEMORY.md", "memory/u.md"]


def test_absorb_with_no_change_reports_none(tmp_path):
    state = tmp_path / "state"
    write(state / "app" / "CLAUDE.md", "rule")
    write(state / "app" / ".claude" / "harness" / "refine-log.jsonl", "{}")
    assert refine.absorb(out_dir(tmp_path / "out"), state, tmp_path / "h" / "001") == []


def test_history_entries_and_skill_use_are_read_from_disk(tmp_path):
    agent = tmp_path / "trial" / "agent"
    write(agent / "refine-history.json", json.dumps({"entries": [{"id": "e1"}, {"id": "e2"}]}))
    write(agent / "claude-code.txt", json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": "refine"}}]}}) + "\n")
    assert refine.history_ids(tmp_path / "trial") == ["e1", "e2"]
    assert refine.skill_used(tmp_path / "trial") is True
    write(agent / "claude-code.txt", "")
    assert refine.skill_used(tmp_path / "trial") is False
    assert refine.history_ids(tmp_path / "missing") is None


def fake_session(tmp_path, *, exception=None, entries=("e1",), memory=None):
    def run(cmd, **kw):
        name = cmd[cmd.index("--job-name") + 1]
        args = dict(a.split("=", 1) for a in cmd[1:] if "=" in a and not a.startswith("CLAUDE_"))
        t = tmp_path / "runs" / "jobs" / name / "trial__x"
        write(t / "result.json", json.dumps({"task_name": "refine", "exception_info":
                                             {"exception_type": exception} if exception else None,
                                             "verifier_result": {"rewards": {"reward": 1.0}}}))
        write(t / "agent" / "refine-history.json", json.dumps({"entries": [{"id": e} for e in entries]}))
        write(t / "agent" / "claude-code.txt", json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "refine"}}]}}) + "\n")
        out_dir(Path(args["out_dir"]), memory=memory or {"MEMORY.md": "m"})
        return subprocess.CompletedProcess(cmd, 0)
    return run


@pytest.fixture
def practice(tmp_path):
    task = write(tmp_path / "tasks" / TASK / "instruction.md", "do it").parent
    trial = tmp_path / "trial"
    write(trial / "agent" / "sessions" / "projects" / "-app" / "s.jsonl", "{}\n")
    (tmp_path / "skill").mkdir()
    write(tmp_path / "skill" / "SKILL.md")
    return task, trial


def test_a_session_absorbs_its_state_and_records_what_changed(tmp_path, practice):
    task, trial = practice
    rec = refine.run_session(1, TASK, task, trial, "passed", runs=tmp_path / "runs", skill=tmp_path / "skill",
                             token="tok", run=fake_session(tmp_path))
    assert rec["valid"] and rec["entries_added"] == ["e1"] and rec["skill_used"]
    assert ".claude/CLAUDE.md" in rec["changed"]
    state = tmp_path / "runs" / "refine" / "state"
    assert (state / "memory" / "MEMORY.md").read_text() == "m"
    saved = json.loads((tmp_path / "runs" / "refine" / "records" / "001.json").read_text())
    assert saved == rec


def test_an_invalid_session_leaves_the_state_alone(tmp_path, practice):
    task, trial = practice
    rec = refine.run_session(1, TASK, task, trial, "passed", runs=tmp_path / "runs", skill=tmp_path / "skill",
                             token="tok", run=fake_session(tmp_path, exception="RuntimeError"))
    assert rec["valid"] is False and rec["changed"] == []
    assert not (tmp_path / "runs" / "refine" / "state" / "app").exists()


def test_more_than_one_new_entry_is_flagged(tmp_path, practice):
    task, trial = practice
    rec = refine.run_session(1, TASK, task, trial, "passed", runs=tmp_path / "runs", skill=tmp_path / "skill",
                             token="tok", run=fake_session(tmp_path, entries=("e1", "e2")))
    assert rec["entries_added"] == ["e1", "e2"] and rec["over_one_edit"] is True


def test_running_the_snapshot_cli_counts_as_using_the_skill(tmp_path):
    """`/refine` at the top of the prompt expands the skill without a Skill tool call."""
    write(tmp_path / "trial" / "agent" / "claude-code.txt", json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command":
            "python3 /app/.claude/skills/refine/scripts/harness.py --runtime claude --project /app doctor"}}]}}) + "\n")
    assert refine.skill_used(tmp_path / "trial") is True
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_refine.py`
Expected: FAIL with `ImportError: cannot import name 'refine'`

- [ ] **Step 3: Write `refine.py`**

Create `bench/swepro/refine.py`:

```python
"""One refine session per practice task, in its own offline container.

The notes state lives at RUNS/refine/state ({app/, memory/, entries.json}). A session gets the state, the
frozen refine snapshot and three inputs (task statement, transcript, result line), and Harbor's
RefineClaudeCode copies the state back out. What refine applied is read from disk: the harness ledger
(`refine-history`) and the bundle manifest before and after, never from the session's own report.
"""
import json
import shutil
import subprocess
from pathlib import Path

from bench.swepro import bundle, config, jobs
from bench.tb4 import stream

PROMPT = """/refine

You are improving the working notes of a coding agent that solves tasks in the ansible repository
(github.com/ansible/ansible). A practice task has just finished. Its evidence is in /inputs:

- /inputs/task.md: the task statement the agent was given.
- /inputs/transcript.jsonl: the agent's session transcript.
- /inputs/result.txt: the hidden-test result in one line, for example `passed` or
  `failed: 2 of 16 graded tests failed`. You will not get test names or test output.

The project is /app. It holds no ansible code, only the notes the agent will have on future ansible
tasks: CLAUDE.md, .claude/skills, .claude/agents, and project memory. Follow the refine skill as written,
with PROJECT=/app and project scope, to decide whether this evidence supports one small change that
would help on *different* future tasks in this repository.

For this study the operator authorises you to apply your own proposal: run `refine-apply` with
`--approved` and `--override-cap`. Apply at most one proposal. If nothing is worth learning, apply
nothing and say so. Do not run `refine-outcome` or `refine-undo`, and do not copy task-specific code,
file contents or test names into the notes.
"""

TASK_TOML = """schema_version = "1.4"

[task]
name = "swepro-refine/session"
description = "One refine session over a practice task's evidence."

[agent]
network_mode = "no-network"
timeout_sec = 1800.0

[verifier]
network_mode = "public"
timeout_sec = 120.0

[environment]
network_mode = "public"
build_timeout_sec = 900.0
os = "linux"
cpus = 1
memory_mb = 2048
storage_mb = 4096
"""

TEST_SH = """#!/bin/bash
mkdir -p /logs/verifier
echo 1 > /logs/verifier/reward.txt
"""

STATE = config.RUNS / "refine" / "state"


def build_task(dest: Path = config.RUNS / "refine" / "task") -> Path:
    (dest / "environment").mkdir(parents=True, exist_ok=True)
    (dest / "tests").mkdir(parents=True, exist_ok=True)
    (dest / "task.toml").write_text(TASK_TOML)
    (dest / "instruction.md").write_text(PROMPT)
    (dest / "environment" / "Dockerfile").write_text(
        f"FROM {config.REFINE_BASE_IMAGE}\nRUN mkdir -p /app /inputs\nWORKDIR /app\n")
    test_sh = dest / "tests" / "test.sh"
    test_sh.write_text(TEST_SH)
    test_sh.chmod(0o755)
    return dest


def make_inputs(task_dir: Path, trial_dir: Path, result_line: str, dest: Path) -> Path:
    """The statement the agent saw, its transcript, and the result line. Nothing from tests/ or solution/."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copyfile(task_dir / "instruction.md", dest / "task.md")
    sessions = sorted((trial_dir / "agent" / "sessions" / "projects").rglob("*.jsonl"))
    (dest / "transcript.jsonl").write_text("".join(p.read_text(errors="replace") for p in sessions))
    (dest / "result.txt").write_text(result_line + "\n")
    return dest


def history_ids(trial_dir: Path):
    try:
        data = json.loads((trial_dir / "agent" / "refine-history.json").read_text())
    except (OSError, ValueError):
        return None
    return [str(e.get("id")) for e in data.get("entries", [])]


def skill_used(trial_dir: Path) -> bool:
    """A Skill tool call, or a call to the snapshot CLI (`/refine` in the prompt loads the skill directly)."""
    events = stream.read_events(trial_dir / "agent" / "claude-code.txt")
    return (any(b.get("name") == "Skill" and (b.get("input") or {}).get("skill") == "refine"
                for _, b in stream.tool_uses(events))
            or any(".claude/skills/refine/scripts/harness.py" in c for c in stream.bash_commands(events)))


def _bundle_files(state: Path, scratch: Path) -> dict:
    return bundle.export(state, scratch)["files"]


def absorb(out_dir: Path, state: Path, archive: Path) -> list:
    """Make `out_dir` the new state (minus the refine snapshot), keep the old state in `archive`, and
    return the bundle files that changed."""
    scratch = archive.parent / f".{archive.name}.scratch"
    before = _bundle_files(state, scratch / "before")
    new = state.with_name(state.name + ".next")
    if new.exists():
        shutil.rmtree(new)
    shutil.copytree(out_dir / "app", new / "app", symlinks=True)
    shutil.rmtree(new / "app" / ".claude" / "skills" / "refine", ignore_errors=True)
    if (out_dir / "memory").is_dir():
        shutil.copytree(out_dir / "memory", new / "memory", symlinks=True)
    if (state / "entries.json").exists():
        shutil.copyfile(state / "entries.json", new / "entries.json")
    after = _bundle_files(new, scratch / "after")
    shutil.rmtree(scratch)
    archive.parent.mkdir(parents=True, exist_ok=True)
    if state.exists():
        state.rename(archive)
    new.rename(state)
    return sorted(rel for rel in set(before) | set(after) if before.get(rel) != after.get(rel))


def run_session(index: int, task: str, task_dir: Path, trial_dir: Path, result_line: str, *, runs: Path,
                skill: Path, token: str, run=subprocess.run, before_rerun=lambda reason: None) -> dict:
    state = runs / "refine" / "state"
    task_path = build_task(runs / "refine" / "task")
    inputs = make_inputs(task_dir, trial_dir, result_line, runs / "refine" / "inputs" / f"{index:03d}")

    def make_cmd(name):
        kwargs = {"tools_dir": runs / "tools", "state_dir": state, "skill_dir": skill, "inputs_dir": inputs,
                  "out_dir": runs / "refine" / "out" / name}
        return jobs.harbor_command(task_path, name, runs / "jobs", jobs.REFINE_AGENT, kwargs, claude=True)

    read, tries = jobs.run_with_reruns(config.job_name("refine", task, "refine", 1), make_cmd,
                                       jobs_dir=runs / "jobs", logs_dir=runs / "logs", env=jobs.job_env(token),
                                       run=run, before_rerun=before_rerun)
    record = {"index": index, "task": task, "result_line": result_line, "tries": tries,
              "valid": tries[-1]["reason"] is None, "entries_added": [], "changed": [], "skill_used": False,
              "over_one_edit": False, "cost_usd": (read or {}).get("cost_usd")}
    out = runs / "refine" / "out" / tries[-1]["job"]
    if record["valid"] and (out / "app").is_dir():
        trial = Path(read["trial_dir"])
        before = json.loads((state / "entries.json").read_text()) if (state / "entries.json").exists() else []
        after = history_ids(trial) or []
        record["entries_added"] = [e for e in after if e not in before]
        record["over_one_edit"] = len(record["entries_added"]) > 1
        record["skill_used"] = skill_used(trial)
        record["changed"] = absorb(out, state, runs / "refine" / "history" / f"{index:03d}")
        (state / "entries.json").write_text(json.dumps(after) + "\n")
    elif record["valid"]:
        record["valid"] = False
        record["reason"] = "no state came back"
    path = runs / "refine" / "records" / f"{index:03d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record
```

- [ ] **Step 4: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_refine.py`
Expected: `10 passed`

- [ ] **Step 5: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1371 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 6: Commit**

```bash
git add bench/swepro/refine.py tests/test_swepro_refine.py
git commit -m "feat(swepro): offline refine sessions that read what was applied from disk"
```

---

### Task 11: Practice phase and the go/no-go gate

Runs each practice task with the notes so far, then a refine session; resumable; probes at start and every 10 tasks; computes the gate and the usage projection. Adds the shared Harbor fake used by this task's and Task 13's tests.

**Files:**
- Create: `tests/swepro_fakes.py`
- Create: `bench/swepro/practice.py`
- Test: `tests/test_swepro_practice.py`

**Interfaces:**
- Consumes: Tasks 2, 4, 6, 7, 9, 10; `bench.tb4.run.read_token`, `wait_for_headroom`, `probe_usage`, `hold_lock`
- Produces: `practice.run_practice(order, *, runs, skill, token, run, pace) -> list`, `practice.gate(records, *, usage_start, usage_end) -> dict` (with `edits_by_layer` and `sessions_without_change`), `practice.layer(rel) -> 'M' | 'G' | 'K' | 'rho'`, `practice.PracticeError`; files `RUNS/practice/records/NNN.json`, `RUNS/practice/bundles/NNN/`, `RUNS/practice/gate.json`; test helper `swepro_fakes.FakeHarbor`, `swepro_fakes.make_tasks`, `swepro_fakes.write`

- [ ] **Step 1: Add the test helper**

Create `tests/swepro_fakes.py`:

```python
"""A fake `run` for subprocess calls the swepro runner makes: docker, and harbor jobs of every phase."""
import json
import subprocess
from pathlib import Path

from bench.swepro import config


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class FakeHarbor:
    """`reward(phase, task, arm, attempt) -> float | str` decides each job: a float is the reward, a str is
    the Harbor exception type. Every call is recorded in `calls` (job names, or the docker argv)."""

    def __init__(self, runs: Path, reward=None, cost=0.5, entries=("e1",)):
        self.runs, self.cost, self.entries = runs, cost, list(entries)
        self.reward = reward or (lambda phase, task, arm, attempt: 1.0)
        self.calls = []
        self.kwargs = {}

    def __call__(self, cmd, **kw):
        if cmd[0] == "docker":
            self.calls.append(tuple(cmd))
            return subprocess.CompletedProcess(cmd, 0, "", "")
        name = cmd[cmd.index("--job-name") + 1]
        self.calls.append(name)
        args = dict(cmd[i + 1].split("=", 1) for i, a in enumerate(cmd) if a == "--ak")
        self.kwargs[name] = args
        phase, task, arm, attempt = config.parse_job_name(name.split("-rerun")[0])
        value = self.reward(phase, task, arm, attempt)
        exc = value if isinstance(value, str) else None
        trial = self.runs / "jobs" / name / "trial__x"
        write(trial / "result.json", json.dumps({
            "task_name": f"swebench-pro/{task}", "exception_info": {"exception_type": exc} if exc else None,
            "verifier_result": None if exc else {"rewards": {"reward": value}},
            "agent_execution": {"started_at": "2026-10-14T00:00:00Z", "finished_at": "2026-10-14T00:01:00Z"}}))
        events = [{"type": "system", "subtype": "init", "claude_code_version": config.CLAUDE_CODE_VERSION,
                   "model": "claude-sonnet-5-5"},
                  {"type": "assistant", "message": {"content": [
                      {"type": "tool_use", "name": "Skill", "input": {"skill": "refine"}}]}},
                  {"type": "result", "is_error": False, "total_cost_usd": self.cost,
                   "modelUsage": {"m": {"inputTokens": 100, "outputTokens": 10}}}]
        write(trial / "agent" / "claude-code.txt", "".join(json.dumps(e) + "\n" for e in events))
        write(trial / "agent" / "sessions" / "projects" / "-app" / "s.jsonl", '{"session": 1}\n')
        bundle = args.get("bundle_dir")
        notes_hash = json.loads((Path(bundle) / "manifest.json").read_text())["hash"] if bundle else ""
        write(trial / "agent" / "notes.json", json.dumps({"hash": notes_hash, "claude_dir": bool(bundle),
                                                          "memory_files": 0}))
        write(trial / "agent" / "model.patch", "diff --git a/x b/x\n")
        if not exc:
            write(trial / "verifier" / "reward.txt", f"{int(value)}\n")
            write(trial / "verifier" / "output.json", json.dumps({"tests": [
                {"name": "t1", "status": "PASSED" if value >= 1 else "FAILED"}, {"name": "t2", "status": "PASSED"}]}))
        if phase == "refine" and not exc:
            write(trial / "agent" / "refine-history.json", json.dumps(
                {"entries": [{"id": f"{task[-4:]}-{e}"} for e in self.entries]}))
            out = Path(args["out_dir"])
            write(out / "app" / "CLAUDE.md", f"lesson from {task}\n")
            write(out / "app" / ".claude" / "skills" / "refine" / "SKILL.md", "snapshot")
            write(out / "memory" / "MEMORY.md", f"- [{task[-4:]}](n.md) — note\n")
        return subprocess.CompletedProcess(cmd, 0)


def make_tasks(root: Path, names) -> Path:
    for name in names:
        write(root / name / "task.toml", f'[environment]\ndocker_image = "img:{name}"\n')
        write(root / name / "instruction.md", f"statement for {name}")
        write(root / name / "tests" / "config.json", json.dumps({"fail_to_pass": '["t1"]', "pass_to_pass": '["t2"]'}))
        write(root / name / "solution" / "solve.sh", "gold")
    return root
```

- [ ] **Step 2: Write the failing test `test_swepro_practice.py`**

Create `tests/test_swepro_practice.py`:

```python
import json

import pytest
from swepro_fakes import FakeHarbor, make_tasks, write

from bench.swepro import config, practice

P = [f"instance_ansible__ansible-{i:040d}-vp" for i in range(4)]


@pytest.fixture
def env(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    tasks = make_tasks(runs / "scale" / "v2" / "tasks", [*P, config.SMOKE_TASK])
    write(tmp_path / "skill" / "SKILL.md", "refine")
    probes = []
    monkeypatch.setattr(practice.probe, "run_probe", lambda runs, tasks, label, run: probes.append(label))
    return runs, tasks, tmp_path / "skill", probes


def go(env, harbor, order=P, **kw):
    runs, tasks, skill, _ = env
    return practice.run_practice(order, runs=runs, skill=skill, token="tok", run=harbor,
                                 pace=lambda: {"seven_day": 0.1}, **kw)


def test_each_practice_task_runs_with_the_notes_so_far_then_refines(env):
    runs, tasks, skill, probes = env
    harbor = FakeHarbor(runs, reward=lambda ph, t, a, n: 0.0 if t == P[1] else 1.0)
    records = go(env, harbor)
    names = [c for c in harbor.calls if isinstance(c, str)]
    assert names == [x for t in P for x in (config.job_name("practice", t, "refined", 1),
                                            config.job_name("refine", t, "refine", 1))]
    assert [r["feedback"] for r in records] == ["passed", "failed: 1 of 2 graded tests failed", "passed", "passed"]
    first, second = (harbor.kwargs[config.job_name("practice", t, "refined", 1)]["bundle_dir"] for t in P[:2])
    assert json.loads((runs / "practice" / "bundles" / "001" / "manifest.json").read_text())["files"] == {}
    assert ".claude/CLAUDE.md" in json.loads((runs / "practice" / "bundles" / "002" / "manifest.json").read_text())["files"]
    assert records[1]["bundle_hash"] == json.loads((runs / "practice" / "bundles" / "002" / "manifest.json").read_text())["hash"]
    assert records[0]["refine"]["entries_added"] == [f"{P[0][-4:]}-e1"]
    assert probes == ["practice start"]


def test_a_probe_runs_every_ten_tasks(env, monkeypatch):
    monkeypatch.setattr(config, "PROBE_EVERY", 2)
    go(env, FakeHarbor(env[0]))
    assert env[3] == ["practice start", "practice after 2 tasks"]


def test_practice_resumes_after_the_last_recorded_task(env):
    runs = env[0]
    go(env, FakeHarbor(runs), order=P[:2])
    harbor = FakeHarbor(runs)
    records = go(env, harbor)
    assert len(records) == 4
    assert [c for c in harbor.calls if isinstance(c, str)][0] == config.job_name("practice", P[2], "refined", 1)
    assert env[3] == ["practice start", "practice after 2 tasks"]


def test_a_record_with_a_different_task_at_its_index_stops_the_run(env):
    go(env, FakeHarbor(env[0]), order=P[:1])
    with pytest.raises(practice.PracticeError, match="order"):
        go(env, FakeHarbor(env[0]), order=list(reversed(P)))


def test_images_are_pulled_before_and_removed_after_each_task(env):
    harbor = FakeHarbor(env[0])
    go(env, harbor, order=P[:1])
    docker = [c for c in harbor.calls if isinstance(c, tuple)]
    assert docker[0][:2] == ("docker", "pull") and docker[-1][:3] == ("docker", "image", "rm")


@pytest.mark.parametrize("passes,decision", [(26, "stop_high"), (30, "stop_high"), (25, "ask_user"),
                                              (5, "ask_user"), (4, "stop_low"), (0, "stop_low")])
def test_gate(passes, decision):
    records = [{"reward": 1.0 if i < passes else 0.0, "valid": True, "cost_usd": 1.0, "tokens_in": 10,
                "tokens_out": 1, "refine": {"cost_usd": 0.5}} for i in range(30)]
    g = practice.gate(records, usage_start={"seven_day": 0.10}, usage_end={"seven_day": 0.40})
    assert g["passes"] == passes and g["decision"] == decision
    assert g["mean_agent_cost_usd"] == 1.0 and g["mean_refine_cost_usd"] == 0.5
    assert g["seven_day_used"] == pytest.approx(0.30)
    # 0.30 over 30 tasks; the agent's share of cost is 2/3; the test phase has 300 agent runs
    assert g["projected_test_seven_day"] == pytest.approx(0.30 / 30 * (2 / 3) * 300)


def test_gate_refuses_an_incomplete_practice():
    with pytest.raises(practice.PracticeError):
        practice.gate([{"reward": 1.0, "valid": True}] * 29, usage_start={}, usage_end={})


def test_a_resumed_task_keeps_the_bundle_it_ran_with(env):
    runs = env[0]
    go(env, FakeHarbor(runs), order=P[:1])
    first = json.loads((runs / "practice" / "bundles" / "001" / "manifest.json").read_text())["hash"]
    (runs / "practice" / "records" / "001.json").unlink()  # crashed after refine, before the record
    records = go(env, FakeHarbor(runs), order=P[:1])
    assert records[0]["bundle_hash"] == first


def test_gate_counts_edits_by_layer_and_sessions_that_changed_nothing():
    changes = [[".claude/CLAUDE.md"], ["memory/MEMORY.md", "memory/a.md"], [".claude/skills/x/SKILL.md"],
               [".claude/agents/r.md"], []] + [[]] * 25
    records = [{"reward": 1.0 if i < 10 else 0.0, "valid": True, "cost_usd": 1.0,
                "refine": {"cost_usd": 0.5, "changed": c, "entries_added": ["e"] if c else []}}
               for i, c in enumerate(changes)]
    g = practice.gate(records, usage_start={}, usage_end={})
    assert g["edits_by_layer"] == {"rho": 1, "M": 1, "G": 1, "K": 1}
    assert g["sessions_without_change"] == 26 and g["edits"] == 4
    assert g["projected_test_seven_day"] is None
```

- [ ] **Step 3: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_practice.py`
Expected: FAIL with `ImportError: cannot import name 'practice'`

- [ ] **Step 4: Write `practice.py`**

Create `bench/swepro/practice.py`:

```python
"""The practice phase: each practice task runs with the notes so far, then refine learns from it.

Resumable: a task whose record exists is done. Records live at RUNS/practice/records/<index>.json.
"""
import argparse
import json
import subprocess
from pathlib import Path

from bench.swepro import bundle, config, dataset, feedback, jobs, probe, refine
from bench.tb4 import run as tb4run


class PracticeError(RuntimeError):
    pass


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def _load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def practice_task(index: int, task: str, *, runs: Path, skill: Path, token: str, run, pace) -> dict:
    tasks_dir = runs / "scale" / "v2" / "tasks"
    task_dir = tasks_dir / task
    notes = runs / "practice" / "bundles" / f"{index:03d}"
    # exported once: after a crash the state may already hold this task's lesson, which the run never saw
    digest = bundle.verify(notes) if notes.exists() else bundle.export(runs / "refine" / "state", notes)["hash"]
    image = dataset.docker_image(task_dir)
    jobs.pull_image(image, run=run)
    try:
        pace()

        def make_cmd(name):
            return jobs.harbor_command(task_dir, name, runs / "jobs", jobs.ARM_AGENT,
                                       {"tools_dir": runs / "tools", "bundle_dir": notes}, claude=True)

        read, tries = jobs.run_with_reruns(config.job_name("practice", task, "refined", 1), make_cmd,
                                           jobs_dir=runs / "jobs", logs_dir=runs / "logs", env=jobs.job_env(token),
                                           run=run, before_rerun=lambda reason: pace())
    finally:
        jobs.remove_image(image, run=run)
    valid = tries[-1]["reason"] is None
    trial = Path(read["trial_dir"]) if read else None
    line = feedback.line(trial, task_dir, read["exception"]) if valid else "failed: no result (error)"
    record = {"index": index, "task": task, "job": tries[-1]["job"], "tries": tries, "valid": valid,
              "bundle_hash": digest, "feedback": line,
              **{k: (read or {}).get(k) for k in ("reward", "exception", "cost_usd", "tokens_in", "tokens_out",
                                                  "agent_sec", "notes", "claude_version", "model")}}
    if valid:
        record["refine"] = refine.run_session(index, task, task_dir, trial, line, runs=runs, skill=skill,
                                              token=token, run=run, before_rerun=lambda reason: pace())
    else:
        record["refine"] = None
    _write(runs / "practice" / "records" / f"{index:03d}.json", record)
    return record


def run_practice(order, *, runs: Path, skill: Path, token: str, run=subprocess.run, pace) -> list:
    records, ran = [], 0
    tasks_dir = runs / "scale" / "v2" / "tasks"
    start = runs / "practice" / "usage_start.json"
    for index, task in enumerate(order, 1):
        saved = _load(runs / "practice" / "records" / f"{index:03d}.json")
        if saved is not None:
            if saved["task"] != task:
                raise PracticeError(f"record {index} is {saved['task']}, but the practice order has {task}")
            records.append(saved)
            continue
        if not start.exists():
            _write(start, pace())
        done = index - 1
        if ran == 0 or done % config.PROBE_EVERY == 0:  # every process start, then every PROBE_EVERY tasks
            probe.run_probe(runs, tasks_dir, "practice start" if done == 0 else f"practice after {done} tasks",
                            run=run)
        records.append(practice_task(index, task, runs=runs, skill=skill, token=token, run=run, pace=pace))
        ran += 1
    return records


def layer(rel: str) -> str:
    """Which refine layer a bundle path belongs to: M memory, G skill, K subagent, rho CLAUDE.md."""
    if rel.startswith("memory/"):
        return "M"
    if rel.startswith(".claude/skills/"):
        return "G"
    if rel.startswith(".claude/agents/"):
        return "K"
    return "rho"


def gate(records, *, usage_start: dict, usage_end: dict) -> dict:
    if len(records) != config.N_PRACTICE:
        raise PracticeError(f"{len(records)} practice records; the gate needs {config.N_PRACTICE}")
    passes = sum(1 for r in records if r.get("valid") and (r.get("reward") or 0) >= 1.0)
    if passes >= config.GATE_HIGH:
        decision = "stop_high"
    elif passes <= config.GATE_LOW:
        decision = "stop_low"
    else:
        decision = "ask_user"
    agent_cost = [r["cost_usd"] for r in records if r.get("cost_usd") is not None]
    refine_cost = [r["refine"]["cost_usd"] for r in records if (r.get("refine") or {}).get("cost_usd") is not None]
    mean = lambda xs: sum(xs) / len(xs) if xs else None  # noqa: E731
    used = None
    if usage_start.get("seven_day") is not None and usage_end.get("seven_day") is not None:
        used = usage_end["seven_day"] - usage_start["seven_day"]
    share = sum(agent_cost) / (sum(agent_cost) + sum(refine_cost)) if agent_cost and refine_cost else 1.0
    test_runs = 2 * config.ATTEMPTS * 50
    by_layer = {}
    for r in records:  # a session that changed several files of one layer is one edit of that layer
        for name in sorted({layer(rel) for rel in (r.get("refine") or {}).get("changed", [])}):
            by_layer[name] = by_layer.get(name, 0) + 1
    return {"runs": len(records), "passes": passes, "decision": decision,
            "mean_agent_cost_usd": mean(agent_cost), "mean_refine_cost_usd": mean(refine_cost),
            "mean_tokens": mean([(r.get("tokens_in") or 0) + (r.get("tokens_out") or 0) for r in records]),
            "seven_day_used": used,
            "projected_test_seven_day": None if used is None else used / len(records) * share * test_runs,
            "edits": sum(len((r.get("refine") or {}).get("entries_added", [])) for r in records),
            "edits_by_layer": by_layer,
            "sessions_without_change": sum(1 for r in records if not (r.get("refine") or {}).get("changed"))}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the practice phase, then print the go/no-go numbers.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--docs", type=Path, default=config.DOCS)
    args = parser.parse_args(argv)
    order = json.loads((args.docs / "split.json").read_text())["practice"]
    token = tb4run.read_token()

    def pace():
        return tb4run.wait_for_headroom(lambda: tb4run.probe_usage(token), config.FIVE_HOUR_CEILING,
                                        config.WEEKLY_CEILING)

    with tb4run.hold_lock(args.runs / "runner.lock"):
        records = run_practice(order, runs=args.runs, skill=args.runs / "refine" / "skill", token=token, pace=pace)
    _write(args.runs / "practice" / "usage_end.json", pace())
    result = gate(records, usage_start=_load(args.runs / "practice" / "usage_start.json") or {},
                  usage_end=_load(args.runs / "practice" / "usage_end.json") or {})
    _write(args.runs / "practice" / "gate.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_practice.py`
Expected: `14 passed`

- [ ] **Step 6: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1385 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 7: Commit**

```bash
git add tests/swepro_fakes.py bench/swepro/practice.py tests/test_swepro_practice.py
git commit -m "feat(swepro): practice loop with refine after each task and the go/no-go gate"
```

---

### Task 12: Freeze

Exports the frozen bundle, collects every pin into `prereg.json`/`prereg.md`, refuses a gate that said stop, and checks the `swepro-prereg` tag later.

**Files:**
- Create: `bench/swepro/prereg.py`
- Test: `tests/test_swepro_prereg.py`

**Interfaces:**
- Consumes: Task 3 `tools.sha256_file`, `tools.write_manifest`; Task 4 `bundle.*`
- Produces: `prereg.FROZEN_PATHS`, `prereg.export_bundle(runs) -> dict`, `prereg.collect(runs, docs, *, versions) -> dict`, `prereg.write(p, docs) -> (json_path, md_path)`, `prereg.require_freeze(run, *, repo) -> str`, `prereg.check_runtime(p, runs)`, `prereg.FreezeError`, `prereg.NotFrozen`

- [ ] **Step 1: Write the failing test `test_swepro_prereg.py`**

Create `tests/test_swepro_prereg.py`:

```python
import json
import subprocess

import pytest

from bench.swepro import bundle, config, prereg, tools

T = [f"instance_ansible__ansible-{i:040d}-v" for i in range(80)]


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def frozen_inputs(tmp_path):
    runs, docs = tmp_path / "runs", tmp_path / "docs"
    write(runs / "refine" / "state" / "app" / "CLAUDE.md", "Use bin/ansible-test units.")
    write(runs / "refine" / "state" / "memory" / "MEMORY.md", "- [u](u.md)")
    write(runs / "refine" / "skill" / "SKILL.md", "refine")
    bundle._write_manifest(runs / "refine" / "skill")
    for rel in (tools.CLAUDE_REL, tools.LOADER_REL, "patch_replay.py"):
        write(runs / "tools" / rel, rel)
    tools.write_manifest(runs / "tools")
    split = {"seed": config.SPLIT_SEED, "practice": T[:30], "test": T[30:], "test_order": T[30:][::-1],
             "invalid": {}}
    write(docs / "split.json", json.dumps(split))
    write(runs / "practice" / "gate.json", json.dumps({"passes": 15, "decision": "ask_user"}))
    return runs, docs


def test_export_bundle_freezes_the_state(frozen_inputs):
    runs, _ = frozen_inputs
    m = prereg.export_bundle(runs)
    assert bundle.verify(runs / "bundle") == m["hash"]
    assert ".claude/CLAUDE.md" in m["files"]


def test_collect_pins_everything_the_test_phase_depends_on(frozen_inputs):
    runs, docs = frozen_inputs
    prereg.export_bundle(runs)
    p = prereg.collect(runs, docs, versions={"harbor": "0.24.0", "colima": "0.10.3"})
    assert p["bundle"]["hash"] == bundle.verify(runs / "bundle")
    assert p["refine_snapshot"]["hash"] == bundle.manifest(runs / "refine" / "skill")["hash"]
    assert p["tools"] == json.loads((runs / "tools" / "manifest.json").read_text())
    assert p["split"]["test_order"] == T[30:][::-1]
    assert p["pins"]["model"] == config.MODEL and p["pins"]["scale_commit"] == config.SCALE_COMMIT
    assert p["analysis"]["draws"] == config.PERM_DRAWS and p["analysis"]["seed"] == config.PERM_SEED
    assert p["gate"] == {"passes": 15, "decision": "ask_user"}


def test_collect_refuses_a_bundle_edited_after_export(frozen_inputs):
    runs, docs = frozen_inputs
    prereg.export_bundle(runs)
    write(runs / "bundle" / "memory" / "MEMORY.md", "edited")
    with pytest.raises(bundle.BundleError):
        prereg.collect(runs, docs, versions={})


def test_collect_refuses_a_gate_that_said_stop(frozen_inputs):
    runs, docs = frozen_inputs
    prereg.export_bundle(runs)
    write(runs / "practice" / "gate.json", json.dumps({"passes": 28, "decision": "stop_high"}))
    with pytest.raises(prereg.FreezeError, match="stop_high"):
        prereg.collect(runs, docs, versions={})


def test_collect_refuses_changed_tools(frozen_inputs):
    runs, docs = frozen_inputs
    prereg.export_bundle(runs)
    write(runs / "tools" / tools.LOADER_REL, "other loader")
    with pytest.raises(prereg.FreezeError, match="tools"):
        prereg.collect(runs, docs, versions={})


def test_write_renders_json_and_markdown(frozen_inputs):
    runs, docs = frozen_inputs
    prereg.export_bundle(runs)
    p = prereg.collect(runs, docs, versions={"harbor": "0.24.0"})
    json_path, md_path = prereg.write(p, docs)
    assert json.loads(json_path.read_text()) == p
    md = md_path.read_text()
    assert p["bundle"]["hash"] in md and "sign-flip" in md and str(len(T[30:])) in md


def git(responses):
    """Fake git: responses maps an argv tail (tuple) to (returncode, stdout)."""
    def run(cmd, **kw):
        for tail, (rc, out) in responses.items():
            if tuple(cmd[-len(tail):]) == tail:
                return subprocess.CompletedProcess(cmd, rc, out, "")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return run


def test_require_freeze_returns_the_tagged_commit():
    run = git({("rev-list", "-n", "1", config.FREEZE_TAG): (0, "abc123\n")})
    assert prereg.require_freeze(run=run) == "abc123"


def test_require_freeze_refuses_without_the_tag():
    with pytest.raises(prereg.NotFrozen, match="tag"):
        prereg.require_freeze(run=git({("rev-list", "-n", "1", config.FREEZE_TAG): (128, "")}))


def test_require_freeze_refuses_frozen_files_changed_since_the_tag():
    run = git({("rev-list", "-n", "1", config.FREEZE_TAG): (0, "abc\n"),
               ("diff", "--quiet", "abc", "--", *prereg.FROZEN_PATHS): (1, "")})
    with pytest.raises(prereg.NotFrozen, match="changed"):
        prereg.require_freeze(run=run)


def test_require_freeze_refuses_uncommitted_frozen_files():
    run = git({("rev-list", "-n", "1", config.FREEZE_TAG): (0, "abc\n"),
               ("status", "--porcelain", "--", *prereg.FROZEN_PATHS): (0, " M bench/swepro/run.py\n")})
    with pytest.raises(prereg.NotFrozen, match="uncommitted"):
        prereg.require_freeze(run=run)


def test_check_runtime_matches_bundle_and_tools(frozen_inputs):
    runs, docs = frozen_inputs
    prereg.export_bundle(runs)
    p = prereg.collect(runs, docs, versions={})
    prereg.check_runtime(p, runs)
    write(runs / "bundle" / "memory" / "MEMORY.md", "edited")
    with pytest.raises(bundle.BundleError):
        prereg.check_runtime(p, runs)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_prereg.py`
Expected: FAIL with `ImportError: cannot import name 'prereg'`

- [ ] **Step 3: Write `prereg.py`**

Create `bench/swepro/prereg.py`:

```python
"""The freeze: export the bundle, pin everything the test phase depends on, and check the tag later."""
import argparse
import json
import subprocess
from pathlib import Path

from bench.swepro import bundle, config, tools

DOCS_REL = config.DOCS.relative_to(config.REPO_ROOT).as_posix()
FROZEN_PATHS = ("bench/swepro", config.SPEC, f"{DOCS_REL}/split.json", f"{DOCS_REL}/prereg.json",
                f"{DOCS_REL}/prereg.md")
ANALYSIS = {
    "unit": "test task; y = passes / 3 per arm, scored by the pristine-image re-grade",
    "primary": "mean of d = y_refined - y_plain",
    "test": "two-sided sign-flip permutation, Monte Carlo",
    "draws": config.PERM_DRAWS,
    "seed": config.PERM_SEED,
    "alpha": 0.05,
    "interval": "95% by test inversion over shifts in steps of 0.01",
}


class FreezeError(RuntimeError):
    pass


class NotFrozen(RuntimeError):
    pass


def export_bundle(runs: Path = config.RUNS) -> dict:
    return bundle.export(runs / "refine" / "state", runs / "bundle")


def _read(path: Path):
    return json.loads(path.read_text())


def pins() -> dict:
    return {"scale_commit": config.SCALE_COMMIT, "replay_sha256": config.REPLAY_SHA256,
            "harbor": config.HARBOR_VERSION, "claude_code": config.CLAUDE_CODE_VERSION,
            "claude_arm_sha256": config.CLAUDE_ARM_SHA256, "model": config.MODEL, "effort": config.EFFORT,
            "max_output_tokens": config.MAX_OUTPUT_TOKENS, "allow_host": config.ALLOW_HOST,
            "attempts": config.ATTEMPTS, "excluded": list(config.EXCLUDED), "infra_reruns": config.INFRA_RERUNS,
            "probe_every": config.PROBE_EVERY}


def collect(runs: Path, docs: Path, *, versions: dict) -> dict:
    digest = bundle.verify(runs / "bundle")
    skill = bundle.manifest(runs / "refine" / "skill")
    if skill != _read(runs / "refine" / "skill" / "manifest.json"):
        raise FreezeError("the refine snapshot no longer matches its manifest")
    stored_tools = _read(runs / "tools" / "manifest.json")
    if stored_tools != {rel: tools.sha256_file(runs / "tools" / rel) for rel in stored_tools}:
        raise FreezeError("the tools no longer match tools/manifest.json")
    gate = _read(runs / "practice" / "gate.json")
    if gate.get("decision", "").startswith("stop"):
        raise FreezeError(f"the practice gate said {gate['decision']}; the test phase needs the user's decision")
    split = _read(docs / "split.json")
    return {"spec": config.SPEC, "pins": pins(), "versions": versions, "split": split,
            "bundle": {"hash": digest, "files": _read(runs / "bundle" / "manifest.json")["files"]},
            "refine_snapshot": skill, "tools": stored_tools, "gate": gate, "analysis": ANALYSIS}


def render(p: dict) -> str:
    lines = [
        "# SWE-bench Pro refine study: pre-registration", "",
        f"Spec: `{p['spec']}`", "",
        "## Pins", "",
        *[f"- {k}: `{v}`" for k, v in p["pins"].items()], "",
        "## Observed versions", "",
        *[f"- {k}: `{v}`" for k, v in p["versions"].items()], "",
        "## Tasks", "",
        f"- Practice: {len(p['split']['practice'])} tasks; test: {len(p['split']['test'])} tasks "
        f"(split seed {p['split']['seed']}); invalid: {len(p['split'].get('invalid', {}))}.",
        f"- Test order (seed {config.ORDER_SEED}): " + ", ".join(f"`{t}`" for t in p["split"]["test_order"]), "",
        "## Frozen notes", "",
        f"- Bundle hash: `{p['bundle']['hash']}`",
        *[f"  - `{rel}` `{h[:12]}`" for rel, h in sorted(p["bundle"]["files"].items())],
        f"- Refine snapshot hash: `{p['refine_snapshot']['hash']}`",
        *[f"- Tool `{rel}`: `{h}`" for rel, h in sorted(p["tools"].items())], "",
        "## Practice gate", "",
        *[f"- {k}: {v}" for k, v in sorted(p["gate"].items())], "",
        "## Analysis", "",
        *[f"- {k}: {v}" for k, v in p["analysis"].items()], "",
    ]
    return "\n".join(lines)


def write(p: dict, docs: Path = config.DOCS) -> tuple:
    docs.mkdir(parents=True, exist_ok=True)
    json_path, md_path = docs / "prereg.json", docs / "prereg.md"
    json_path.write_text(json.dumps(p, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render(p))
    return json_path, md_path


def _git(run, repo, *args):
    return run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def require_freeze(run=subprocess.run, *, repo=config.REPO_ROOT) -> str:
    """The tagged commit, if the tag exists and no frozen path changed since it (committed or not)."""
    tagged = _git(run, repo, "rev-list", "-n", "1", config.FREEZE_TAG)
    commit = (tagged.stdout or "").strip()
    if tagged.returncode != 0 or not commit:
        raise NotFrozen(f"no {config.FREEZE_TAG} tag: freeze first")
    if _git(run, repo, "diff", "--quiet", commit, "--", *FROZEN_PATHS).returncode != 0:
        raise NotFrozen(f"frozen paths changed since {config.FREEZE_TAG}")
    if (_git(run, repo, "status", "--porcelain", "--", *FROZEN_PATHS).stdout or "").strip():
        raise NotFrozen("frozen paths have uncommitted changes")
    return commit


def check_runtime(p: dict, runs: Path = config.RUNS) -> None:
    """The bundle and tools on disk are the frozen ones."""
    if bundle.verify(runs / "bundle") != p["bundle"]["hash"]:
        raise bundle.BundleError("the bundle on disk is not the frozen bundle")
    for rel, digest in p["tools"].items():
        if tools.sha256_file(runs / "tools" / rel) != digest:
            raise FreezeError(f"tool {rel} differs from the frozen one")


def observed_versions(run=subprocess.run) -> dict:
    out = {}
    for name, cmd in (("harbor", ["harbor", "--version"]), ("colima", ["colima", "version"]),
                      ("docker_server", ["docker", "version", "--format", "{{.Server.Version}}"])):
        proc = run(cmd, capture_output=True, text=True)
        out[name] = (proc.stdout or "").strip().splitlines()[0] if proc.returncode == 0 and proc.stdout else None
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Freeze the SWE-bench Pro refine study.")
    parser.add_argument("action", choices=("export-bundle", "write", "check"))
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--docs", type=Path, default=config.DOCS)
    args = parser.parse_args(argv)
    if args.action == "export-bundle":
        m = export_bundle(args.runs)
        print(f"bundle {m['hash']}: {len(m['files'])} files in {args.runs / 'bundle'}")
    elif args.action == "write":
        paths = write(collect(args.runs, args.docs, versions=observed_versions()), args.docs)
        print("\n".join(str(p) for p in paths))
    else:
        commit = require_freeze()
        check_runtime(_read(args.docs / "prereg.json"), args.runs)
        print(f"frozen at {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_prereg.py`
Expected: `11 passed`

- [ ] **Step 5: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1396 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 6: Commit**

```bash
git add bench/swepro/prereg.py tests/test_swepro_prereg.py
git commit -m "feat(swepro): freeze the bundle and pre-register the test phase"
```

---

### Task 13: Test phase and re-grade

Runs each test task in the frozen order: three concurrent plain/refined pairs, then a pristine re-grade of all six runs with Scale's PatchReplayAgent. Resumable per run.

**Files:**
- Create: `bench/swepro/regrade.py`
- Create: `bench/swepro/run.py`
- Test: `tests/test_swepro_run.py`

**Interfaces:**
- Consumes: Tasks 2, 6, 7, 9, 12; `bench.tb4.run` pacing and lock
- Produces: `run.run_test(order, *, runs, token, freeze, run, pace)`, `run.run_task(...)`, `run.run_one(...)`, `run.task_done(runs, task)`, `regrade.regrade(source_job, task, arm, attempt, *, runs, run) -> dict`, `regrade.regrade_practice(runs, *, run)`; files `RUNS/records/<job>.json`, `RUNS/regrade/<job>.json`

- [ ] **Step 1: Write the failing test `test_swepro_run.py`**

Create `tests/test_swepro_run.py`:

```python
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
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_run.py`
Expected: FAIL with `ImportError: cannot import name 'regrade'`

- [ ] **Step 3: Write `regrade.py`**

Create `bench/swepro/regrade.py`:

```python
"""Re-grade a run's captured model.patch on a pristine image with Scale's PatchReplayAgent.

The re-graded reward is the run's score. Records live at RUNS/regrade/<job>.json.
"""
import argparse
import json
import subprocess
from pathlib import Path

from bench.swepro import config, dataset, feedback, jobs


def regrade(source_job: str, task: str, arm: str, attempt: int, *, runs: Path, run=subprocess.run) -> dict:
    name = config.job_name("regrade", task, arm, attempt)
    path = runs / "regrade" / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    task_dir = runs / "scale" / "v2" / "tasks" / task

    def make_cmd(n):
        return jobs.harbor_command(task_dir, n, runs / "jobs", jobs.REPLAY_AGENT,
                                   {"source_job": runs / "jobs" / source_job}, claude=False, model="replay")

    read, tries = jobs.run_with_reruns(name, make_cmd, jobs_dir=runs / "jobs", logs_dir=runs / "logs",
                                       env=jobs.job_env(None, extra_path=[runs / "tools"]), run=run)
    valid = tries[-1]["reason"] is None
    graded = feedback.counts(Path(read["trial_dir"]), task_dir) if valid else None
    record = {"job": name, "source_job": source_job, "task": task, "arm": arm, "attempt": attempt,
              "tries": tries, "valid": valid, "reward": read["reward"] if valid else None,
              "graded_failed": graded[0] if graded else None, "graded_total": graded[1] if graded else None}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def regrade_practice(runs: Path, *, run=subprocess.run) -> list:
    """Re-grade every practice run (its image was removed after the task, so pull it again)."""
    out = []
    for path in sorted((runs / "practice" / "records").glob("*.json")):
        record = json.loads(path.read_text())
        image = dataset.docker_image(runs / "scale" / "v2" / "tasks" / record["task"])
        jobs.pull_image(image, run=run)
        try:
            out.append(regrade(record["job"], record["task"], "refined", 1, runs=runs, run=run))
        finally:
            jobs.remove_image(image, run=run)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Re-grade the practice runs on pristine images.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    args = parser.parse_args(argv)
    records = regrade_practice(args.runs)
    print(f"{sum(1 for r in records if r['reward'] == 1.0)} of {len(records)} practice runs pass on re-grade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Write `run.py`**

Create `bench/swepro/run.py`:

```python
"""The test phase: for each test task in the frozen order, 3 attempts, each a concurrent plain/refined pair,
then a pristine re-grade of all 6 runs. Resumable: a task with all its records and re-grades is done.
"""
import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bench.swepro import config, dataset, jobs, prereg, probe, regrade
from bench.tb4 import run as tb4run

READ_FIELDS = ("reward", "exception", "cost_usd", "tokens_in", "tokens_out", "agent_sec", "verifier_sec",
               "claude_version", "model", "notes", "patch_bytes", "audit_tests")


def _record_path(runs: Path, job: str) -> Path:
    return runs / "records" / f"{job}.json"


def run_one(task: str, arm: str, attempt: int, *, runs: Path, token: str, freeze: str, run, pace) -> dict:
    name = config.job_name("test", task, arm, attempt)
    path = _record_path(runs, name)
    if path.exists():
        return json.loads(path.read_text())
    kwargs = {"tools_dir": runs / "tools"}
    if arm == "refined":
        kwargs["bundle_dir"] = runs / "bundle"
    task_dir = runs / "scale" / "v2" / "tasks" / task

    def make_cmd(n):
        return jobs.harbor_command(task_dir, n, runs / "jobs", jobs.ARM_AGENT, kwargs, claude=True)

    read, tries = jobs.run_with_reruns(name, make_cmd, jobs_dir=runs / "jobs", logs_dir=runs / "logs",
                                       env=jobs.job_env(token), run=run, before_rerun=lambda reason: pace())
    record = {"job": name, "final_job": tries[-1]["job"], "task": task, "arm": arm, "attempt": attempt,
              "tries": tries, "valid": tries[-1]["reason"] is None, "freeze": freeze,
              **{k: (read or {}).get(k) for k in READ_FIELDS}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def task_done(runs: Path, task: str) -> bool:
    names = [config.job_name(p, task, arm, a) for a in range(1, config.ATTEMPTS + 1) for arm in config.ARMS
             for p in ("test", "regrade")]
    return all((runs / ("records" if n.startswith("test") else "regrade") / f"{n}.json").exists() for n in names)


def run_task(task: str, *, runs: Path, token: str, freeze: str, run=subprocess.run, pace) -> list:
    image = dataset.docker_image(runs / "scale" / "v2" / "tasks" / task)
    jobs.pull_image(image, run=run)
    records = []
    try:
        for attempt in range(1, config.ATTEMPTS + 1):
            pace()
            with ThreadPoolExecutor(max_workers=len(config.ARMS)) as pool:
                records += list(pool.map(lambda arm: run_one(task, arm, attempt, runs=runs, token=token,
                                                             freeze=freeze, run=run, pace=pace), config.ARMS))
        for r in records:
            regrade.regrade(r["final_job"], task, r["arm"], r["attempt"], runs=runs, run=run)
    finally:
        jobs.remove_image(image, run=run)
    return records


def run_test(order, *, runs: Path, token: str, freeze: str, run=subprocess.run, pace) -> None:
    tasks_dir = runs / "scale" / "v2" / "tasks"
    ran = 0
    for index, task in enumerate(order):
        if task_done(runs, task):
            continue
        if ran == 0 or index % config.PROBE_EVERY == 0:  # every process start, then every PROBE_EVERY tasks
            probe.run_probe(runs, tasks_dir, "test start" if index == 0 else f"test after {index} tasks", run=run)
        run_task(task, runs=runs, token=token, freeze=freeze, run=run, pace=pace)
        ran += 1
        print(f"[{index + 1}/{len(order)}] {task} done", flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the frozen test phase.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--docs", type=Path, default=config.DOCS)
    args = parser.parse_args(argv)
    freeze = prereg.require_freeze()
    p = json.loads((args.docs / "prereg.json").read_text())
    prereg.check_runtime(p, args.runs)
    token = tb4run.read_token()

    def pace():
        return tb4run.wait_for_headroom(lambda: tb4run.probe_usage(token), config.FIVE_HOUR_CEILING,
                                        config.WEEKLY_CEILING)

    with tb4run.hold_lock(args.runs / "runner.lock"):
        run_test(p["split"]["test_order"], runs=args.runs, token=token, freeze=freeze, pace=pace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_run.py`
Expected: `8 passed`

- [ ] **Step 6: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1404 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 7: Commit**

```bash
git add bench/swepro/regrade.py bench/swepro/run.py tests/test_swepro_run.py
git commit -m "feat(swepro): test phase in concurrent pairs with pristine re-grades"
```

---

### Task 14: Rows, analysis and report

Joins each run to its re-grade, runs the pre-registered Monte Carlo sign-flip test with its inverted interval, the secondary outcomes and the validity checks, and renders the report.

**Files:**
- Create: `bench/swepro/score.py`
- Create: `bench/swepro/analysis.py`
- Test: `tests/test_swepro_score.py`
- Test: `tests/test_swepro_analysis.py`

**Interfaces:**
- Consumes: Task 1 `config`; Task 12 `prereg.require_freeze`
- Produces: `score.row`, `score.build_rows(runs) -> list`, `score.write_rows`, `score.read_rows`, `analysis.task_scores(rows) -> (scores, incomplete)`, `analysis.permutation(diffs, *, draws, seed) -> dict`, `analysis.secondary(rows)`, `analysis.validity(rows, *, probes, frozen_hash)`, `analysis.summarize(...)`, `analysis.render(summary, *, practice, learned, deviations) -> str`

- [ ] **Step 1: Write the failing test `test_swepro_score.py`**

Create `tests/test_swepro_score.py`:

```python
import json

from bench.swepro import config, score

TASK = "instance_ansible__ansible-0000000000000000000000000000000000000001-v"


def record(arm="refined", attempt=1, **extra):
    base = {"job": config.job_name("test", TASK, arm, attempt), "final_job": config.job_name("test", TASK, arm, attempt),
            "task": TASK, "arm": arm, "attempt": attempt, "tries": [{"job": "x", "reason": None}], "valid": True,
            "reward": 1.0, "exception": None, "cost_usd": 0.5, "tokens_in": 100, "tokens_out": 10, "agent_sec": 60.0,
            "claude_version": "2.1.293", "model": "claude-sonnet-5-5", "notes": {"hash": "h", "claude_dir": True},
            "patch_bytes": 10, "audit_tests": False, "freeze": "abc"}
    base.update(extra)
    return base


def test_the_score_is_the_regrade_not_the_sandbox_reward():
    r = score.row(record(reward=1.0), {"valid": True, "reward": 0.0, "graded_failed": 2, "graded_total": 9})
    assert (r["reward_sandbox"], r["reward_regrade"], r["score"]) == (1.0, 0.0, 0)
    assert (r["graded_failed"], r["graded_total"]) == (2, 9)


def test_a_missing_or_invalid_regrade_scores_zero():
    assert score.row(record(), None)["score"] == 0
    assert score.row(record(), {"valid": False, "reward": None})["score"] == 0


def test_plain_notes_are_read_as_no_hash():
    r = score.row(record(arm="plain", notes={"hash": "", "claude_dir": False}), {"valid": True, "reward": 1.0})
    assert r["notes_hash"] is None and r["claude_dir"] is False and r["score"] == 1


def test_reruns_count_the_extra_tries():
    r = score.row(record(tries=[{"reason": "infrastructure"}, {"reason": None}]), None)
    assert r["reruns"] == 1


def test_build_rows_joins_records_to_regrades(tmp_path):
    (tmp_path / "records").mkdir()
    (tmp_path / "regrade").mkdir()
    rec = record()
    (tmp_path / "records" / f"{rec['job']}.json").write_text(json.dumps(rec))
    name = config.job_name("regrade", TASK, "refined", 1)
    (tmp_path / "regrade" / f"{name}.json").write_text(json.dumps({"valid": True, "reward": 1.0}))
    rows = score.build_rows(tmp_path)
    assert len(rows) == 1 and rows[0]["score"] == 1 and set(rows[0]) == set(score.ROW_FIELDS)
    score.write_rows(rows, tmp_path / "rows.jsonl")
    assert score.read_rows(tmp_path / "rows.jsonl") == rows
```

- [ ] **Step 2: Write the failing test `test_swepro_analysis.py`**

Create `tests/test_swepro_analysis.py`:

```python
import itertools

import pytest

from bench.swepro import analysis, config

FROZEN = "f" * 64


def row(task, arm, attempt, score, **extra):
    base = {"task": task, "arm": arm, "attempt": attempt, "score": score, "valid": True, "reruns": 0,
            "reward_sandbox": float(score), "reward_regrade": float(score), "regrade_valid": True,
            "exception": None, "cost_usd": 1.0, "tokens_in": 100, "tokens_out": 10, "agent_sec": 120.0,
            "claude_version": config.CLAUDE_CODE_VERSION, "model": "claude-sonnet-5-5",
            "notes_hash": FROZEN if arm == "refined" else None, "claude_dir": arm == "refined",
            "audit_tests": False, "graded_failed": 0 if score else 2, "graded_total": 10, "job": f"{task}-{arm}-{attempt}"}
    base.update(extra)
    return base


def rows_for(task, plain, refined):
    return [row(task, "plain", a + 1, s) for a, s in enumerate(plain)] + \
           [row(task, "refined", a + 1, s) for a, s in enumerate(refined)]


def test_task_scores_are_pass_shares_and_incomplete_tasks_are_listed():
    rows = rows_for("a", (1, 0, 0), (1, 1, 0)) + rows_for("b", (1, 1, 1), (1, 1, 1))[:5]
    scores, incomplete = analysis.task_scores(rows)
    assert scores == {"a": {"plain": pytest.approx(1 / 3), "refined": pytest.approx(2 / 3)}}
    assert incomplete == ["b"]


def exact_p(diffs, delta=0.0):
    n, obs = len(diffs), abs(sum(diffs) - delta * len(diffs))
    hits = sum(1 for s in itertools.product((1, -1), repeat=n)
               if abs(sum(a * d for a, d in zip(s, diffs)) - delta * sum(s)) >= obs - 1e-9)
    return hits / 2 ** n


def test_the_monte_carlo_p_matches_exact_enumeration():
    diffs = [1 / 3, 2 / 3, 0, -1 / 3, 1 / 3, 1, 0, 1 / 3, 2 / 3, -1 / 3]
    r = analysis.permutation(diffs, draws=100_000, seed=config.PERM_SEED)
    assert r["p"] == pytest.approx(exact_p(diffs), abs=0.005)
    assert (r["wins"], r["losses"], r["ties"]) == (6, 2, 2)
    assert r["mean"] == pytest.approx(sum(diffs) / 10)


def test_the_interval_contains_the_mean_and_excludes_far_shifts():
    diffs = [0.33, 0.67, 0.0, 0.33, 0.33, 1.0, 0.0, 0.33, 0.67, 0.33] * 3
    r = analysis.permutation(diffs, draws=20_000, seed=1)
    lo, hi = r["ci95"]
    assert lo < r["mean"] < hi and lo > 0 and hi < 1


def test_the_test_is_seeded():
    diffs = [0.33, -0.33, 0.67, 0, 0.33]
    assert analysis.permutation(diffs, draws=5_000, seed=7) == analysis.permutation(diffs, draws=5_000, seed=7)


def test_no_tasks_gives_no_result():
    assert analysis.permutation([], draws=10, seed=1)["p"] is None


def test_secondary_outcomes_per_arm():
    rows = rows_for("a", (1, 0, 0), (1, 1, 0))
    s = analysis.secondary(rows)
    assert s["plain"]["passes"] == 1 and s["refined"]["passes"] == 2 and s["refined"]["runs"] == 3
    assert s["plain"]["mean_graded_failed"] == pytest.approx(4 / 3)
    assert s["plain"]["median_agent_min"] == 2.0 and s["plain"]["cost_usd"] == 3.0


def test_disagreements_between_sandbox_and_regrade_are_counted():
    rows = rows_for("a", (1, 1, 1), (1, 1, 1))
    rows[0]["reward_sandbox"] = 0.0
    assert analysis.secondary(rows)["plain"]["sandbox_regrade_disagree"] == 1


def test_validity_checks_pass_on_clean_rows():
    rows = rows_for("a", (1, 0, 0), (1, 1, 0))
    checks = analysis.validity(rows, probes=[{"passed": True}], frozen_hash=FROZEN)
    assert all(ok for _, ok, _ in checks), checks


@pytest.mark.parametrize("change,label", [
    ({"notes_hash": "other"}, "frozen bundle"),
    ({"claude_version": "2.1.299"}, "Claude Code"),
    ({"audit_tests": True}, "/tests"),
    ({"regrade_valid": False}, "re-grade"),
])
def test_validity_flags_each_problem(change, label):
    rows = rows_for("a", (1, 0, 0), (1, 1, 0))
    rows[4].update(change)
    failed = [name for name, ok, _ in analysis.validity(rows, probes=[{"passed": True}], frozen_hash=FROZEN)
              if not ok]
    assert any(label in name for name in failed), failed


def test_validity_flags_a_plain_run_that_found_notes():
    rows = rows_for("a", (1, 0, 0), (1, 1, 0))
    rows[0]["claude_dir"] = True
    failed = [n for n, ok, _ in analysis.validity(rows, probes=[], frozen_hash=FROZEN) if not ok]
    assert any("plain" in n for n in failed)


def test_render_shows_the_result_and_every_task():
    rows = rows_for("a", (1, 0, 0), (1, 1, 0)) + rows_for("b", (1, 1, 1), (1, 1, 0))
    summary = analysis.summarize(rows, probes=[{"passed": True}], frozen_hash=FROZEN, draws=1000)
    text = analysis.render(summary, practice={"passes": 15, "runs": 30, "edits": 9}, learned="It learned X.",
                           deviations="- 2026-10-20: none")
    for needle in ("Mean d", "| a |", "| b |", "It learned X.", "2026-10-20", "sign-flip", "Limits"):
        assert needle in text, needle
```

- [ ] **Step 3: Run it to make sure it fails**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_score.py tests/test_swepro_analysis.py`
Expected: FAIL with `ImportError: cannot import name 'score'` (and `'analysis'`)

- [ ] **Step 4: Write `score.py`**

Create `bench/swepro/score.py`:

```python
"""One row per test run in RUNS/rows.jsonl: the run record joined to its re-grade."""
import argparse
import json
from pathlib import Path

from bench.swepro import config

ROW_FIELDS = ("task", "arm", "attempt", "job", "final_job", "reruns", "valid", "reward_sandbox", "regrade_valid",
              "reward_regrade", "score", "exception", "cost_usd", "tokens_in", "tokens_out", "agent_sec",
              "claude_version", "model", "notes_hash", "claude_dir", "audit_tests", "patch_bytes",
              "graded_failed", "graded_total", "freeze")


def row(record: dict, regrade) -> dict:
    notes = record.get("notes") or {}
    regrade = regrade or {}
    reward_regrade = regrade.get("reward") if regrade.get("valid") else None
    return {
        "task": record["task"], "arm": record["arm"], "attempt": record["attempt"], "job": record["job"],
        "final_job": record["final_job"], "reruns": len(record["tries"]) - 1, "valid": record["valid"],
        "reward_sandbox": record.get("reward"), "regrade_valid": bool(regrade.get("valid")),
        "reward_regrade": reward_regrade, "score": 1 if reward_regrade == 1.0 else 0,
        "exception": record.get("exception"), "cost_usd": record.get("cost_usd"),
        "tokens_in": record.get("tokens_in"), "tokens_out": record.get("tokens_out"),
        "agent_sec": record.get("agent_sec"), "claude_version": record.get("claude_version"),
        "model": record.get("model"), "notes_hash": notes.get("hash") or None,
        "claude_dir": notes.get("claude_dir"), "audit_tests": record.get("audit_tests"),
        "patch_bytes": record.get("patch_bytes"), "graded_failed": regrade.get("graded_failed"),
        "graded_total": regrade.get("graded_total"), "freeze": record.get("freeze"),
    }


def build_rows(runs: Path = config.RUNS) -> list:
    rows = []
    for path in sorted((runs / "records").glob("test__*.json")):
        record = json.loads(path.read_text())
        name = config.job_name("regrade", record["task"], record["arm"], record["attempt"])
        regrade_path = runs / "regrade" / f"{name}.json"
        rows.append(row(record, json.loads(regrade_path.read_text()) if regrade_path.exists() else None))
    return rows


def write_rows(rows, path: Path) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def read_rows(path: Path) -> list:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write RUNS/rows.jsonl from the test records and re-grades.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    args = parser.parse_args(argv)
    rows = build_rows(args.runs)
    write_rows(rows, args.runs / "rows.jsonl")
    print(f"{len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Write `analysis.py`**

Create `bench/swepro/analysis.py`:

```python
"""The pre-registered analysis and the report."""
import argparse
import json
import random
import statistics
from pathlib import Path

from bench.swepro import config, prereg, score

ALPHA = 0.05
TOL = 1e-9
GRID = tuple(k / 100 for k in range(-100, 101))
LIMITS = (
    "One repository (ansible) and one model (Sonnet 5.5) through Claude Code only.",
    "Plain against refined cannot separate useful lessons from any added notes; a placebo-notes arm would.",
    "The ansible fixes are public, so the model may have seen some of them; both arms share this.",
    "Edits were auto-approved and the daily cap lifted, which normal refine use does not do.",
    "The amd64 task images ran under Rosetta on Colima with an arm64 Claude Code; scores are not "
    "comparable with the public leaderboard.",
    "One operator ran the study.",
)


def task_scores(rows) -> tuple:
    """({task: {arm: passes / 3}} for tasks with every run, sorted list of incomplete tasks)."""
    by = {}
    for r in rows:
        by.setdefault(r["task"], {}).setdefault(r["arm"], {})[r["attempt"]] = r["score"]
    scores, incomplete = {}, []
    for task, arms in sorted(by.items()):
        if all(len(arms.get(arm, {})) == config.ATTEMPTS for arm in config.ARMS):
            scores[task] = {arm: sum(arms[arm].values()) / config.ATTEMPTS for arm in config.ARMS}
        else:
            incomplete.append(task)
    return scores, incomplete


def _p(pairs, observed: float, n: int, delta: float) -> float:
    target = abs(observed - delta * n)
    hits = sum(1 for a, b in pairs if abs(a - delta * b) >= target - TOL)
    return hits / len(pairs)


def permutation(diffs, *, draws: int = config.PERM_DRAWS, seed: int = config.PERM_SEED) -> dict:
    """Two-sided sign-flip test by Monte Carlo (the observed signs are one of the draws); 95% interval by
    inverting the test over GRID with the same draws."""
    diffs = [float(d) for d in diffs]
    n = len(diffs)
    wins, losses = sum(d > TOL for d in diffs), sum(d < -TOL for d in diffs)
    counts = {"wins": wins, "losses": losses, "ties": n - wins - losses}
    if not n:
        return {"n": 0, "mean": None, "ci95": (None, None), "p": None, "draws": draws, **counts}
    rng = random.Random(seed)
    pairs = [(sum(diffs), n)]  # with signs s: (sum s*d, sum s)
    for _ in range(draws):
        signs = [1 if rng.random() < 0.5 else -1 for _ in range(n)]
        pairs.append((sum(s * d for s, d in zip(signs, diffs)), sum(signs)))
    total = sum(diffs)
    kept = [delta for delta in GRID if _p(pairs, total, n, delta) >= ALPHA]
    return {"n": n, "mean": total / n, "ci95": (min(kept), max(kept)) if kept else (None, None),
            "p": _p(pairs, total, n, 0.0), "draws": draws, **counts}


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def secondary(rows) -> dict:
    out = {}
    for arm in config.ARMS:
        mine = [r for r in rows if r["arm"] == arm]
        out[arm] = {
            "runs": len(mine), "passes": sum(r["score"] for r in mine),
            "mean_graded_failed": _mean([r["graded_failed"] for r in mine]),
            "cost_usd": sum(r["cost_usd"] or 0 for r in mine),
            "mean_tokens": _mean([(r["tokens_in"] or 0) + (r["tokens_out"] or 0) for r in mine
                                  if r["tokens_in"] is not None]),
            "median_agent_min": statistics.median([r["agent_sec"] / 60 for r in mine if r["agent_sec"]])
            if any(r["agent_sec"] for r in mine) else None,
            "timeouts": sum(r["exception"] == "AgentTimeoutError" for r in mine),
            "nonzero_exits": sum(r["exception"] == "NonZeroAgentExitCodeError" for r in mine),
            "sandbox_regrade_disagree": sum(1 for r in mine if r["regrade_valid"]
                                            and (r["reward_sandbox"] or 0) != (r["reward_regrade"] or 0)),
            "reruns": sum(r["reruns"] for r in mine),
            "invalid_after_reruns": sum(not r["valid"] for r in mine),
        }
    return out


def validity(rows, *, probes, frozen_hash: str) -> list:
    """(check, ok, detail) for every integrity check in the spec."""
    def where(bad):
        return "; ".join(f"{r['task']} {r['arm']} a{r['attempt']}" for r in bad[:10]) or "none"

    refined = [r for r in rows if r["arm"] == "refined"]
    plain = [r for r in rows if r["arm"] == "plain"]
    checks = [
        ("Every refined run logged the frozen bundle hash", [r for r in refined if r["notes_hash"] != frozen_hash]),
        ("No plain run found notes", [r for r in plain if r["claude_dir"] or r["notes_hash"]]),
        (f"Every run reported Claude Code {config.CLAUDE_CODE_VERSION} and claude-sonnet-5-5",
         [r for r in rows if r["claude_version"] != config.CLAUDE_CODE_VERSION
          or r["model"] != config.MODEL.split("/")[-1]]),
        ("No transcript touched /tests, /solution or /logs/verifier", [r for r in rows if r["audit_tests"]]),
        ("Every run has a valid re-grade", [r for r in rows if not r["regrade_valid"]]),
    ]
    out = [(name, not bad, where(bad)) for name, bad in checks]
    failed_probes = [p for p in probes if not p.get("passed")]
    out.append((f"All {len(probes)} network probes passed", not failed_probes, f"{len(failed_probes)} failed"))
    return out


def summarize(rows, *, probes, frozen_hash: str, draws: int = config.PERM_DRAWS) -> dict:
    scores, incomplete = task_scores(rows)
    diffs = [s["refined"] - s["plain"] for s in scores.values()]
    return {"primary": permutation(diffs, draws=draws), "scores": scores, "incomplete": incomplete,
            "secondary": secondary([r for r in rows if r["task"] in scores]),
            "validity": validity(rows, probes=probes, frozen_hash=frozen_hash)}


def _f(x, spec=".2f"):
    return "n/a" if x is None else format(x, spec)


def render(summary: dict, *, practice: dict, learned: str, deviations: str) -> str:
    p, s = summary["primary"], summary["secondary"]
    lo, hi = p["ci95"]
    lines = [
        "# SWE-bench Pro: does refine make Claude Code better on new tasks?", "",
        f"Refine learned from {practice.get('runs', 'n/a')} ansible practice tasks; its notes were frozen; plain "
        f"Claude Code and Claude Code with the frozen notes then tried each of {p['n']} unseen ansible tasks "
        f"{config.ATTEMPTS} times. Every run was scored by re-grading its patch on a pristine image.", "",
        f"Setup: {config.MODEL} at effort {config.EFFORT}, Claude Code {config.CLAUDE_CODE_VERSION} (arm64-musl "
        f"build), Harbor {config.HARBOR_VERSION}, SWE-bench Pro v2 at {config.SCALE_COMMIT[:12]}, agent offline "
        f"except {config.ALLOW_HOST}.", "",
        "## Primary result", "",
        f"Analysis: two-sided sign-flip permutation (Monte Carlo, {p['draws']} draws, seed {config.PERM_SEED}), "
        f"alpha {ALPHA}, on d = refined - plain pass share per task.", "",
        f"- Tasks analysed: {p['n']}" + (f" (incomplete, left out: {len(summary['incomplete'])})"
                                          if summary["incomplete"] else ""),
        f"- Mean d: {_f(p['mean'], '+.3f')}",
        f"- 95% interval: [{_f(lo, '+.2f')}, {_f(hi, '+.2f')}]",
        f"- Two-sided p: {_f(p['p'], '.4f')}",
        f"- Refined won / lost / tied: {p['wins']} / {p['losses']} / {p['ties']}", "",
        "## Per-task results", "",
        "| Task | Plain | Refined | d |", "| --- | --- | --- | --- |",
        *[f"| {t} | {v['plain']:.2f} | {v['refined']:.2f} | {v['refined'] - v['plain']:+.2f} |"
          for t, v in summary["scores"].items()], "",
        "## Secondary outcomes", "",
        "| Outcome | Plain | Refined |", "| --- | --- | --- |",
        *[f"| {label} | {_f(s['plain'][key], fmt)} | {_f(s['refined'][key], fmt)} |" for label, key, fmt in (
            ("Runs", "runs", "d"), ("Passes", "passes", "d"),
            ("Graded tests failed per run (mean)", "mean_graded_failed", ".2f"),
            ("Cost reported by Claude Code (USD)", "cost_usd", ".2f"), ("Tokens per run (mean)", "mean_tokens", ",.0f"),
            ("Agent minutes per run (median)", "median_agent_min", ".1f"), ("Agent timeouts", "timeouts", "d"),
            ("Non-zero agent exits", "nonzero_exits", "d"),
            ("In-sandbox vs re-grade disagreements", "sandbox_regrade_disagree", "d"),
            ("Reruns", "reruns", "d"), ("Invalid after reruns (scored 0)", "invalid_after_reruns", "d"))], "",
        "## Practice", "",
        *[f"- {k}: {v}" for k, v in sorted(practice.items())], "",
        "## What refine learned", "", learned.strip(), "",
        "## Validity", "",
        *[f"- {name}: {'met' if ok else 'not met: ' + detail}" for name, ok, detail in summary["validity"]], "",
        "## Deviations", "", deviations.strip() or "None.", "",
        "## Limits", "", *[f"- {line}" for line in LIMITS], "",
        "## Credit", "",
        f"SWE-bench Pro by Scale AI ({config.SCALE_URL.removesuffix('.git')} at {config.SCALE_COMMIT[:12]}). "
        "This report reproduces no hidden tests, reference patches, per-test results or transcripts.", "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Analyse the test phase and write the report.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--docs", type=Path, default=config.DOCS)
    args = parser.parse_args(argv)
    prereg.require_freeze()
    frozen = json.loads((args.docs / "prereg.json").read_text())
    rows = score.read_rows(args.runs / "rows.jsonl")
    probes = [json.loads(p.read_text()) for p in sorted((args.runs / "probes").glob("*.json"))]
    summary = summarize(rows, probes=probes, frozen_hash=frozen["bundle"]["hash"])
    gate = json.loads((args.runs / "practice" / "gate.json").read_text())
    learned = (args.docs / "learned.md").read_text() if (args.docs / "learned.md").exists() else "Not written."
    deviations = (args.runs / "deviations.md").read_text() if (args.runs / "deviations.md").exists() else ""
    (args.docs / "report.md").write_text(render(summary, practice=gate, learned=learned, deviations=deviations))
    (args.runs / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=list) + "\n")
    print(args.docs / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run the task's tests**

Run: `sh bench/swepro/test.sh -q tests/test_swepro_score.py tests/test_swepro_analysis.py`
Expected: `19 passed`

- [ ] **Step 7: Run the whole suite**

Run: `sh bench/swepro/test.sh -q tests/ 2>&1 | tail -1`
Expected: `1423 passed` (TB4 and EvoCode tests unchanged)

- [ ] **Step 8: Commit**

```bash
git add bench/swepro/score.py bench/swepro/analysis.py tests/test_swepro_score.py tests/test_swepro_analysis.py
git commit -m "feat(swepro): rows, pre-registered analysis and report"
```

---

### Task 15: Runbook (operator; no new code)

Every step runs from `"$WT"` with the system `python3`, which needs 3.11 or later for `tomllib`. A step marked **STOP** waits for the user. Long phases run in the background under `caffeinate`, and progress is monitored by **counting record files only**: never print a record's transcript or verifier fields. Any departure from this runbook is appended to `~/swepro-runs/deviations.md` as a dated line, e.g. `- 2026-10-20: Step 11: ...`.

- [ ] **Step 1: Preconditions**

```bash
cd "$WT"
colima status 2>&1 | head -3
docker context show
docker info --format '{{.Architecture}}'
harbor --version
security find-generic-password -s tb4-horizon-claude-token >/dev/null && echo token-present
pgrep -x Docker >/dev/null && echo "Docker Desktop is running: quit it" || echo "Docker Desktop not running"
```

Expected:
- Colima running;
- context `colima`;
- `aarch64`;
- `0.24.0`;
- `token-present`;
- `Docker Desktop not running`.

If Colima is stopped, run `colima start --vm-type vz --vz-rosetta --cpu 6 --memory 10 --disk 150`. On an authentication failure at any later step, the **user** refreshes the token in their own terminal:
1. run `claude setup-token`;
2. run `security add-generic-password -U -s tb4-horizon-claude-token -a "$USER" -w '<token>'`.

- [ ] **Step 2: Dataset and re-grader**

Run: `python3 -m bench.swepro.dataset`
Expected: `82 ansible tasks; 80 in the study pool`. The pinned `patch_replay.py` is now at `~/swepro-runs/tools/patch_replay.py`.

- [ ] **Step 3: Tools**

Run: `python3 -m bench.swepro.tools`
Expected: a JSON manifest. Its `claude-arm64-musl/claude` value is `00755ae106b6925c1adb2b17e4c6d9b0c41eb4cc55bcad3581345b0aa3176c85`, and its `patch_replay.py` value is `5c8b344de37164e9723f1724c2573013957fb644c3913a64c12c1718c737d876`.

- [ ] **Step 4: Refine snapshot**

The refine skill and its `harness/` package come from `main`'s working tree, where they are not yet committed. Record what `main` is at, then snapshot:

```bash
git -C "/Users/deeps/Documents/NEW STUFF/fun " rev-parse HEAD
git -C "/Users/deeps/Documents/NEW STUFF/fun " status --short -- harness .claude/skills/refine | wc -l
python3 -c "
from pathlib import Path
from bench.swepro import bundle, config
main = Path('/Users/deeps/Documents/NEW STUFF/fun ')
m = bundle.snapshot_refine(main / '.claude/skills/refine', main / 'harness', config.RUNS / 'refine' / 'skill')
print(m['hash'], len(m['files']), 'files')"
T=$(mktemp -d); mkdir -p "$T/app"
HOME="$T" python3 ~/swepro-runs/refine/skill/scripts/harness.py --runtime claude --project "$T/app" refine-count
```

Expected:
- a hash and about 9 files;
- `refine-count` prints JSON with `"used": 0` and `"cap": 3`.

Append a deviations line naming `main`'s commit and the count of uncommitted refine/harness files: the snapshot is pinned by hash but is not reproducible from git history.

- [ ] **Step 5: Network probe**

Run: `python3 -m bench.swepro.probe --label setup`
Expected: four URLs `blocked` and `https://api.anthropic.com/v1/models` `http_error`. On `ProbeFailed`: **STOP** and tell the user; nothing runs with an open network.

- [ ] **Step 6: Local validation (about 6 hours)**

```bash
mkdir -p ~/swepro-runs/logs
caffeinate -dims nohup python3 -m bench.swepro.validate > ~/swepro-runs/logs/validate.out 2>&1 &
```

Monitor with `ls ~/swepro-runs/validation | wc -l` (out of 80). When the process ends, `tail -1 ~/swepro-runs/logs/validate.out` shows `N valid, M invalid`. Invalid tasks and reasons are in `~/swepro-runs/valid.json`. With fewer than 70 valid tasks, Step 7 refuses (`SplitTooSmall`): **STOP** and ask the user.

- [ ] **Step 7: Split, committed before any practice run**

```bash
python3 -m bench.swepro.split
git add docs/evaluations/swepro-refine/split.json
git commit -m "docs(swepro): practice/test split of the validated ansible tasks"
```

Expected: `practice 30, test <N-30>, invalid <M>`.

- [ ] **Step 8: Practice (about 6-8 hours)**

```bash
caffeinate -dims nohup python3 -m bench.swepro.practice > ~/swepro-runs/logs/practice.out 2>&1 &
```

Monitor with `ls ~/swepro-runs/practice/records | wc -l` (out of 30). If the process dies, rerun the same command: it resumes. After the first record exists, check that refine is really running:

```bash
python3 -c "
import json, pathlib
for p in sorted(pathlib.Path.home().glob('swepro-runs/refine/records/*.json')):
    r = json.loads(p.read_text())
    print(p.stem, 'valid' if r['valid'] else 'INVALID', 'skill' if r['skill_used'] else 'NO-SKILL',
          len(r['entries_added']), 'edits', len(r['changed']), 'files changed')"
```

If the first three sessions are all `NO-SKILL`, kill the practice process and **STOP**: refine is not being exercised.

When practice ends, the gate JSON is printed and saved to `~/swepro-runs/practice/gate.json`. Then re-grade the practice runs:

Run: `python3 -m bench.swepro.regrade`
Expected: `<k> of 30 practice runs pass on re-grade`.

- [ ] **Step 9: STOP: the go/no-go gate**

Tell the user, from `gate.json` and the line above:
- passes out of 30, in-sandbox and re-graded;
- the decision;
- the edits applied;
- the mean agent and refine cost;
- the projected seven-day usage of the test phase.

The decision rules:
- `stop_high` or `stop_low`: the study stops here, and the report says why.
- `ask_user`: the test phase starts only after the user says go.

- [ ] **Step 10: Freeze the notes; STOP for the user to read them**

```bash
python3 -m bench.swepro.prereg export-bundle
find ~/swepro-runs/bundle -type f ! -name manifest.json | sort | while read -r f; do echo "== ${f#$HOME/swepro-runs/bundle/}"; cat "$f"; done
```

Read the notes for any text copied from one task's statement, code or test names. Show the user the file list and the notes. They either approve the bundle as is, or stop the study. The bundle is never edited.

- [ ] **Step 11: Pre-register and tag**

Write `docs/evaluations/swepro-refine/learned.md`: a short plain-language summary of what the notes say, by layer, quoting at most a few lines. Then:

```bash
python3 -m bench.swepro.prereg write
git add docs/evaluations/swepro-refine/prereg.json docs/evaluations/swepro-refine/prereg.md docs/evaluations/swepro-refine/learned.md
git commit -m "docs(swepro): pre-register the test phase with the frozen notes"
git tag swepro-prereg
python3 -m bench.swepro.prereg check
```

Expected: `frozen at <commit>`. Never move or recreate the tag. A code fix after this point needs the user's approval and a deviations line.

- [ ] **Step 12: Test phase (about 1.5-2 days)**

```bash
caffeinate -dims nohup python3 -m bench.swepro.run > ~/swepro-runs/logs/run.out 2>&1 &
```

Monitor:
- `ls ~/swepro-runs/records | wc -l`: out of 6 × the number of test tasks;
- `ls ~/swepro-runs/regrade | wc -l`: out of 30 practice re-grades plus 6 × the number of test tasks;
- `tail -2 ~/swepro-runs/logs/run.out`.

If the process dies, rerun the same command: it resumes. A `ProbeFailed` means **STOP**: tell the user. No interim looks are planned. If the user asks for one, report counts of passes per arm from `rows.jsonl` only (after `python3 -m bench.swepro.score`), append a deviations line, and let the run continue unchanged.

- [ ] **Step 13: Rows, analysis and report**

```bash
python3 -m bench.swepro.score
python3 -m bench.swepro.analysis
cp ~/swepro-runs/deviations.md docs/evaluations/swepro-refine/deviations.md 2>/dev/null || true
```

Expected:
- `<6N> rows`;
- the path of `docs/evaluations/swepro-refine/report.md`.

Check SWE-bench Pro's license and citation at the pinned commit before anything is published:

```bash
git -C ~/swepro-runs/scale show 66f92766bba642462d4bbe5479e83f91f9211862:LICENSE | head -5
git -C ~/swepro-runs/scale show 66f92766bba642462d4bbe5479e83f91f9211862:README.md | grep -n -i -A3 'citation\|bibtex\|license' | head -20
```

Add the license name and the citation to the report's Credit section if the render lacks them, and append a deviations line naming the license.

Read the report's Validity section. For each "not met" line, rule on it in a deviations line: what it is, and whether counting it the other way changes the primary result. Do not open transcripts to decide.

- [ ] **Step 14: Commit the report; STOP for the user's decision**

```bash
git add docs/evaluations/swepro-refine/report.md docs/evaluations/swepro-refine/learned.md docs/evaluations/swepro-refine/deviations.md 2>/dev/null
git commit -m "docs(swepro): SWE-bench Pro refine study report"
```

Tell the user the primary result in plain words. They decide whether to push the branch and tag, and whether to publish the report.
