# SWE-bench Pro: does refine make Claude Code better on new tasks?

Status: design approved by the user in conversation on 2026-10-14; written here
for review.

## Purpose and user decisions

The question: when refine learns from practice tasks in one repository, and its
notes are then frozen, does Claude Code with those notes solve **new** tasks
from the same repository more often than plain Claude Code?

The EvoCode first look (branch `eval/evocode-horizon`, report `74622fa`) tested
Horizon and found nothing. This study tests the other skill, refine. It avoids
three weaknesses of Prime Intellect's self-improvement claims: we never score on
the tasks refine learned from, we compare against a plain arm on the same tasks,
and we report every attempt instead of the best of several.

The user's choices:
- **Learn, freeze, then test.** Refine learns on practice tasks; its notes are
  frozen; the frozen notes are tested on unseen tasks.
- **Practice feedback:** pass/fail plus a count, e.g. "failed: 2 of 16 graded
  tests failed". No test names, no test output.
- **Arms:** plain Claude Code against Claude Code with the frozen refine notes.
  No Horizon in either arm.
- **Attempts:** 3 per arm per test task.
- **Benchmark:** SWE-bench Pro v2 instead of EvoCode. EvoCode's tasks share
  little with each other, its unused tasks sit at 0 or 1, and it is slow.
- **Local engine:** Colima instead of Docker Desktop, no cloud account.

Out of scope: a placebo-notes arm, other repositories, other models, Horizon,
refine running during the test. These are named in the report's limits.

## Background facts (smoke test, 2026-10-14)

- **Dataset.** SWE-bench Pro v2, `github.com/scaleapi/SWE-bench_Pro-os` at
  `66f92766bba642462d4bbe5479e83f91f9211862`, directory `v2/tasks/`: 642 Harbor
  tasks, 82 from `ansible/ansible`. Harbor's hub copy `scale-ai/swe-bench-pro`
  is the older v1 (731 tasks, `jefzda/sweap-images`) and is not used.
- **Images.** One prebuilt image per task, `ghcr.io/scaleapi/swe-bench_pro-v2:<id>`,
  linux/amd64 only, anonymous pull. Compose asks for arm64 unless the image is
  pulled first with `docker pull --platform linux/amd64`.
- **Offline agent.** Every `task.toml` sets `[agent] network_mode = "no-network"`.
  Harbor 0.24.0 enforces it with an egress sidecar that needs the kernel option
  `CONFIG_NFT_FIB_INET`. Docker Desktop's kernel lacks it and Harbor refuses
  the task. Colima 0.10.3 (`--vm-type vz --vz-rosetta`, Ubuntu kernel
  6.8.0-117) has it as a module. A probe from the agent phase reached only
  `api.anthropic.com` (HTTP 401); GitHub, raw.githubusercontent.com, PyPI and
  Google all failed.
- **Claude Code under Rosetta.** The x64 build (Bun) refuses to start: "CPU
  lacks AVX support". The linux-arm64-musl build of 2.1.293 (sha256
  `00755ae106b6925c1adb2b17e4c6d9b0c41eb4cc55bcad3581345b0aa3176c85`) runs
  natively inside the amd64 container when Alpine's `ld-musl-aarch64.so.1` is
  copied to `/lib`. Its child processes (bash, python, the repo's tests) run
  under Rosetta. The prototype agent is `~/swepro-runs/agents/arm_claude_code.py`.
- **Mounts.** Colima shares only `$HOME`, so all run data lives under
  `~/swepro-runs/`.
- **Smoke task.** `instance_ansible__ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8-v30a923fb5c164d6cd18280c02422f75e611e8fb2`:
  oracle 1.0, empty patch 0.0, Sonnet 5.5 passed (27 s agent, $0.06, verifier
  217 s). It is excluded from the study.
- **Verifier output.** `verifier/output.json` holds `{"tests": [{"name", "status"}]}`
  and `verifier/reward.txt` holds 0 or 1. The graded test lists are in the
  task's `tests/config.json`.
- **Refine.** The refine skill's CLI `scripts/harness.py` is a symlink into the
  repo's `harness/` package. On `main` that package and the skill edits are not
  yet committed. Refine's four layers are native Claude Code locations: memory
  (M) under `~/.claude/projects/<project key>/memory/` with a `MEMORY.md` index,
  skills (G) in `.claude/skills/`, subagents (K) in `.claude/agents/`, and
  `CLAUDE.md` (rho).

## Study design

### Tasks and split

1. Start from the 82 ansible tasks in `v2/tasks/`. Remove the smoke task and
   `instance_ansible__ansible-40ade1f84b8bb10a63576b0ac320c13f57c87d34-v6382ea168a93d80a64aab1fbd8c4f02dc5ada5bf`
   (named timing-sensitive in Scale's `GATE.md`). 80 remain.
2. **Local validation.** On Colima, run every remaining task with the oracle
   agent and the nop agent, under the task's own network policy. A task is
   valid if oracle scores 1 and nop scores 0. An infrastructure exception gets
   up to two reruns. Invalid tasks are dropped and listed.
3. **Split.** Sort the valid task ids, shuffle with `random.Random(20261014)`,
   take the first 30 as practice and the rest as test. If fewer than 70 tasks
   are valid, practice stays 30 and the test set shrinks; below 40 test tasks
   the study stops for a user decision.

The split file is committed before any practice run.

### Practice phase (refine learns)

The 30 practice tasks run one at a time, in split order, so the notes grow.

For each practice task:
1. **Agent run.** Claude Code solves the task with the current notes
   installed exactly as in the test phase's refined arm (see Arms).
2. **Feedback line.** A script reads the verifier output and the task's
   graded lists and prints only `passed` or
   `failed: K of N graded tests failed`. A run that times out or crashes gets
   `failed: no result (timeout)` or `failed: no result (error)`.
3. **Refine session.** A separate Claude Code session runs `/refine` with
   three inputs: the task's `instruction.md`, the agent's session transcript,
   and the feedback line. It may apply **at most one** edit through
   `refine-apply --approved`, or decide nothing is worth learning. It records
   its choice, and the edit's entry id if any, in a one-line result file.

Refine sessions run in their **own container** through Harbor:
- an arm64 image with python3 and the arm64 Claude Code build;
- network: `no-network` with `--allow-agent-host api.anthropic.com`;
- contents: the three inputs, the refine snapshot (below), and the notes state;
- no access to any task directory, test file, image or other run.

The notes state is a sandbox home plus a sandbox project, kept on the host at
`~/swepro-runs/refine/state/` and copied in before and out after each session.
Its project path inside the refine container is `/app`, the same as in the
SWE-bench Pro images, so memory lands under the same project key.

Departures from normal refine use, recorded in the report:
- Edits are applied with `--approved` without a human reading them. The
  prompt states that the operator authorised this for the study.
- The rolling cap (3 applies per 24 h per scope) is lifted with
  `--override-cap`, also authorised in the prompt. Scope is always `project`.
- `refine-outcome` is not used.

**Refine snapshot.** Before practice, the refine skill (`SKILL.md`,
`references/`) and the `harness/` package are copied from `main`'s working
tree with symlinks resolved into `~/swepro-runs/refine/skill/`. A sha256
manifest of every file goes into the pre-registration.

**Go/no-go gate.** After practice:
- If 26 or more of the 30 practice runs passed (above 85%), or 4 or fewer
  passed (below 15%), stop and bring it to the user.
- Report tokens and cost per practice run and project the test phase's
  seven-day usage. The test phase starts only after the user says go.

### Freeze

1. Export the notes bundle from the state: `CLAUDE.md`, `.claude/skills/*`
   (excluding `refine` and `horizon`), `.claude/agents/*`, and the memory
   directory. Write a sha256 manifest.
2. **User checkpoint.** The user reads the bundle. The operator also checks
   it for text copied from one task's statement or patch. The bundle is used
   as is: if the user rejects it, the study stops rather than editing notes.
3. Commit the frozen spec values, the split, the bundle manifest, the
   refine snapshot manifest and the analysis code. Tag that commit
   `swepro-prereg`. The bundle text stays in `~/swepro-runs/bundle/`; the
   report summarises it and may quote it.

### Arms (test phase)

Both arms use the same image, the same `instruction.md`, the same agent
settings and no extra prompt text.

- **Plain.** Claude Code with no CLAUDE.md, no project `.claude/`, and an
  empty `~/.claude/projects/`.
- **Refined.** Before the agent starts, the install step writes the bundle:
  `CLAUDE.md` and `.claude/` into `/app`, and memory into the agent user's
  `~/.claude/projects/-app/memory/`. The bundle paths are added to
  `/app/.git/info/exclude` so they never enter the captured patch. The
  install step records the bundle manifest hash in the agent log.

Agent settings, both arms and the practice phase:
- `anthropic/claude-sonnet-5-5`, `--effort high`;
- Claude Code 2.1.293, arm64-musl build;
- `disable_web_search=true`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000`;
- OAuth token from Keychain service `tb4-horizon-claude-token`, passed as
  `CLAUDE_CODE_OAUTH_TOKEN`, never printed;
- the task's own timeouts (agent 3000 s) and network policy, with
  `--allow-agent-host api.anthropic.com`;
- one attempt per Harbor job (`-n 1 -k 1 -r 0`).

### Running the test phase

- Order: tasks in a seeded order (`random.Random(20261015)`). For each task,
  attempts 1, 2, 3; each attempt is a **pair**, plain and refined, run at the
  same time (2 concurrent jobs).
- A task's image is pulled once before its first pair and removed after its
  last pair and re-grade.
- **Infrastructure errors** (Harbor environment or verifier exceptions, image
  pull failures) are rerun, up to two times per run, and logged. An agent
  timeout, a non-zero agent exit or an empty patch is a result, not an error.
- **Network probe** (Python, as in the smoke test) at the start of each phase
  and after every 10 tasks. A failed probe stops the run.
- No interim looks are planned. If the user asks for one, it shows counts
  only, is logged in `deviations.md`, and the run continues unchanged.

### Scoring

- Every run's captured `model.patch` is **re-graded** on a pristine image
  with Scale's `patch_replay:PatchReplayAgent` (code read and pinned by
  sha256 before use). The re-graded reward is the run's score. The in-sandbox
  reward is kept as a secondary record.
- A run with no patch or no re-grade result scores 0.
- Practice runs are re-graded too, but the feedback line refine sees comes
  from the in-sandbox verifier (it is needed straight away).

### Outcomes and pre-registered analysis

- **Unit:** the test task. For each arm, `y = passes / 3`.
- **Primary:** `d = y_refined - y_plain` per task. Two-sided sign-flip
  permutation test on the mean of `d`, 100,000 draws with
  `random.Random(20261016)`, the observed sign pattern included. Alpha 0.05.
  95% interval by test inversion over shifts in steps of 0.01. Also report
  wins, losses and ties.
- **Secondary:**
  - total passes per arm (out of 150);
  - graded tests failed per run;
  - cost reported by Claude Code, tokens, agent minutes per run;
  - agent timeouts and non-zero exits;
  - in-sandbox vs re-graded disagreements.
- **Descriptive (practice):** practice pass rate, edits applied by layer,
  "nothing to learn" count, bundle size.
- **Power note:** with about 50 tasks and a paired SD near 0.30, the smallest
  reliably detectable mean `d` is about 0.12.

### Integrity checks (in the report's validity section)

- Every refined run logged the frozen bundle hash; no plain run found a
  bundle file.
- Every run reported Claude Code 2.1.293 and model `claude-sonnet-5-5`.
- All network probes passed.
- No transcript shows the agent reading `/tests` or `/solution` (automated
  flag from tool-call paths; the operator does not read transcripts).
- Re-grade coverage: every run has a re-graded result or a logged reason.
- Every rerun is listed with its reason.

## Runner architecture

New package `bench/swepro/` on branch `eval/swepro-refine` (worktree
`.superpowers/worktrees/swepro-refine`, based on `eval/evocode-horizon`).
It reuses `bench/tb4` and `bench/evo` generic pieces (token reader,
pre-registration check, stream-json reader) without changing their
behaviour. Each module has one job:

- `config.py`: every pinned value in this spec.
- `dataset.py`: fetch and verify the v2 tree at the pinned commit; list the
  ansible tasks; apply the exclusions.
- `validate.py`: oracle and nop runs; writes `valid.json`.
- `split.py`: the seeded split.
- `agent.py`: the Harbor agent class. It installs the arm64-musl Claude Code
  and the musl loader, optionally installs a notes bundle, and captures
  `model.patch`.
- `feedback.py`: the pass/fail-plus-count line from verifier output, printing
  counts only.
- `refine.py`: builds the refine container task, copies state in and out,
  reads the one-line result.
- `practice.py`: the practice loop and the go/no-go numbers.
- `bundle.py`: export, manifest, install-time hash.
- `run.py`: the test phase (pairs, pulls, reruns, probes).
- `regrade.py`: the patch_replay re-grade.
- `score.py` and `analysis.py`: rows, the permutation test, the report.

Run data lives in `~/swepro-runs/` (`dataset/`, `jobs/`, `refine/`,
`bundle/`, `rows.jsonl`, `deviations.md`). Code and the report are in the
repo; run data is not.

## Operator rules

- Never open or print anything under a task's `tests/` or `solution/`, any
  `verifier/` output beyond `reward.txt` and the feedback counts, or the
  graded lists in `config.json`. Scripts read these and print only counts.
- Never read test-phase transcripts or patches. Practice transcripts go to
  refine, which needs them, not to the operator.
- Never edit the bundle, the refine snapshot or the task copies to make a
  check pass. Never move or recreate the `swepro-prereg` tag.
- Never use the horizon or refine skills, or `/loop`, to run or monitor the
  study. Refine runs only inside its container.
- No new API keys or accounts. No push without the user's decision.

## Write-up

`docs/evaluations/swepro-refine/report.md`, with the same shape as the
EvoCode report: question, setup, primary result, per-task table, secondary
outcomes, practice summary, what refine learned (a summary of the bundle),
validity, deviations, limits, credit and license. The license and citation
for SWE-bench Pro are checked at the pinned commit before the report is
published.

## Risks

- **Ceiling or floor.** Sonnet 5.5 may solve almost all or almost none of
  the ansible tasks. The go/no-go gate catches this before the test phase.
- **Usage.** Token use per run is unknown; estimates range from 20% to 60%
  of a week. The gate's projection lets the user stop first.
- **Rosetta.** Tests may be slow or flaky under emulation. Local validation
  catches broken tasks; reruns cover infrastructure errors only.
- **Disk.** Images are 0.7–3.5 GB compressed. Pull per task and remove after.
  The Colima disk is 150 GB.
- **Uncommitted refine code.** The snapshot is pinned by hash, but the code
  it came from is not in git. Committing `main`'s pending work first would
  make it reproducible from history.
- **Extra context.** Plain vs refined cannot separate good lessons from any
  added notes; a placebo arm would.
- **Public fixes.** The model may have seen some ansible fixes. Both arms
  share this.
- **Refine writes nothing.** A valid outcome; the test phase then compares
  plain against near-plain and the report says so.

## Amendment 1 (2026-10-14): a harder repository

The ansible study stopped at the gate: 29 of 30 practice runs passed
(`docs/evaluations/swepro-refine/report.md`). The user asked to try a
harder repository. Everything above applies unchanged to the new study,
except the following.

- **Candidates.** Only repositories with at least 70 tasks can supply 30
  practice and 40 test tasks: openlibrary (82), flipt (78) and qutebrowser
  (73). Qutebrowser drops below 70 once its pilot tasks are set aside, so the
  candidates are openlibrary and flipt.
- **Pilot.** For each candidate, `random.Random(20261017)` draws 8 tasks from
  its sorted task list. These are pinned in `config.py`. Plain Claude Code
  (same model, effort, build and network policy) runs each task once, and
  each task is validated with oracle and nop. Only rewards are read. A task
  counts if it is valid and the agent run had no infrastructure failure.
- **Choice.** Among candidates with at least 4 counted tasks and a pass rate
  strictly between 4/30 and 26/30, choose the one closest to 50%; a tie goes
  to openlibrary. If neither qualifies, stop and bring it to the user.
- **Exclusion.** The chosen repository's 8 pilot tasks are excluded from its
  study pool, so no test task has been run before the freeze.
- **Separation.** `SWEPRO_STUDY=<repo>` selects the task prefix, the
  exclusions, the run directory `~/swepro-runs-<repo>`, the docs directory
  `docs/evaluations/swepro-refine-<repo>`, and the freeze tag
  `swepro-prereg-<repo>`. The refine prompt names the repository. Ansible
  keeps its original names.

## Amendment 2 (2026-10-14): Haiku on ansible

The Sonnet pilot was stopped after 6 runs:
- openlibrary passed 4 of 4;
- on flipt, Scale's reference fix scored 0 on both tasks run, which points to a local environment problem.

The user chose Haiku instead. The `ansible-haiku` study is the ansible study above with
`anthropic/claude-haiku-5-5` for both arms and every refine session. Everything else carries over:
- the same pool, validation records and committed split, since validation does not depend on the model;
- fresh notes;
- its own run directory, docs directory and freeze tag.

A Haiku pilot runs plain Claude Code once on 8 tasks drawn with `random.Random(20261017)` from the
committed practice list, under the Amendment 1 choice rule with this study as the only candidate.
Practice tasks are never scored, so nothing is excluded. If the pilot rate is outside (4/30, 26/30),
stop and bring it to the user.

## Amendment 3 (2026-10-15): a minimal agent with DeepSeek (plan B)

Every Claude Code pilot sat at the gate's ceiling:
- Haiku on ansible passed practice 30 of 30 (stop_high);
- Haiku passed the openlibrary pilot 8 of 8;
- DeepSeek V4 Flash inside Claude Code passed it 8 of 8.

The pipeline was checked before blaming the tasks:
- an empty patch scores 0, and the reference fix scores 1;
- the task images hold no commits after the base, no fix object, no `/tests` and no `/solution`;
- 534 practice tool calls show no route to the answer;
- 7 passing patches still pass on pristine images with every test-file change removed.

The user chose plan B: keep the study, swap the agent under test for a minimal one.

The `openlibrary-mini` study is the openlibrary study with these changes:
- **Agent under test.** mini-swe-agent 2.4.6 (a single bash tool and one prompt), driven by DeepSeek
  V4 Flash (`deepseek/deepseek-v4-flash` through LiteLLM) at `api.deepseek.com`, the only host open in
  the agent phase. It is capped at 100 steps, with no cost limit. Its Python 3.12.14
  (python-build-standalone 20260929, checksum-verified) and packages (resolved with
  `--exclude-newer 2026-10-01`) are pre-built into the tools directory, so the offline agent phase
  installs nothing.
- **Notes.** The only note layer the agent can read is rho, the notes file. In the refined arm its
  text is appended to mini-swe-agent's system prompt under "Notes from earlier tasks in this
  repository", inside a Jinja raw block. The plain arm gets mini-swe-agent's default prompt. Memory,
  skills and subagents have no channel into this agent.
- **Refine.** It is still Claude Code running the frozen refine skill, now on DeepSeek V4 Flash through
  `api.deepseek.com/anthropic`. Its inputs are the task statement, mini-swe-agent's own trajectory
  (as `transcript.json`) and the result line. Its prompt says that only CLAUDE.md reaches the agent,
  and that edits to any other layer are lost. The practice records keep counting edits by layer, so
  any lost edits show in the report.
- **Key.** The DeepSeek key is read from Keychain service `swepro-deepseek-key`. Neither the agent
  nor refine ever receives the Claude subscription token.
- **Pilot.** Plain mini-swe-agent runs once on the 8 pinned openlibrary pilot tasks, which this study
  excludes as before, under the Amendment 1 choice rule with this study as the only candidate. If
  the rate is outside (4/30, 26/30), stop and bring it to the user.

Everything else carries over unchanged:
- the split procedure and seeds, practice length, gate, freeze, test design and scoring;
- the operator rules;
- its own run directory, docs directory and freeze tag.

The claim narrows to: do notes that refine writes during practice help a minimal agent solve more
unseen tasks in the same repository?

## Amendment 4 (2026-10-15): plan B with a 20-step cap

Plan B's pilot passed 8 of 8 at 100 steps; its runs took 22 to 78 steps, none hitting the cap. The
user asked for the cap to be cut to 20 steps and for web search to stay off.

- **Study.** `openlibrary-mini20` is `openlibrary-mini` with `step_limit` 20 and nothing else changed:
  same pool, pilot tasks, agent, model, provider, refine setup, rules and gate. It has its own run
  directory, docs directory and freeze tag (`swepro-prereg-openlibrary-mini20`).
- **Capped runs.** A run stopped at the cap is graded on the patch it left, like any other run; it is
  the model's outcome, not an infrastructure failure, and is never rerun.
- **Web search.** Already off and unchanged. Every Claude Code session (refine) is started with
  `--disallowedTools WebSearch,WebFetch`, and mini-swe-agent has only a bash tool in a container
  whose network is closed except to `api.deepseek.com`.
- **Pilot.** The same 8 tasks, once each, plain arm. Inside (4/30, 26/30): continue to split and
  practice under the existing rules. Outside: stop and bring it to the user.
