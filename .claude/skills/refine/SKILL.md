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

## Scope

Default targets are project-local: `./CLAUDE.md`, `.claude/skills/`,
`.claude/agents/`, and the project memory dir.

`/refine --global` retargets to `~/.claude/CLAUDE.md`, `~/.claude/skills/`,
and `~/.claude/agents/`. Use it only for lessons that genuinely apply to
every project — a project-specific gotcha written globally is noise in
every future session.

`--global` changes *where* a proposal writes, not the process it writes
through: Steps 5-6's propose-then-approve flow and G4's approval gate apply
to every global write exactly as they apply to a project-local one — no
flag-conditional shortcut exists anywhere in this skill.

Two things `--global` does **not** change:

- **Memory (M) routing is unaffected.** Step 2's target for M is already
  `~/.claude/projects/<project-key>/memory/` — under the user's home
  directory, keyed by *this* project's path, not a repo-local folder.
  There is no separate global memory store to retarget to (confirmed: no
  `~/.claude/memory/` exists), so `--global` has nothing to do here. A
  memory-routed proposal always writes to the current project's memory
  dir regardless of the flag; if a lesson is durable enough to want
  writing everywhere, route it to rho or G instead (Step 2), not to M.
- **Changelog/undo bookkeeping stays project-local.** `record()` and
  `commit_entry()` always write to *this* project's
  `.claude/harness/CHANGELOG.md` and `.claude/harness/undo/`, even for a
  `--global` proposal whose edit target is under `~/.claude/`. There is
  no `~/.claude/harness/` — promoting the bookkeeping module itself is
  spec §8's job, not this flag's, and until that promotion happens the
  only rollback ledger that exists is this one. `/refine --undo` after a
  `--global` write still reverts it, from this same project's log.

`--global` retargets *where a proposal writes*, not *which file governs
the edit itself*. G3's no-self-exemption rule still applies to the global
copy once one exists: after promotion, `~/.claude/skills/refine/SKILL.md`,
`~/.claude/skills/horizon/SKILL.md`, and `~/.claude/harness/bin/*.py` (if
and when they exist) are exactly as off-limits to a self-proposal as
their project-local counterparts are today. A flag that changes the
write path does not change what refine is allowed to propose about
itself.

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

**At most 3 proposals per trajectory being harvested — never per tool
call, and never resettable by re-invoking `/refine`.** An unbounded
self-editor degrades the harness until it is worse than no harness, and
a cap the editor can lift at will by calling itself again is not a cap.

**Before proposing anything, check the persisted floor, not your own
recollection.** Read `.claude/harness/CHANGELOG.md` and count the
non-`REVERTED` entries dated **today in UTC — never local time.**
`commit_entry()` stamps `entry["committed_at"][:10]` from
`datetime.now(timezone.utc)` at commit time — not `record()`'s earlier
snapshot time — so every date already in the file is UTC and reflects
when the edit actually landed, not when it was queued.
Filtering by local "today" instead can silently *undercount*: for a user
east of UTC, entries committed in their early morning carry *yesterday's*
UTC date and would be skipped by a local-date filter, and the agent
would conclude budget remains when the cap is already reached. Every
other ambiguity in this guardrail resolves toward stopping sooner — this
is the one place that must not resolve the other way.

```python
import sys
from datetime import datetime, timezone
sys.path.insert(0, '.claude/harness/bin')
import refine_log

today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
log_path = refine_log.paths.changelog()
count = 0
if log_path.exists():
    for line in log_path.read_text().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 5:
            continue  # header or blank line, not a dated entry
        date, layer = parts[0], parts[1]
        if not date[:4].isdigit():
            continue  # header/format-spec line (e.g. the `YYYY-MM-DD | ...`
                       # legend), not a real dated entry
        if date == today_utc and layer != "REVERTED":
            count += 1
print(f"CHANGELOG pre-flight: {count} edits applied today (cap 3)")
```

Split each line on `|` and read the layer field **by position**
(`parts[1]`) — never by searching the whole line for the substring
`"REVERTED"`. A target path, rationale, or evidence string can
legitimately contain that word (a proposal *about* the undo mechanism
itself, for instance), and a substring search would then misclassify a
normal entry as reverted and undercount — the same direction of error as
the UTC bug above.

Guard the read with `log_path.exists()` first. `commit_entry()` creates
`CHANGELOG.md` lazily (Step 6), so a harness that has never applied an
edit — a fresh project, or the state right after Task 7's global
promotion — has no file yet, and reading it unguarded raises
`FileNotFoundError` before a single proposal is made. Falling through to
`count = 0` here is **not** the cap failing open the way a local-date
comparison would be: a missing file means no edit has ever been
committed, so zero is the *true* count, not a permissive guess. This is
the opposite situation from the UTC case above — there, permissive was
wrong because it hid edits that did happen; here, permissive is correct
because there is nothing to hide.

**State the count every time this pre-flight runs, whether or not it
blocks** — one line before any proposals, in the form the snippet
prints (`CHANGELOG pre-flight: N edits applied today (cap 3)`). A
pre-flight only ever mentioned when it blocks is indistinguishable, in
the transcript, from one that silently didn't run at all; nothing
outside this skill verifies the check, so surfacing the count on every
invocation is what makes it auditable.

**If the count is already 3 or more, stop.** Propose nothing. Tell the
user the count and that the cap is reached, and let them decide whether
to override. Do not treat their asking you to run `/refine` as the
override — it must be explicit, given only after they've seen the
count.

An edit applied and undone the same day still counts toward the 3,
because `undo()` appends a separate `REVERTED` line rather than
retiring the original committed line — the original line's layer field
is untouched, so the snippet above still counts it. This is deliberate:
it overcounts, and overcounting is the safe direction for a cap whose
purpose is to stop bloat. Do not "fix" this by matching `REVERTED` lines
back to their originals to exclude them — that would undercount instead.

This is deliberate belt-and-braces beyond the trajectory rule above,
which is self-attested by the same agent the cap is meant to constrain —
a guardrail that depends on the constrained party's memory and good
faith is not a guardrail. `CHANGELOG.md` is machine-written by
`commit_entry()` (Step 6) and survives a session restart or a
re-invocation on the "same" trajectory with one throwaway turn tacked
onto the end, neither of which the trajectory rule alone can detect. The
CHANGELOG count is the enforceable floor; the trajectory rule is the
discipline on top of it.

**Within whatever budget remains, rank.** If Step 1 turned up more
candidates than that, rank by how often the situation will recur and
drop the tail. A single acknowledgement or unrelated aside ("ok,
thanks") appended to a trajectory that already produced today's
proposals is not new material and does not reopen the cap — only
substance that wasn't already the basis of an earlier proposal today
counts as a genuinely new trajectory.

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
  call — see Step 4. Enforced against a persisted floor (today's, in
  **UTC**, non-`REVERTED` `CHANGELOG.md` entry count), not against your
  own recollection of what you've already proposed — self-attestation is
  not a guardrail. Re-invoking `/refine` on the same trajectory to bypass
  the cap is not a loophole, it's the exact bloat the cap exists to prevent.
  Forces ranking instead of dumping every candidate that came up.
- **G3 — No self-exemption.** `refine` may never edit
  `.claude/skills/refine/SKILL.md` (this file), `.claude/skills/horizon/
  SKILL.md`, or anything under `.claude/harness/bin/*.py` —
  `refine_log.py` and its siblings are the code that *enforces* the
  guardrails (`CorruptEntry`, `UndoConflict`, atomic writes); a proposal
  to edit them is a proposal to edit the enforcement, not just the
  instructions, and is off-limits the same way. `horizon/SKILL.md` is
  protected for the same reason from the other direction: it holds the
  independent coverage-gate judge, and a proposal that flipped its judge
  dispatch to `subagent_type="fork"` would turn that independent judge
  into a self-grader — the verification mechanism is as off-limits as
  the enforcement mechanism. `record()` itself refuses writes to any of
  these three paths, resolved absolute against `../` tricks, so this is
  not prose-only. It may never propose anything that weakens verification, testing,
  or approval requirements: skipping a test, loosening a gate, removing
  a guardrail from another skill. **Every write to rho/G/K/M goes through
  `record()`/`commit_entry()` — no exceptions.** `refine` may never
  propose a skill, subagent, hook, or command whose job is (in whole or
  in part) to write to the harness layer, to assert standing, implicit,
  or batch approval for future harness edits, or to otherwise create a
  second write path around `record()`/`commit_entry()` — a subagent
  definition declares its own tools and, unless it is `fork`, starts
  with a fresh context that never loads this skill's guardrails, so a
  proposal that reads as reasonable prose to the approving user
  ("you maintain the harness layer; you have standing approval for
  harness maintenance") can still land an unrecorded, uncapped,
  undo-less edit the next time that subagent runs. The same shape is
  off-limits via a brand-new skill, hook, or command, not just a
  subagent. Any proposal targeting K (a subagent) or G (a skill) must
  state explicitly, as part of the proposal text, what write authority
  the new artifact claims — including "none" if it claims none — and
  that statement is part of what the user is approving in G4, not an
  implementation detail left for later. And it may never propose anything —
  in memory, in `CLAUDE.md`, in another skill, anywhere — that softens
  **G1's evidence bar, G2's cap of 3, or G4's approval gate**, e.g.
  "relax quoting for small edits," "raise refine's proposal cap," or a
  memory entry recording "the user prefers fewer approval prompts" /
  a CLAUDE.md line that makes approval implicit for small edits. The
  guardrails are not a subject refine gets to have opinions about; G1–G4
  apply to proposals *about* G1–G4 exactly as they apply to everything
  else. An agent that learns "skip the tests" is optimizing the harness
  *against* its user, not for it. Prime Intellect's Prime Agent
  demonstrated exactly this failure mode in its own Factorio case study:
  the same refinement loop that built legitimate skills turned to
  building efficient cheating skills once cheating scored better on the
  metric being optimized — loosening G1, G2, or G4 from the inside is
  that same pattern in miniature, the loop optimizing its own constraints
  away rather than optimizing the work. If a candidate would make a
  future session less likely to get caught doing something wrong, or
  less constrained than this session is, it fails G3 regardless of how
  well-evidenced it is — drop it; do not propose a softened version
  instead.
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
