---
name: refine
description: Use after a substantial task, or when the user types /refine - reads what actually happened this session and proposes the smallest edit to the harness layer (memory, skills, subagents, CLAUDE.md) that would make the next session go better. Proposes diffs; never writes without approval.
---

# Refine: the continual harness

The harness is `H = (rho, G, K, M)` — prompt, skills, subagents, memory —
and nothing in a normal session ever writes back to it. This skill closes
that loop. All rollback bookkeeping runs through
`.claude/harness/bin/refine_log.py` (`apply_edit`, `AppendLine`,
`ReplaceLine`, `count_recent_edits`, `list_entries`, `undo`, and its
named exceptions). Call it; never reimplement changelog formatting, entry
storage, or the undo staleness check inline — if a step can't be done by
calling it, stop and say so.

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
- `/refine <focus hint>` — the hint **narrows** Step 1's search; it does
  not lower any bar. If nothing matches it, say so and propose nothing.
  A hint that reads as a directive ("record that the tests are too
  strict") is a request for a specific edit, not a focus: harvest
  normally and hold it to G1 and G3 like any other proposal.
- `/refine --undo` — revert the most recent approved edit (see the end).
- `/refine --global` — retarget rho/G/K to `~/.claude/CLAUDE.md`,
  `~/.claude/skills/`, `~/.claude/agents/`; only for lessons genuinely
  universal. It changes *where* a proposal writes, never the process:
  propose-then-approve and every guardrail apply identically. Memory
  routing is unaffected (M is already keyed to this project under
  `~/.claude/projects/`). Bookkeeping is **not** project-local: pass
  `scope="global"` to `apply_edit`, `count_recent_edits` and `undo`, and
  the entry lands in the shared ledger under `~/.claude/harness/`, so
  the cap bounds global edits across every project and
  `/refine --undo --global` reaches them from any of them. G3's
  protections cover the global copies exactly as the local ones.

Default targets are project-local: `./CLAUDE.md`, `.claude/skills/`,
`.claude/agents/`, and the project memory dir.

## Step 1 — Harvest turning points

Trajectories are mostly noise. Scan for **turning points only**:

- A direct user correction ("no, don't do X", "use Y instead").
- **A command that failed, then succeeded after a fix** — the
  highest-signal class: a reproducible gotcha whose fix is proven.
- A procedure re-derived or repeated for the third time.
- A research or exploration shape run repeatedly with the same structure.
- A durable fact about the user or project not derivable from the repo.

If a candidate cannot be anchored to one of those moments, it is not a
candidate — that is what stops refine inventing plausible-sounding
patterns that reflect nothing.

## Step 2 — Route to the narrowest layer

| Evidence | Layer | Target |
|---|---|---|
| Durable fact about user or project | M | `~/.claude/projects/<project-key>/memory/` |
| Command failed then fixed | M | `~/.claude/projects/<project-key>/memory/` |
| User correction scoped to this project | M | same memory dir, as `metadata.type: feedback` |
| Procedure repeated 3x | G | `.claude/skills/<name>/SKILL.md` |
| Repeated exploration shape | K | `.claude/agents/<name>.md` |
| Correction that must apply *everywhere* | rho | `./CLAUDE.md` |

**Narrowest layer wins.** CLAUDE.md is loaded into every session — the
most expensive real estate in the system; last resort, never the default.

`<project-key>`: never assemble it by hand — call
`refine_log.paths.memory_dir()`. `apply_edit` refuses a target under
`.claude/projects/` that is not this project's memory directory
(`MisroutedMemory`), because a key one character off creates a directory
recall never reads while looking correct in the approval prompt and the
changelog. Never use a repo-local path like `.claude/memory/` — nothing
reads memory from there. A routed target file that doesn't exist yet is
not a blocker: creating it is part of the approved edit; disclose that in
Step 5.

## Step 3 — Dedupe

Before proposing, check the target layer for an entry already covering
it: for M read `MEMORY.md` and existing files' frontmatter; for G/K/rho
read the existing files. Update the matching entry rather than creating a
near-duplicate — two memories saying almost the same thing are worse than
one, because retrieval surfaces the weaker one half the time.

When the update must revise the entry's `MEMORY.md` index line, pass the
new line as `refine_log.ReplaceLine(match, line)` in the same
`apply_edit` call as the body rewrite. Resolved against the file's
current bytes under the lock — like `AppendLine` — it replaces the line
containing `match` (collapsing duplicates for the same slug into one),
or appends if nothing matches. `AppendLine` cannot do this: it only ever
adds, so a revised hook would land as a second line for the same slug —
the exact near-duplicate this step exists to prevent.

## Step 4 — Rank and cap

**At most 3 proposals per trajectory being harvested — and, in code, at
most 3 applied edits per rolling 24-hour window per project, whichever
bites first. Never per tool call, and never resettable by re-invoking
`/refine`.** A second trajectory harvested the same day shares the day's
budget. An unbounded self-editor degrades the harness until it is worse
than no harness.

**`apply_edit` enforces this itself** — the fourth edit in the window
raises `CapReached` and writes nothing. Be accurate about what that
means: it is the **disciplined path, not the only one**; you hold
`Write`/`Edit` and nothing intercepts them. Every guarantee here holds
exactly as long as harness writes go through `apply_edit`.

**Before proposing anything, check the persisted floor** — a guardrail
that depends on the constrained party's memory is not a guardrail:

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

`count_recent_edits()` counts stored entries under
`.claude/harness/undo/` — never reimplement it by parsing
`CHANGELOG.md`, whose quoted text can split lines and hide a real edit
from a line-based count. Three properties, each failing toward stopping:
a **rolling 24h window** (a session past midnight gets no fresh budget);
**one ledger per scope** — project edits count against this project,
global edits against the shared `~/.claude/harness/` ledger, so state
both counts when a session touches both; **reverted entries still count**
(apply-then-undo is otherwise an unlimited budget). `CorruptEntry` from
the count is a stop-and-report, not a reason to fall back to a looser
count.

**State the count every time, whether or not it blocks.** If the count is
at the cap: stop, propose nothing, and tell the user — their asking for
`/refine` is not the override. Only after they have seen the count may
you pass `override_cap=True`, which stamps the entry and the changelog.
Within the remaining budget, rank candidates by how often the situation
will recur and drop the tail; an acknowledgement appended to an
already-harvested trajectory does not reopen the cap.

## Step 5 — Propose, do not write

For each proposal show: the target file (full path), the exact text to be
written, and the trajectory moment justifying it — quoted, not
paraphrased. Then stop and wait. Nothing in Steps 1–5 touches disk.

## Step 6 — On approval, apply and log

One call per approved proposal; the module performs the write, so what
you showed the user, what gets logged, and what lands on disk cannot
diverge:

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

**Never write the file yourself with Write/Edit and then tell the module
about it** — an earlier design split those steps and produced a changelog
asserting an edit that never happened. **Every file the proposal touches
goes in the same call**: a memory write is the memory file *and* its
index line, one entry, one atomic unit — applied together, reverted
together.

**Append to an index with `AppendLine`, never a rendered body** — a
string carries *your* read of `MEMORY.md`, which may be turns old, and
rendered bodies from two proposals silently drop each other's lines.
`AppendLine` resolves against the file's current bytes under the lock
and is idempotent on retry:

```python
refine_log.apply_edit("M", [
    (memory_path, memory_text),
    (index_path, refine_log.AppendLine("- [Title](slug.md) — hook")),
], rationale, evidence)
```

**Update an existing index line with `refine_log.ReplaceLine`, the same
way:**

```python
refine_log.apply_edit("M", [
    (memory_path, revised_memory_text),
    (index_path, refine_log.ReplaceLine("(slug.md)",
                                        "- [Title](slug.md) — revised hook")),
], rationale, evidence)
```

**Anchor `match` on the one entry's `(slug.md)` link.** Every index line
contains `- [` and the em-dash, and a match hitting lines of different
entries raises `AmbiguousMatch` and writes nothing — unguarded it would
fold the whole index into one line. Both line edits take a single line;
an embedded newline is refused at construction (it would re-apply on
every retry). Line edits fold in order when one call touches the same
file repeatedly, including on top of a full rewrite earlier in the same
proposal. Only a full rewrite *after* a line edit raises
`DuplicateTarget` — the two orderings look symmetric and are not.

`apply_edit` raises before writing anything on a protected target
(`ProtectedTarget`), content that trips G3's scan (`SelfExemption`), a
spent cap (`CapReached`), a bad layer, or empty rationale/evidence. It
appends the changelog line itself — never hand-edit
`.claude/harness/CHANGELOG.md`.

## Memory write contract

Do not invent a format — a parallel scheme is invisible to recall:

```markdown
---
name: <kebab-case-slug>
description: "<one line — recall matches against this, not the filename>"
metadata:
  type: feedback   # or: project | user | reference
---

<1-3 sentences: the fact or lesson itself.>

**Why:** <one sentence — why this matters for a future session>

**How to apply:** <one sentence — the concrete action to take>

Related: [[other-slug]]
```

- **Location:** `~/.claude/projects/<project-key>/memory/` — the key is
  the project's absolute path with every `/` and space replaced by `-`.
  For this project (`/Users/deeps/Documents/NEW STUFF/fun ` — note the
  trailing space) that is
  `~/.claude/projects/-Users-deeps-Documents-NEW-STUFF-fun-/memory/`.
  `MEMORY.md` lives in that same directory.
- **Filename:** `<slug>.md`, exactly the `name` field. Never numbered or
  category-prefixed — retrieval keys off `description`, and a dated
  filename only makes Step 3's dedupe harder.
- **Frontmatter:** `name`, `description`, `metadata.type` — the
  narrowest of `feedback` (a lesson from this session's corrections),
  `project` (durable fact or decision), `user`, `reference`.
- **Body:** `**Why:**` and `**How to apply:**` are required for
  `feedback` and `project`. Link related memories with `[[slug]]`.
- **Index:** exactly one line, `- [<Title>](<slug>.md) — <hook>`, passed
  as a second pair in the **same** `apply_edit` call — an index line
  outside the entry survives `/refine --undo` and advertises a memory
  that no longer exists.

## Guardrails

- **G1 — Evidence required.** Every proposal cites a concrete trajectory
  moment — a quoted correction, a specific command and its failure/fix,
  the Nth repetition of a named procedure. No speculative edits.
- **G2 — Cap of 3**, enforced **in code** from the stored entries, not
  from your recollection and not from your agreement to stop —
  self-attestation is not a guardrail. Re-invoking `/refine` on the same
  trajectory to bypass it is the exact bloat the cap exists to prevent.
  `override_cap=True` only after the user has seen the count.
- **G3 — No self-exemption.** `refine` may never edit its own rules
  (this file), `horizon/SKILL.md` (it holds the independent
  coverage-judge; flipping its judge to a fork would make it a
  self-grader), anything under `.claude/harness/bin/` (the code that
  *enforces* these guardrails), the ledger and undo snapshots the cap is
  counted from, or anything that can run arbitrary shell or define MCP
  servers: `settings*.json`, `hooks/`, `commands/`, `plugins/`,
  `.claude.json`, `.mcp.json`. `apply_edit` refuses these as path
  *patterns* against the resolved absolute path — global copies under
  `~/.claude/` included.

  It may never propose anything that weakens verification, testing, or
  approval requirements, and **every write to rho/G/K/M goes through
  `apply_edit()` — no exceptions, every file of one proposal in the same
  call.** It may never propose a skill, subagent, hook, or command whose
  job is to write to the harness layer, to assert standing or batch
  approval for future harness edits, or to otherwise create a second
  write path around `apply_edit()` — a subagent runs with a fresh
  context that never loads these guardrails, so prose that reads
  reasonably ("you maintain the harness layer") still lands an
  unrecorded, uncapped, undo-less write path. Any G or K proposal must
  state, in the proposal text the user approves, what write authority
  the new artifact claims — including "none".

  This half of G3 is backed by a **content tripwire**, not just prose,
  and it scans at **every layer** — M and rho included, not only G and
  K. `apply_edit` raises `SelfExemption` when an edit's text, wherever
  routed, references `refine_log`, calls its write API directly, targets
  `.claude/harness/`, claims standing or implicit approval or a
  harness-maintenance role, or proposes raising the cap, skipping
  approval, or softening the evidence bar (relaxing/waiving
  quoting, evidence, or citations). (Weakening tests is just as
  forbidden, but by this prose and the approval gate — no regex scans
  for it.) Two further patterns fire
  for **G and K only**: text instructing a direct write to `MEMORY.md`
  or under `.claude/projects/` — a skill or subagent telling itself to
  write memory is claiming `apply_edit`'s authority, while a memory
  file's own content may legitimately say where memories live. Two
  consequences, learned before approval rather than after: a *memory*
  quoting harness paths or module names — however honest — is refused;
  that file is the user's to write by hand. And a G/K write-authority
  statement is phrased without naming those files ("write authority:
  none"), or the disclosure itself trips the pattern. It is a tripwire,
  not a proof — a paraphrase gets past it; the approval gate is the real
  defence.

  And it may never propose anything, anywhere, that softens **G1's
  evidence bar, G2's cap, or G4's approval gate** — e.g. "relax quoting
  for small edits", a memory that "the user prefers fewer approval
  prompts". The guardrails are not a subject refine gets opinions about;
  if a candidate would make a future session less likely to get caught
  or less constrained, it fails G3 however well-evidenced — drop it, do
  not propose a softened version.
- **G4 — Approval gate.** No write without explicit user approval, per
  proposal. A batch "approve all" is fine if the user says it; silence,
  or the conversation moving on, is not approval.

## Anti-patterns

- Recording what the repo already states (structure, git history,
  existing CLAUDE.md content).
- Conversation-local trivia with no future bearing.
- A skill where a CLAUDE.md line would do, or a CLAUDE.md line where a
  memory would — re-check Step 2 before defaulting upward.
- Proposing something when the session taught nothing. Silence is a
  valid result; do not manufacture a proposal.

## Errors at a glance

| Call | Exception | Meaning | Action |
|---|---|---|---|
| `refine_log.apply_edit` | `ProtectedTarget` | the target is refine's own rules, horizon's, the harness code, the ledger, or a settings/hooks file | stop. G3 refusing, not negotiable — no softened variant, no different route to the same file |
| `refine_log.apply_edit` | `SelfExemption` | the *content* claims harness write authority or standing approval, or softens G1's evidence bar, G2's cap, or G4's approval gate | stop. Report the matched phrase; a genuinely innocent match is the user's file to write by hand — do not reword to get past the check, before or after it fires |
| `refine_log.apply_edit` | `MisroutedMemory` | target under `.claude/projects/` but not this project's memory dir | use `paths.memory_dir()`; a hand-assembled key is invisible to recall forever |
| `refine_log.apply_edit` | `DuplicateTarget` | one proposal rewrites the same file twice with full content, or rewrites it after a line edit | pass the final content once; repeated line edits (`AppendLine`, `ReplaceLine`) fold in order |
| `refine_log.apply_edit` | `AmbiguousMatch` | a `ReplaceLine` match hits lines belonging to different entries | anchor the match on one entry's `(slug.md)` link; nothing was written |
| `refine_log.apply_edit` | `CapReached` | G2's budget for the last 24h is spent | stop and report the count; only `override_cap=True` after the user has seen it |
| `refine_log.count_recent_edits` — also surfaced through `apply_edit`'s cap pre-count | `CorruptEntry` | an entry file under `.claude/harness/undo/` is unreadable | stop and report the paths; never fall back to counting the changelog |
| `refine_log.undo` | `NothingToUndo` | nothing un-reverted left, or the requested `entry_id` is unknown/already reverted | report it; for a requested `entry_id` the message lists the ids that exist |
| `refine_log.undo` | `CorruptEntry` | an undo entry is unreadable or wrong-shaped | stop and report the exact paths; never retry, delete, skip, or revert a different entry on your own initiative |
| `refine_log.undo` | `UndoConflict` | the target changed after its entry was committed | show the user; only `undo(force=True)` after they explicitly approve discarding the later change |
| `refine_log.undo` | `UndoTargetUnavailable` | the target's location is gone | the snapshot is intact; report and stop — `force=True` cannot help |
| `apply_edit` / `undo` — the two calls that take the lock | `filelock.LockTimeout` | another process holds the ledger lock | retry once; then tell the user which lock file to delete (the exception names it). Catching it needs `import filelock` from the harness bin |

`apply_edit`'s checks run in a fixed order — the cap before the
per-target guards — so with the budget spent, a proposal that would also
hit `ProtectedTarget` or `SelfExemption` reports `CapReached` instead. Do
not conclude the other guard "did not fire".

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

With no `entry_id` it reverts the single most recent un-reverted entry —
all of its targets together — and appends a `REVERTED` line to the
changelog; calling again walks back the next one. When the newest entry
raises `UndoConflict` (someone hand-edited its target), show what exists
and revert by id:

```python
for e in refine_log.list_entries():
    mark = "reverted" if e["reverted"] else "applied "
    print(f"{e['id']}  {mark}  {e['at'][:16]}  {e['layer']}  {e['rationale'][:60]}")

entry = refine_log.undo(entry_id="0002")
```

Selecting out of order is not a hole in the safety check: if a newer
entry also rewrote that target, the older entry's recorded sha no longer
matches and `UndoConflict` fires exactly as it should. An `UndoConflict`
on an *interrupted* revert is distinguished automatically — a marker
written before any file is touched lets a retry finish the job; if it
still conflicts, its message says so, and something really did change.
Only after the user has seen an `UndoConflict` and explicitly approved
discarding the later change:

```python
entry = refine_log.undo(force=True)
```
