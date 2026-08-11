---
name: refine
description: Use after a substantial task, or when the user types /refine - reads what actually happened this session and proposes the smallest edit to the harness layer (memory, skills, subagents, CLAUDE.md) that would make the next session go better. Proposes diffs; never writes without approval.
---

# Refine: the continual harness

The harness is `H = (rho, G, K, M)` — prompt, skills, subagents, memory.
Every one is editable. This skill closes the loop that otherwise never
closes: nothing in a normal session ever writes back to it.

Rollback bookkeeping runs through one module at
`.claude/harness/bin/refine_log.py` (`apply_edit`, `AppendLine`,
`count_recent_edits`, `list_entries`, `undo`, plus the `NothingToUndo` /
`CorruptEntry` / `UndoConflict` / `UndoTargetUnavailable` /
`ProtectedTarget` / `SelfExemption` / `CapReached` exceptions).
The skill calls it; it does not reimplement changelog formatting, entry
storage, or the undo staleness check inline. If a step below can't be
done by calling it, stop and say so rather than inventing an inline
substitute.

## Setup

```bash
python3 - <<'PY'
import sys, pathlib
_c = pathlib.Path.cwd().resolve()
_bin = next((c / ".claude/harness/bin" for c in (_c, *_c.parents)
             if (c / ".claude/harness/bin").is_dir()),
            pathlib.Path.home() / ".claude/harness/bin")
sys.path.insert(0, str(_bin))
import refine_log
print('module loads OK')
PY
```

Quote the path — the project directory name ends in a space.

## Invocation

- `/refine` — harvest the whole trajectory.
- `/refine <focus hint>` — harvest only what relates to the hint, e.g.
  `/refine the test failures` or `/refine how we handled paths`. The hint
  **narrows** Step 1's search; it does not lower any bar. Every proposal
  must still satisfy G1's evidence rule, and if nothing in the trajectory
  matches the hint, the correct answer is to say so and propose nothing —
  never stretch an unrelated turning point to fit the hint, and never
  treat the hint as an instruction about what conclusion to reach. A hint
  that reads as a directive ("record that the tests are too strict")
  is a request for a specific edit, not a focus: harvest normally and
  hold that proposal to G1 and G3 like any other.
- `/refine --undo` — revert the most recent approved edit (see the end of
  this file).
- `/refine --global` — see Scope below.

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
- **Changelog/undo bookkeeping stays project-local.** `apply_edit()`
  always writes its ledger and snapshot to *this* project's
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

**`apply_edit` enforces this itself.** The fourth edit inside the window
raises `CapReached` and writes nothing — you are not trusted to stop, and
neither is any future edit to this file. The pre-flight below exists so
you can rank *before* proposing and tell the user where the budget
stands, not because the count is advisory.

**Before proposing anything, check the persisted floor, not your own
recollection.** A guardrail that depends on the constrained party's memory
is not a guardrail.

```python
import sys, pathlib
_c = pathlib.Path.cwd().resolve()
_bin = next((c / ".claude/harness/bin" for c in (_c, *_c.parents)
             if (c / ".claude/harness/bin").is_dir()),
            pathlib.Path.home() / ".claude/harness/bin")
sys.path.insert(0, str(_bin))
import refine_log
print(f"cap pre-flight: {refine_log.count_recent_edits()} of "
      f"{refine_log.CAP} edits used in the last {refine_log.CAP_WINDOW_HOURS}h")
```

`count_recent_edits()` counts the stored entries under
`.claude/harness/undo/`. It does **not** parse `CHANGELOG.md`. That
distinction is load-bearing: the changelog carries quoted trajectory text,
and a newline inside a rationale would split a markdown line so a
line-based count silently missed a real, committed, undoable edit — a cap
failing in the one direction a cap must never fail. Do not reimplement the
count by reading the changelog.

Three properties of the count, each chosen to fail toward stopping:

- **A rolling 24-hour window, not a UTC calendar day.** A session that
  runs past midnight would otherwise be handed a fresh budget
  mid-trajectory. The cost — two unrelated sessions in one day sharing a
  budget — is the harmless direction.
- **Reverted entries still count.** Apply-then-undo is otherwise an
  unlimited budget. The cap exists to force ranking, and an undo does not
  undo the ranking decision.
- **An entry with an unreadable timestamp counts.** It cannot be placed
  outside the window, so it is treated as inside it.

It raises `CorruptEntry` if any entry file is unreadable. That is not a
reason to fall back to a looser count: report it and stop, exactly as
`undo()` does.

**State the count every time, whether or not it blocks.** A pre-flight
only mentioned when it blocks is indistinguishable, in the transcript,
from one that never ran.

**If the count is already at the cap, stop.** Propose nothing. Tell the
user the count and let them decide whether to override. Their asking you
to run `/refine` is not the override — it must be explicit, given after
they have seen the count. Only then may you pass `override_cap=True`,
which records `cap_override` on the entry and marks the changelog line, so
an override is never mistaken later for the cap having failed.

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

## Step 6 — On approval, apply and log

One call per approved proposal. The module performs the write:

```python
import sys, pathlib
_c = pathlib.Path.cwd().resolve()
_bin = next((c / ".claude/harness/bin" for c in (_c, *_c.parents)
             if (c / ".claude/harness/bin").is_dir()),
            pathlib.Path.home() / ".claude/harness/bin")
sys.path.insert(0, str(_bin))
import refine_log

entry = refine_log.apply_edit(
    layer,                     # "rho" | "G" | "K" | "M"
    [(target_path, new_content)],   # every file this proposal touches
    rationale,                 # one sentence
    evidence,                  # the trajectory moment from Step 5, quoted
)
```

**Do not write the file yourself with Write/Edit and then tell the module
about it.** `apply_edit` takes the approved content and performs the write
precisely so that what you showed the user, what gets logged, and what
lands on disk cannot diverge. An earlier design split those steps and a
single mistyped path produced a changelog asserting an edit that never
happened, an `undo()` that "reverted" an untouched file, and a real change
with no snapshot at all.

**Every file the proposal touches goes in the same call.** Writing a
memory means writing the memory file *and* appending its `MEMORY.md`
index line — pass both pairs. One approved proposal is one entry and one
atomic unit: all of them are written together, all of them revert
together, and a failure part-way rolls the earlier ones back. Splitting
them across two calls leaves `undo()` able to remove the memory while the
index still advertises it, and burns two of your three proposals for one
lesson.

**Append to an index with `AppendLine`, never with a rendered body:**

```python
refine_log.apply_edit("M", [
    (memory_path, memory_text),
    (index_path, refine_log.AppendLine("- [Title](slug.md) — hook")),
], rationale, evidence)
```

A string carries *your* read of `MEMORY.md`, which may be several turns
old. Two memory proposals in one session both read the index before either
wrote, so each rendered a full body containing exactly one new line and
the second silently dropped the first's: the memory file survived, its
index entry did not, and nothing in the entry or the changelog showed
anything had been lost. `AppendLine` is resolved against the file's
current bytes while the lock is held, and appending a line that is already
present is a no-op, so a retry cannot double it.

`apply_edit` raises before writing anything if the target is protected
(`ProtectedTarget`, guardrail G3), if the *content* claims harness
authority or softens a guardrail (`SelfExemption`, also G3 — see below),
if the cap is spent (`CapReached`, G2), if `layer` is not one of the four,
or if `rationale`/`evidence` are empty. It appends the changelog line
itself — never hand-edit `.claude/harness/CHANGELOG.md`; every line in it
should trace back to an `apply_edit()` or `undo()` call.

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
- **Index:** exactly **one** line appended to `MEMORY.md` in the same
  directory: `- [<Title>](<slug>.md) — <hook>`. Never put memory content
  in the index — it's a table of contents, not a copy. **Pass the index
  file as a second `(target, content)` pair in the same `apply_edit()`
  call**, not as a separate write: an index line outside the entry
  survives `/refine --undo` and goes on advertising a memory that no
  longer exists.

## Guardrails

- **G1 — Evidence required.** Every proposal cites a concrete trajectory
  moment — a quoted correction, a specific command and its failure/fix,
  the Nth repetition of a named procedure. No speculative or anticipatory
  edits ("this might help next time").
- **G2 — Cap of 3.** At most 3 proposals per trajectory, not per tool
  call — see Step 4. Enforced **in code**: `apply_edit` counts the stored
  entries of the last 24 hours and raises `CapReached` on the fourth,
  writing nothing. Not against your own recollection of what you have
  already proposed, and not on your agreement to stop — self-attestation
  is not a guardrail, and a limit the constrained party applies to itself
  is self-attestation with extra steps. Re-invoking `/refine` on the same
  trajectory to bypass the cap is not a loophole, it's the exact bloat the
  cap exists to prevent. Forces ranking instead of dumping every candidate
  that came up. `override_cap=True` exists for a user who has seen the
  count and said so explicitly, and stamps the entry and the changelog
  when used.
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
  the enforcement mechanism. `apply_edit()` itself refuses these targets,
  matched as path *patterns* against the resolved absolute path — so the
  rule holds for the global copies under `~/.claude/` exactly as for this
  project's, and covers the ledger and undo snapshots the cap is counted
  from, plus `settings*.json` and `hooks/` where a hook can run arbitrary
  shell. It is not prose-only, and it is not three literal paths. It may never propose anything that weakens verification, testing,
  or approval requirements: skipping a test, loosening a gate, removing
  a guardrail from another skill. **Every write to rho/G/K/M goes through
  `apply_edit()` — no exceptions, and every file a single proposal touches goes in the *same* call.** `refine` may never
  propose a skill, subagent, hook, or command whose job is (in whole or
  in part) to write to the harness layer, to assert standing, implicit,
  or batch approval for future harness edits, or to otherwise create a
  second write path around `apply_edit()` — a subagent
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
  implementation detail left for later.

  This half of G3 is backed by a **content tripwire**, not just prose:
  `apply_edit` raises `SelfExemption` when a G or K edit's text references
  `refine_log`, calls its write API directly, targets `.claude/harness/`,
  claims standing or implicit approval, or claims a harness-maintenance role — and when an edit at *any* layer proposes
  raising the cap, skipping approval, or weakening tests or gates. It is a
  tripwire, not a proof: a determined paraphrase gets past it, and the
  approval gate remains the real defence. It exists so that the shape the
  audit found — `~/.claude/skills/harness-maintainer/SKILL.md`, a path no
  denylist protects — fails closed instead of depending on the constrained
  party to notice. If it fires on something genuinely innocent, that is
  the user's file to write by hand; refine does not get to make that class
  of change on its own authority.

  And it may never propose anything —
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
| `refine_log.apply_edit` | `ProtectedTarget` | the target is refine's own rules, horizon's, the harness code, the ledger, or a settings/hooks file | stop. This is G3 refusing, and it is not negotiable — do not propose a softened variant or a different route to the same file. |
| `refine_log.apply_edit` | `SelfExemption` | the *content* claims harness write authority, standing approval, or softens G1/G2/G4 | stop. Also G3, for the same reason. Report the matched phrase to the user; if the match is genuinely innocent, they can write the file themselves — do not reword it to get past the check. |
| `refine_log.apply_edit` | `CapReached` | G2's budget for the last 24h is spent | stop and report the count. Only re-run with `override_cap=True` if the user, having seen the count, explicitly says to. |
| `refine_log.count_recent_edits` | `CorruptEntry` | an entry file under `.claude/harness/undo/` is unreadable | stop and report the paths. Do not fall back to counting the changelog — that is the looser count this design deliberately replaced. |
| `refine_log.undo` | `NothingToUndo` | no matching entry: nothing un-reverted left, or the requested `entry_id` is unknown or already reverted | report it; the message lists the ids that exist |
| `refine_log.undo` | `CorruptEntry` | an undo-log entry file under `.claude/harness/undo/` is unreadable or not valid JSON | stop. Report the exact file path(s) named in the exception to the user. Do not retry, delete the file, skip past it, or fall back to reverting a different entry on your own initiative — guessing past damaged history risks reverting the wrong edit. |
| `refine_log.undo` | `UndoConflict` | the target's current sha256 doesn't match what was recorded when its entry was committed — something changed the target after the approved edit landed | stop. Show the user the target path and that it changed since. Only call `undo(force=True)` after the user explicitly approves discarding that later change — silently forcing would delete an edit nobody agreed to lose. |

## `/refine --undo`

```python
import sys, pathlib
_c = pathlib.Path.cwd().resolve()
_bin = next((c / ".claude/harness/bin" for c in (_c, *_c.parents)
             if (c / ".claude/harness/bin").is_dir()),
            pathlib.Path.home() / ".claude/harness/bin")
sys.path.insert(0, str(_bin))
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
except refine_log.UndoTargetUnavailable as e:
    print(f"cannot undo, location gone: {e}")
    # the snapshot is intact and the revert stays valid once the
    # directory is restored. Report and stop; force=True cannot help.
else:
    reverted = ", ".join(t["path"] for t in entry["targets"])
    print(f"reverted entry {entry['id']}: {reverted}")
```

**Undoing something other than the top of the stack.** `undo()` takes the
most recent un-reverted entry. When that one raises `UndoConflict` —
someone hand-edited its target since — every older entry used to be stuck
behind it, because nothing else was reachable. Show the user what exists
and revert by id instead:

```python
for e in refine_log.list_entries():
    mark = "reverted" if e["reverted"] else "applied "
    print(f"{e['id']}  {mark}  {e['at'][:16]}  {e['layer']}  {e['rationale'][:60]}")

entry = refine_log.undo(entry_id="0002")
```

Selecting out of order is not a hole in the safety check. If a newer entry
also rewrote that target, the older entry's recorded sha256 no longer
matches the file and `UndoConflict` fires exactly as it should — the newer
content was never snapshotted by the older entry, so reverting would
destroy it.

Reverts the single most recent un-reverted entry — **all of its targets
together**, since one approved proposal is one atomic unit — and appends a
`REVERTED` line to `CHANGELOG.md`. There is no "undo entry #7
specifically" call — it always targets the top of the stack, so calling
it again walks back the next most recent entry.

Only after the user has seen a `UndoConflict` and explicitly approved
discarding the later change:

```python
entry = refine_log.undo(force=True)
```
