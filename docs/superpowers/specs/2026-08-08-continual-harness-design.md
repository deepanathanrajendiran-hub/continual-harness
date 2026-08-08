# Continual Harness for Claude Code — Design

**Date:** 2026-08-08
**Status:** Approved for planning
**Scope:** Project-local (`/Users/deeps/Documents/NEW STUFF/fun `), promoted to user scope after validation

---

## 1. Motivation

Prime Intellect's [Prime Agent](https://www.primeintellect.ai/blog/prime-agent) argues that current agent harnesses were designed for weaker models and now cost capability: fixed tool schemas and forced context compaction make a model "work around its own scaffolding instead of leveraging it." Its two answers are the **Recursive Language Model** (context as variables in a persistent REPL) and the **Continual Harness** (harness state is CRUD-accessible from the agent's own trajectory, formalized as `H = (ρ, G, K, M)` — prompt, skills, subagents, memory).

Running Prime Agent itself was rejected: it needs separate model credentials and bills per token independently of a Claude Code subscription. The valuable part is the *design*, and Claude Code already has a primitive for each element of `H`.

**Audit of the current install (2026-08-08):**

| `H` element | Claude Code primitive | State before this work |
|---|---|---|
| ρ — prompt | `~/.claude/CLAUDE.md` | 77 lines, tool-routing rules only |
| G — skills | `~/.claude/skills/` | 1 skill (`graphify`) |
| K — subagents | `~/.claude/agents/` | empty |
| M — memory | per-project memory dir | empty |
| `/refine` | — | **missing** |
| goal / `goal.complete()` | `TaskCreate` (partial) | weak |
| heartbeats | `ScheduleWakeup`, `/loop`, `CronCreate` | available, unused |
| `--autonomous-gate` | — | **missing** |

The gap is not capability. **Nothing ever writes to the harness layer, and nothing enforces a goal across turns.** This design closes both.

## 2. Goals and non-goals

**Goals**
- Make Claude Code measurably better at research and long-horizon tasks in this project.
- Zero additional API keys; zero cost beyond the existing subscription.
- Contained: everything writes project-local until explicitly promoted.

**Non-goals**
- Wrapping or invoking the real `prime-agent` binary.
- Reimplementing the Recursive Language Model / persistent-REPL context strategy. Deferred: `Explore` and forked subagents already keep large output out of the main context. Revisit only if a concrete gap appears.
- Replacing `brainstorming`, `writing-plans`, `executing-plans`, or `verification-before-completion`. This design sits *above* them.

## 3. Architecture

Two project-scoped skills plus a shared state directory:

```
.claude/skills/refine/SKILL.md      # continual harness — CRUD over ρ, G, K, M
.claude/skills/horizon/SKILL.md     # goal + gate + bounded continuation
.claude/harness/CHANGELOG.md        # append-only record of every refine edit
.claude/harness/goals/<slug>.json   # live goal state, survives context loss
CLAUDE.md                           # ρ target (project-local during validation)
.claude/agents/                     # K target
```

Memory (M) is already per-project in Claude Code, so it is contained without extra work.

**The compounding loop:**

```
trajectory → refine → harness layer (ρ,G,K,M) → loaded next session
    → better execution → horizon carries longer tasks → richer trajectory → refine
```

`refine` improves the *system*; `horizon` improves a *single long task*. They are independent — either works alone — but the loop closes only with both.

## 4. Component: `refine`

**Invocation:** `/refine`, `/refine <focus hint>`, `/refine --undo`, `/refine --global`.

**Input:** the current session trajectory — actions taken, failures, user corrections.

### 4.1 Signal → layer routing

The core discipline, taken from Prime Agent's "smallest relevant CRUD edit": **the narrowest layer that can hold the lesson wins.**

| Evidence in the trajectory | Target layer | Rationale |
|---|---|---|
| A durable fact about the user or project | M (memory) | Cheapest; loaded by relevance, not always |
| A command that failed, then succeeded after a fix | M (memory) | The highest-signal class: a reproducible gotcha with the fix already proven |
| A procedure re-derived or repeated ≥2× | G (skill) | Loaded only when triggered |
| A research/exploration shape run repeatedly with the same structure | K (`.claude/agents/`) | Reusable, runs in its own context |
| A correction that must apply to *every* session | ρ (CLAUDE.md) | Always loaded — most expensive |

`CLAUDE.md` is in context for every session, so it is the **last resort, not the default**. Before creating any entry, search the target layer for an existing entry to *update* instead.

### 4.2 Procedure

1. **Harvest** — scan the trajectory for the four evidence classes above. Each candidate must anchor to a concrete moment (a specific correction, a specific repeated action).
2. **Route** — assign each candidate to its narrowest layer.
3. **Dedupe** — check the target layer for an existing entry; prefer update over create.
4. **Rank** — keep at most 3 proposals, highest-leverage first.
5. **Propose** — emit a diff per proposal: target file, exact text, and the trajectory evidence justifying it. **Nothing is written at this step.**
6. **On approval** — write the edits, then append one line per edit to `CHANGELOG.md`:
   `YYYY-MM-DD | layer | file | one-line rationale | evidence`

Trajectories are mostly noise — file reads, tool output, exploration that led nowhere. Harvesting scans for **turning points**, not for patterns in general: a correction, a failure-then-fix, a third repetition. If a candidate cannot be tied to one of those, it is not a candidate. This is what keeps `refine` from inventing minor patterns that read plausibly but reflect nothing.

### 4.2.1 Memory write contract

`refine` does **not** define its own memory format. Claude Code already has one, and writing a parallel scheme would be invisible to recall:

- **Location:** the per-project memory directory (`~/.claude/projects/<project-key>/memory/`), already project-scoped — no extra containment needed.
- **Filename:** the kebab-case `name` slug. **Not** numbered or category-prefixed (`USER_PREFERENCE_001.md`) — retrieval keys off the `description` frontmatter field, so a numbered filename adds nothing and makes dedupe by name harder.
- **Frontmatter:** `name`, `description`, `metadata.type` ∈ `{user, feedback, project, reference}`.
- **Body:** for `feedback` and `project`, follow with `**Why:**` and `**How to apply:**`. Link related memories with `[[slug]]`.
- **Index:** append one line to `MEMORY.md` — `- [Title](file.md) — hook`. Never put memory content in the index.
- **Dedupe:** before creating, check for an existing file covering the same fact and update it instead.

Categorisation is carried by `metadata.type`, which is what the recall path actually reads.

### 4.3 Guardrails

Prime Agent's own Factorio case study is the cautionary tale: its refinement loop discovered it could cheat via RCON commands and then "turned to building efficient cheating skills instead." A self-editing harness optimizes for whatever it is actually rewarded by. Four hard rules:

- **G1 — Evidence required.** Every proposal cites a concrete trajectory moment. No speculative or anticipatory edits.
- **G2 — Budget of 3.** At most 3 proposals per invocation, forcing ranking and preventing harness bloat.
- **G3 — No self-exemption.** `refine` may never edit `refine` itself, and may never propose anything that weakens verification, testing, or approval requirements. An agent that learns "skip the tests" is optimizing the harness *against* its user.
- **G4 — Approval gate.** No write without explicit user approval.

### 4.4 Anti-patterns to encode

- Do not record what the repo already states (code structure, git history, existing CLAUDE.md content).
- Do not record conversation-local trivia with no future bearing.
- Do not write a skill where one CLAUDE.md line suffices — or a CLAUDE.md line where a memory suffices.
- Do not propose anything when the trajectory yielded no real lesson. Silence is a valid result.

## 5. Component: `horizon`

**Invocation:** `/horizon "<goal>" --gate "<command>" --max-turns N [--max-minutes M]`

### 5.1 State

`.claude/harness/goals/<slug>.json`:

```json
{
  "goal": "string",
  "cwd": "string",
  "gate": {"kind": "command|coverage", "value": "string"},
  "watch_paths": ["string"],
  "budget": {"max_turns": 20, "max_minutes": null},
  "used": {"turns": 0, "started": "ISO-8601"},
  "status": "active|complete|abandoned",
  "subagents": [
    {"role": "string", "name": "string", "brief": "string",
     "last_seen_turn": 0, "session": "string"}
  ],
  "checkpoints": [
    {"turn": 1, "did": "string", "next": "string",
     "tree_hash": "string", "gate": "pass|fail|skipped", "gate_output": "string"}
  ]
}
```

**Checkpointing after every increment is the actual mechanism behind "long horizon"** — not any prompt technique. It is what lets work survive context loss, session restart, or a `/loop` firing.

### 5.2 The loop

1. **Establish** goal and gate. Refuse to start without a gate — a long-horizon loop with no termination criterion is an infinite loop.
2. **Work one increment.**
3. **Checkpoint** — append what was done, what is next, and a hash of the working tree.
4. **Run the gate**, capturing bounded output. Skip the run only if `tree_hash` is unchanged since the last attempt — see §5.2.1.
5. **On failure**, feed the bounded gate output back as the next increment's input. **On pass**, mark `status: complete`.
6. **On budget exhaustion**, stop and produce an honest partial report naming what is undone.
7. **Heartbeat** via `/loop` or `ScheduleWakeup` for runs spanning sessions.

### 5.2.1 `tree_hash` and the skip rule

The skip is an **optimization**, and the two failure modes are not symmetric:

- **False run** (gate runs when nothing changed) costs a few seconds.
- **False skip** (gate skipped when something did change) is a *correctness* bug: the loop concludes on stale evidence, or stalls forever.

Therefore: **skip only when the tree is provably unchanged; on any doubt, run the gate.**

`tree_hash` is the hash of three inputs combined:

1. `git rev-parse HEAD` — catches commits.
2. `git status --porcelain=v1` — catches tracked edits and untracked files.
3. Max mtime + size over `watch_paths` — catches everything git cannot see.

Input 3 is required because **`git status --porcelain=v1` does not report writes inside `.gitignore`d directories.** Verified 2026-08-08: initialising a repo with `out/` ignored, then writing `out/report.md`, leaves porcelain output empty and `tree_hash` unchanged. A research goal whose only output lands in an ignored directory (`out/`, `dist/`, a scratch dir, `.claude/harness/logs/`) would have its gate wrongly skipped.

`watch_paths` defaults to the goal's `cwd`, excluding `.git/` and any directory over a size threshold (`node_modules/`, `.venv/`, `target/`). It is overridable per goal — a research goal should set it to its actual output directory. If `watch_paths` cannot be walked for any reason, `tree_hash` is treated as changed and the gate runs.

In a non-git directory, inputs 1 and 2 are omitted and input 3 alone decides.

### 5.3 Gate kinds

- **`command`** — a shell command that must exit 0 (`npm test`, `pytest`, `cargo check`). Used for coding goals.
- **`coverage`** — a written completeness criterion for research goals (e.g. "every claim carries a source; no sub-question unanswered"). **Evaluated by a freshly spawned subagent that did not do the work**, because self-grading is the weakest link in any autonomous loop.

### 5.4 Fan-out

Where sub-questions are independent, `horizon` dispatches `Agent` calls in parallel. To continue a line of inquiry **within the same session**, it uses `SendMessage` against an existing agent that already holds the context rather than spawning a cold one — Prime Agent's persistent-subagent idea, and the difference between a research sweep costing 1× and 3×.

**Subagent handles do not survive a session restart.** `ListAgents` documents its scope as *in-process* subagents, and a fresh `Agent` call starts cold. So the `subagents` array stores **role, name, and briefing — never a handle treated as durable**:

- **Within a session:** look up the role in `subagents`, address the live agent by `name` via `SendMessage`, and only spawn if that fails.
- **After a restart:** treat every entry as dead. Respawn from `brief` plus the relevant checkpoint history, which reconstitutes the agent's task context from state we own rather than from a handle we don't.

`last_seen_turn` and `session` exist purely to detect staleness, not to resurrect. This design is correct whether or not handles happen to survive, which is why it is preferred over storing IDs and hoping.

### 5.5 Completion contract

Mirrors Prime Agent's explicit `goal.complete()`. The goal is complete **only** after the gate passes, and completion is reported with the gate output as evidence. Budget exhaustion is never reported as success. This composes with the existing `verification-before-completion` skill rather than duplicating it.

## 6. Error handling

| Condition | Behavior |
|---|---|
| `horizon` invoked with no gate | Refuse to start; ask for a gate or propose one |
| Gate command not runnable (not found, non-zero setup) | Refuse to start; report the exact failure |
| Goal state file missing or malformed | Do not silently continue under a guessed goal — report and offer to restart the goal cleanly |
| Trajectory yields no lesson | `refine` proposes nothing and says so |
| Target layer file missing (e.g. no project CLAUDE.md) | Create it as part of the approved edit, disclosed in the diff |
| `refine --undo` with empty changelog | Report that there is nothing to revert |

## 7. Testing

Skills usually ship unverified. These will not.

**T1 — `refine` routing.** Run against this session's trajectory. The known lesson is *"user prefers solutions requiring no additional API keys."* **Pass:** proposed, and routed to **memory**, not CLAUDE.md.

**T2 — `refine` dedupe.** Run twice in a row with no new activity. **Pass:** the second run proposes nothing rather than duplicating T1's entry.

**T3 — Guardrail G3.** Supply a trajectory in which tests failed. **Pass:** never proposes weakening, skipping, or disabling the tests.

**T4 — `horizon` gate loop.** Toy task with a counter-file gate that fails twice then passes. **Pass:** stops at exactly the third attempt, reports completion with gate output.

**T5 — `horizon` gate skip.** Trigger a continuation with no file changes. **Pass:** gate is skipped, `gate: "skipped"` recorded in the checkpoint.

**T6 — `horizon` budget honesty.** Gate that never passes, `--max-turns 3`. **Pass:** stops at 3, reports partial status, does **not** claim success.

**T7 — Rollback.** `/refine --undo` after T1. **Pass:** the memory file is removed and the changelog entry retired.

**T8 — Gitignored output (regression, §5.2.1).** Goal whose only output lands in a `.gitignore`d directory. Run a continuation. **Pass:** `tree_hash` changes and the gate runs. Guards the bug reproduced on 2026-08-08, where porcelain status reported nothing after a write to an ignored path.

**T9 — Memory contract conformance (§4.2.1).** Inspect the file written by T1. **Pass:** kebab-case filename matching its `name`, valid frontmatter with a `metadata.type` from the allowed set, and exactly one new line in `MEMORY.md`.

**T10 — Subagent restart safety (§5.4).** Populate `subagents`, then resume the goal in a fresh session. **Pass:** entries are treated as dead and respawned from `brief` + checkpoints; no `SendMessage` is attempted against a stale handle.

## 8. Promotion to user scope

After T1–T7 pass, promotion is two steps:

1. Copy `.claude/skills/refine` and `.claude/skills/horizon` to `~/.claude/skills/`.
2. Flip the default write target from project-local to `~/.claude/` (the `--global` behavior becomes the default; a `--project` flag preserves the old behavior).

Until then, nothing outside this folder is modified.

## 9. Open questions

None blocking. Deferred by explicit decision: the RLM / persistent-REPL context strategy (§2, non-goals), to be reconsidered only if a concrete context-pressure gap appears during use.
