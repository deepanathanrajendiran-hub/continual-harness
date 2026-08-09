---
name: refine
description: Use after a substantial task, or when the user types /refine - reads what actually happened this session and proposes the smallest edit to the harness layer (memory, skills, subagents, CLAUDE.md) that would make the next session go better. Proposes diffs; never writes without approval.
---

# Refine: the continual harness

The harness is `H = (rho, G, K, M)` — prompt, skills, subagents, memory.
Every one is editable. This skill closes the loop that otherwise never
closes: nothing in a normal session ever writes back to it.

Rollback bookkeeping runs through one module at
`.claude/harness/bin/refine_log.py` (`record`, `commit_entry`, `undo`,
plus the `NothingToUndo` / `CorruptEntry` / `UndoConflict` exceptions).
The skill calls it; it does not reimplement changelog formatting, entry
storage, or the undo staleness check inline. If a step below can't be
done by calling it, stop and say so rather than inventing an inline
substitute.

## Setup

```bash
cd "/Users/deeps/Documents/NEW STUFF/fun " && python3 -c "
import sys; sys.path.insert(0, '.claude/harness/bin')
import refine_log
print('module loads OK')
"
```

Quote the path — the project directory name ends in a space.

## Step 1 — Harvest turning points

Trajectories are mostly noise: file reads, tool output, exploration that
led nowhere. Scan for **turning points only**:

- A direct user correction ("no, don't do X", "use Y instead").
- **A command that failed, then succeeded after a fix.** The highest-signal
  class — a reproducible gotcha whose fix is already proven.
- A procedure re-derived or repeated for the third time.
- A research or exploration shape run repeatedly with the same structure.
- A durable fact about the user or project not derivable from the repo.

If a candidate cannot be anchored to one of those moments, it is not a
candidate. This is what stops refine inventing plausible-sounding patterns
that reflect nothing.

## Step 2 — Route to the narrowest layer

| Evidence | Layer | Target |
|---|---|---|
| Durable fact about user or project | M | `~/.claude/projects/<project-key>/memory/` |
| Command failed then fixed | M | `~/.claude/projects/<project-key>/memory/` |
| Procedure repeated 3x | G | `.claude/skills/<name>/SKILL.md` |
| Repeated exploration shape | K | `.claude/agents/<name>.md` |
| Correction that must apply *everywhere* | rho | `./CLAUDE.md` |

`<project-key>` — see "Memory write contract" below for the literal
derivation rule and a worked example for this project. Do not guess it
and do not substitute a repo-local path like `.claude/memory/` — nothing
in Claude Code reads memory from there, so a memory written to the wrong
path is invisible forever while still looking, to a user who only sees
the filename in the approval prompt (Step 5, G4), exactly like a correct
write.

**Narrowest layer wins.** CLAUDE.md is loaded into every session, so it is
the most expensive real estate in the system — last resort, never the
default. A fact belongs in memory unless it must fire unconditionally.

If the routed target file doesn't exist yet — this project currently has
no root `CLAUDE.md`, for example — that's not a blocker. Creating it is
part of the approved edit; disclose that in the proposal (Step 5) rather
than treating a missing file as an error.

## Step 3 — Dedupe

Before proposing a new entry, check the target layer for one already
covering it:

- **M:** read `MEMORY.md` in the project memory directory (one line per
  memory), and check existing files' `name` / `description` frontmatter
  for the same fact.
- **G:** read the skill files already under `.claude/skills/`.
- **K:** read the subagent files already under `.claude/agents/`.
- **rho:** read `./CLAUDE.md`.

Update the matching entry rather than creating a near-duplicate. Two
memories saying almost the same thing are worse than one, because
retrieval surfaces the weaker one half the time.

## Step 4 — Rank and cap

**At most 3 proposals per invocation.** If you found more, rank by how
often the situation will recur and drop the tail. An unbounded
self-editor bloats the harness until it is worse than no harness.

The cap is scoped to the **trajectory being harvested, not the tool
call.** If this trajectory already produced 3 proposals in an earlier
`/refine` run this session, re-invoking `/refine` on the same trajectory
to squeeze out 3 more is the exact bloat the cap exists to prevent —
don't. A fresh cap of 3 only opens up for a genuinely new trajectory
(new turns since the last `/refine`, not the same ground re-scanned).

## Step 5 — Propose, do not write

For each proposal show: the target file (full path), the exact text to
be written, and the trajectory moment justifying it — quote it, don't
paraphrase it away. Then stop and wait for the user's response. Nothing
in Steps 1–5 touches disk.

## Step 6 — On approval, write and log

For each approved proposal, in this order:

```python
import sys; sys.path.insert(0, '.claude/harness/bin')
import refine_log

entry = refine_log.record(layer, target, rationale, evidence)  # BEFORE the edit
# ... apply the edit to `target` now (Write/Edit tool) ...
refine_log.commit_entry(entry["id"])                            # AFTER it succeeds
```

`record()` first, always. It snapshots whatever currently exists at
`target` (or notes that it doesn't exist yet), and that snapshot is the
only thing that makes `/refine --undo` possible later. `commit_entry()`
must come strictly after the edit has actually landed: it re-reads
`target` and stores its sha256, which is what a later `undo()` uses to
detect whether something else touched the file since. Calling
`commit_entry()` before the edit lands, or skipping `record()` entirely,
breaks rollback for that entry.

If the edit fails partway through — a write error, a tool failure — do
not call `commit_entry()`. An entry that was recorded but never committed
represents a failed edit and `undo()` ignores it entirely; it is not
left in a half-applied state that needs cleanup.

`layer` is one of `rho`, `G`, `K`, `M` — the same codes as the CHANGELOG
legend. `target` is the absolute path being written. `rationale` is one
sentence. `evidence` is the trajectory moment from Step 5, quoted or
close to it — this is what makes reviewing `CHANGELOG.md` later actually
mean something.

`commit_entry()` appends the changelog line itself
(`.claude/harness/CHANGELOG.md`) — never hand-edit that file; every line
in it should trace back to a `record()`/`commit_entry()` or `undo()`
call.

## Memory write contract

Do not invent a format. Claude Code already has one, and a parallel
scheme would be invisible to recall:

```markdown
---
name: <kebab-case-slug>
description: "<one line — recall matches against this, not the filename>"
metadata:
  type: feedback   # or: project | user | reference
---

<1-3 sentences: the fact or lesson itself.>

**Why:** <one sentence — why this matters for a future session>

**How to apply:** <one sentence — the concrete action a future session
should take because of this>

Related: [[other-slug]]
```

- **Location:** `~/.claude/projects/<project-key>/memory/` — the same
  directory Claude Code already reads at session start. `<project-key>`
  is the project's absolute path with every `/` and every space replaced
  by `-`. Worked example, verified against what's actually on disk for
  *this* project: `/Users/deeps/Documents/NEW STUFF/fun ` (note the
  trailing space in the directory name) becomes
  `-Users-deeps-Documents-NEW-STUFF-fun-`, so the memory directory is
  `~/.claude/projects/-Users-deeps-Documents-NEW-STUFF-fun-/memory/`.
  `MEMORY.md` (the Index, below) lives in that same directory, not
  anywhere else. Do not invent a new folder, and do not use a repo-local
  path such as `.claude/memory/` — recall does not read from there.
- **Filename:** `<slug>.md`, where `<slug>` is exactly the `name` field,
  kebab-case. Never numbered or category-prefixed
  (`USER_PREF_001.md`, `feedback-2026-08-09.md`) — retrieval keys off
  `description`, not the filename, so a numbered or dated filename adds
  nothing and makes the dedupe check in Step 3 harder, not easier.
- **Frontmatter:** `name`, `description`, and `metadata.type` — exactly
  one of `user`, `feedback`, `project`, `reference`. Pick the narrowest:
  `feedback` for a lesson drawn from this session's corrections,
  `project` for a durable fact about the project or a decision made in
  it, `user` for a durable fact about the person, `reference` for
  material to look up rather than a lesson to act on.
- **Body:** `**Why:**` and `**How to apply:**` are required for
  `feedback` and `project` entries — they turn a fact into an
  instruction a future session can actually execute on. Link related
  memories with `[[slug]]` (no `.md`, no path).
- **Index:** after writing the file, append exactly **one** line to
  `MEMORY.md` in the same directory: `- [<Title>](<slug>.md) — <hook>`.
  Never put memory content in the index — it's a table of contents, not
  a copy.

## Guardrails

- **G1 — Evidence required.** Every proposal cites a concrete trajectory
  moment — a quoted correction, a specific command and its failure/fix,
  the Nth repetition of a named procedure. No speculative or anticipatory
  edits ("this might help next time").
- **G2 — Cap of 3.** At most 3 proposals per trajectory, not per tool
  call — see Step 4. Re-invoking `/refine` on the same trajectory to
  bypass the cap is not a loophole, it's the exact bloat the cap exists
  to prevent. Forces ranking instead of dumping every candidate that
  came up.
- **G3 — No self-exemption.** `refine` may never edit
  `.claude/skills/refine/SKILL.md` (this file) or anything under
  `.claude/harness/bin/*.py` — `refine_log.py` and its siblings are the
  code that *enforces* the guardrails (`CorruptEntry`, `UndoConflict`,
  atomic writes); a proposal to edit them is a proposal to edit the
  enforcement, not just the instructions, and is off-limits the same
  way. It may never propose anything that weakens verification, testing,
  or approval requirements: skipping a test, loosening a gate, removing
  a guardrail from another skill. And it may never propose anything —
  in memory, in `CLAUDE.md`, in another skill, anywhere — that softens
  **G1's evidence bar or G2's cap of 3**, e.g. "relax quoting for small
  edits" or "raise refine's proposal cap." The guardrails are not a
  subject refine gets to have opinions about; G1–G3 apply to proposals
  *about* G1–G3 exactly as they apply to everything else. An agent that
  learns "skip the tests" is optimizing the harness *against* its user,
  not for it. Prime Intellect's Prime Agent demonstrated exactly this
  failure mode in its own Factorio case study: the same refinement loop
  that built legitimate skills turned to building efficient cheating
  skills once cheating scored better on the metric being optimized —
  loosening G1 or G2 from the inside is that same pattern in miniature,
  the loop optimizing its own constraints away rather than optimizing the
  work. If a candidate would make a future session less likely to get
  caught doing something wrong, or less constrained than this session
  is, it fails G3 regardless of how well-evidenced it is — drop it; do
  not propose a softened version instead.
- **G4 — Approval gate.** No write without explicit user approval, per
  proposal. An "approve all" for a batch is fine if the user says it;
  silence, or the conversation moving on, is not approval.

## Anti-patterns

- Recording what the repo already states — file structure, git history,
  existing CLAUDE.md content. If it's already there, writing it again is
  noise, not a lesson.
- Recording conversation-local trivia with no future bearing (a filename
  chosen for one file, a one-off typo fix).
- Writing a skill where a CLAUDE.md line would suffice, or a CLAUDE.md
  line where a memory would suffice. Re-check the routing table (Step 2)
  before defaulting upward.
- Proposing something when the session taught nothing. Silence is a
  valid result — say so and stop; do not manufacture a proposal just to
  have something to show.

## Errors at a glance

| Call | Exception | Meaning | Action |
|---|---|---|---|
| `refine_log.undo` | `NothingToUndo` | changelog has no committed, un-reverted entry | report it; there is nothing to revert |
| `refine_log.undo` | `CorruptEntry` | an undo-log entry file under `.claude/harness/undo/` is unreadable or not valid JSON | stop. Report the exact file path(s) named in the exception to the user. Do not retry, delete the file, skip past it, or fall back to reverting a different entry on your own initiative — guessing past damaged history risks reverting the wrong edit. |
| `refine_log.undo` | `UndoConflict` | the target's current sha256 doesn't match what was recorded when its entry was committed — something changed the target after the approved edit landed | stop. Show the user the target path and that it changed since. Only call `undo(force=True)` after the user explicitly approves discarding that later change — silently forcing would delete an edit nobody agreed to lose. |

## `/refine --undo`

```python
import sys; sys.path.insert(0, '.claude/harness/bin')
import refine_log

try:
    entry = refine_log.undo()
except refine_log.NothingToUndo as e:
    print(f"nothing to undo: {e}")
    # report and stop.
except refine_log.CorruptEntry as e:
    print(f"cannot undo, damaged history: {e}")
    # report the file(s) named in `e` to the user and stop. See
    # "Errors at a glance" — never retry or guess past this.
except refine_log.UndoConflict as e:
    print(f"undo conflict: {e}")
    # present this to the user; do not proceed to force=True without
    # their explicit approval.
else:
    print(f"reverted entry {entry['id']} on {entry['target']}")
```

Reverts the single most recent committed, un-reverted entry and appends a
`REVERTED` line to `CHANGELOG.md`. There is no "undo entry #7
specifically" call — it always targets the top of the stack, so calling
it again walks back the next most recent entry.

Only after the user has seen a `UndoConflict` and explicitly approved
discarding the later change:

```python
entry = refine_log.undo(force=True)
```
