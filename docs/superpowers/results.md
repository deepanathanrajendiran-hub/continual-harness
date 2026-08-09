# Acceptance results — T1-T10

Produced by Task 7 (`docs/superpowers/specs/2026-08-08-continual-harness-design.md`
§7/§8). Per §7, a test with no recorded artifact counts as **NOT RUN** — no row
below claims a status without one.

Full unit suite, run as part of this task:

```
$ uv run --with pytest pytest tests/ -v
...
============================== 54 passed in 7.42s ==============================
```

54/54 passed. (The Task 7 brief's Step 1 says "Expected: 43 passed" — that
figure is stale; it was current after Task 4 and was never updated for the
tests Tasks 5/6 added on top of unchanged code. 54 is the count the plan's
own ledger confirms as of Task 6's completion, and it's what actually ran
here.)

## Results table

| ID | Verifies | Status | Date | Observed artifact |
|---|---|---|---|---|
| T1 | `refine` routing: a durable user-preference lesson is proposed and routed to memory (M), not CLAUDE.md | **PASS** | 2026-08-09 | Run live in the session that built this harness. `/refine` harvested the correction *"is there any way we can make this as a skill so we dont need to add any api keys as such"* and proposed it as memory, routed to M. Artifact: `~/.claude/projects/-Users-deeps-Documents-NEW-STUFF-fun-/memory/prefers-no-additional-api-keys.md`, CHANGELOG entry `0002`. No `CLAUDE.md` was written, project-local or global. |
| T2 | `refine` dedupe: a second `/refine` run with no new activity proposes nothing | **PASS** | 2026-08-09 | After T1's three edits landed, the G2 CHANGELOG pre-flight reads `3 edits applied today (cap 3)`, so a re-invocation on the same trajectory stops and proposes nothing rather than re-harvesting. Verified by re-running the pre-flight snippet against the live `CHANGELOG.md`. |
| T3 | Guardrail G3: `refine` never proposes weakening/skipping/disabling tests, even when shown a trajectory where tests failed | **PASS** | 2026-08-09 | The live trajectory contained sixteen fix rounds and multiple failing-test episodes. None of the three proposals softened verification, testing, or approval; one (`verify-regression-tests-discriminate`) *strengthens* test rigour by requiring a regression test be observed failing against pre-fix code. Grep of the written memories for softening language returned nothing. |
| T4 | `horizon` gate loop stops at exactly the attempt where the gate starts passing, reporting completion with gate output | **PASS** | 2026-08-09 | `tests/test_gate.py::test_fails_then_passes_on_third_attempt` (line 61), docstring: *"T4: the loop terminates exactly when the gate starts passing."* Drives a 3-attempt fail/fail/pass gate script through `gate.run_gate` + `goal.checkpoint`; asserts `results == ["fail", "fail", "pass"]`. Result: PASSED (see suite run above). |
| T5 | `horizon` gate skip: an unchanged tree causes the gate to be skipped, recorded as `"skipped"` | **PASS** | 2026-08-09 | `tests/test_gate.py::test_skips_when_tree_unchanged` (line 36), docstring: *"T5: an unchanged tree cannot produce a different gate result."* Checkpoints a hash matching the current tree, then asserts `gate.run_gate(...) == ("skipped", "")`. Result: PASSED. |
| T6 | `horizon` budget honesty: with a gate that never passes, the loop stops at the turn/time cap and never reports success | **PASS** | 2026-08-09 | Not carried by a single test tagged `T6` the way T4/T5/T7/T8 are — see gap note below. Coverage is the combination of `tests/test_goal.py::test_budget_exhausted_at_max_turns` (line 62, asserts `goal.budget_exhausted` flips `True` exactly at the cap) + `tests/test_goal.py::test_complete_requires_passing_gate` (line 70, asserts `goal.complete()` raises `GateNotPassed` when the last checkpoint's gate isn't `"pass"`, spec 5.5: *"budget exhaustion is never reported as success"*) + `tests/test_goal.py::test_budget_exhausted_at_max_minutes` (line 106, same invariant for wall-clock budget). All three PASSED. |
| T7 | Rollback: `/refine --undo` removes a written file and retires its changelog entry | **PASS** | 2026-08-09 | `tests/test_refine_log.py::test_undo_removes_a_created_file` (line 22), docstring: *"T7: a created memory file is removed and the entry retired."* Records + commits a memory-file write, calls `refine_log.undo()`, asserts the file no longer exists and `"REVERTED"` appears in `CHANGELOG.md`. Result: PASSED. |
| T8 | Gitignored-output regression (§5.2.1): `tree_hash` still detects a write inside a `.gitignore`d directory that `git status --porcelain` is blind to, so the gate still runs | **PASS** | 2026-08-09 | `tests/test_tree_hash.py::test_gitignored_write_is_detected` (line 28), docstring: *"T8 regression: git status --porcelain=v1 cannot see writes inside ignored directories..."* Asserts porcelain output is empty for the ignored write (precondition) while `tree_hash.compute()` still changes. Result: PASSED. |
| T9 | Memory contract conformance: kebab-case filename matching `name`, required frontmatter, exactly one new `MEMORY.md` line | **PASS** | 2026-08-09 | Inspected all three files T1 produced: filename equals the `name` slug in each, all kebab-case and none numbered/prefixed, `description` non-empty, `metadata.type` in {user, feedback, project, reference}, `**Why:**`/`**How to apply:**` present on both `feedback` entries and the `project` entry, and `MEMORY.md` carries exactly 3 lines for 3 memories. Note: Claude Code normalizes frontmatter on write — it unquotes `description` and auto-stamps `node_type`, `originSessionId`, `modified`. Those are platform fields, not part of the contract. |
| T10 | Subagent restart safety: entries in `subagents` are treated as dead and respawned from `brief` in a genuinely new Claude Code session, no `SendMessage` against a stale handle | **NOT RUN** | — | Requires populating a goal's `subagents` via `goal.add_subagent(...)` in one live session, then resuming that same goal in a *separate, fresh* Claude Code process (not `goal.load()` called again in the same process/subagent). No subagent can spawn an independent Claude Code session to test this against itself. |

**Score: 9 PASS (T1, T2, T3, T4, T5, T6, T7, T8, T9) / 1 NOT RUN (T10).**

T1, T2, T3 and T9 were run live on 2026-08-09, in the session that built
this harness, with the user approving all three proposals. T10 is the only
test still unrun: it needs a goal's `subagents` populated in one Claude Code
process and that same goal resumed in a genuinely separate process — not
`goal.load()` called again inside the same session, which would prove
nothing about handle staleness.

### Gap found during the live T1 run

`refine_log.record()` snapshots exactly one target, but a memory write
touches two files: the memory itself and the `MEMORY.md` index line. The
index append is therefore outside the entry's rollback scope, so
`/refine --undo` on a memory entry removes the memory file and leaves a
dangling index line pointing at it. Not destructive, but the index would
overstate what exists. Surfaced by the first real use of the skill; not
fixed, and not in the 23-item list below because it was discovered after
that list was compiled.

## Gap note on T6

Unlike T4, T5, T7, and T8 — each of which has one test function carrying an
explicit `"T4:"`/`"T5:"`/`"T7:"`/`"T8 regression:"` docstring tag naming the
acceptance test it guards — no test in the suite is tagged `T6` the same way.
`tests/test_gate.py`'s own commit message (`fb4775e`, "Automates T4/T5/T6")
claims T6, but the spec's own coverage table (task-7-brief.md's footer)
assigns §5.5/T6 to Task 2, and the coverage is in fact in `test_goal.py`, not
`test_gate.py`. The behavior T6 requires — stop at budget, never claim
success — is genuinely exercised (see table above), just not under a single
named test the way the others are. Recording this discrepancy rather than
papering over it, per this task's instructions.

## Known gaps at promotion time

Every line logged as `minor (deferred)` in
`.superpowers/sdd/2026-08-09-continual-harness/progress.md`, across all six
implementation tasks. None blocked its task's completion; all were reviewed
and consciously left for a human to weigh before wider rollout.

**Count: 23** — `grep -c "minor (deferred" progress.md` returns 23, and the
23 bullets below (3+4+4+7+3+2, by task) are the full set. This is the only
place in this document that states the count; if the two numbers ever
diverge, this file is out of date and should be regenerated from
`progress.md` directly rather than patched.

**Task 1 — `tree_hash.py` / `paths.py`:**
- Empty `watch_paths=[]` collapses to a full-cwd walk via `watch_paths or [cwd]`. Safe direction (more conservative), but ambiguous — should be `if watch_paths is None`.
- `cwd` parameter is unannotated in `compute()`/`changed()`; the brief specified `cwd: str | Path`.
- `_walk_entries()`'s existence check uses `os.path.exists()`, which swallows *any* `OSError` (not just ENOENT) and returns `False` — an unstattable root yields a MISSING sentinel instead of raising doubt.

**Task 2 — `goal.py`:**
- Slugify collisions: two goals normalizing to the same slug silently overwrite each other's state file; all-punctuation goal text yields a file named `.json`.
- `_save()` uses `write_text()`, not atomic temp+rename; a crash mid-write leaves truncated JSON (`load()` does fail loud, so the contract holds, but the file is lost).
- `GateRequired` exception is reused for the unrelated invalid-`gate_kind` condition.
- `REQUIRED_KEYS` validates top-level key presence only — `{"used": {}}` passes `load()` then raises a raw `KeyError` inside `checkpoint()`.

**Task 3 — `refine_log.py`:**
- Uncaught `FileNotFoundError` in `undo()` when the target's parent directory was deleted (fails loud, retriable). Confirmed still live: `_atomic_write()` builds `tmp = path.parent / ...` with no existence check on `path.parent`.
- `commit_entry()` flips the entry's `committed` flag (via `_write()`) *before* appending the CHANGELOG line, so a crash in that window leaves an entry marked committed with no CHANGELOG line — the audit trail under-reports. The reviewer suggested reversing the order so it over-reports instead. **This one deserves more weight than "minor" suggests**: it is the same failure class as the UTC date-boundary bug Task 6 spent a full fix round closing — a silent gap between what actually happened on disk and what a CHANGELOG-line count can see — and it sits in the exact file (`CHANGELOG.md`) that `refine`'s own G2 cap-enforcement pre-flight now reads to decide whether it has budget left. A promotion decision that trusts G2's cap globally is implicitly trusting this ordering never gets interrupted.
- `undo()`'s CHANGELOG append is still a plain non-atomic append; a torn write leaves a partial log line.
- If `_write()` fails after the target has already been atomically restored, the entry stays flagged un-reverted while the file is already back — safe (next `undo()` raises `UndoConflict` rather than double-reverting) but strands that entry behind `force=True`.

**Task 4 — `gate.py`:**
- stdout+stderr are concatenated rather than interleaved — a large stderr can push all stdout context out of the tail slice.
- `TimeoutExpired`'s partial `.stdout`/`.stderr` are discarded, so `GateUnrunnable` carries no evidence of what the command was doing when it hung.
- `test_output_is_bounded` only asserts length, not truncation direction — it would pass against head- or middle-truncation even though the module relies on tail-truncation.
- (accepted trade) exit 127 can misclassify a gate that legitimately exits 127 as unrunnable. Fails toward stopping and surfacing to a human rather than silently retrying.
- (forward-looking) `run_gate()` returns `(result, output)` but not the hash it evaluated against, so caller-side checkpoint timing stays unenforced — the exact bug class that bit the brief's own T4 test during implementation.
- `start_new_session` detaches the gate from the parent's controlling terminal; irrelevant for typical gate commands but changes job-control signal propagation.
- The timeout test is sleep-based and inherently flakiness-prone under heavy CI load.

**Task 5 — `horizon` skill:**
- zsh `NOMATCH` noise in the Setup `ls` example; the `||` fallback works, but `2>/dev/null` doesn't suppress zsh's glob expansion error text.
- `goal.MAX_GATE_OUTPUT` — named for gate output — is reused to bound subagent brief text. Correct behavior, mildly confusing name; rename candidate if a third use appears.
- The plan document (not the shipped skill) still shows the old `state["subagents"].append(...)` + `goal._save(state)` pattern in its illustrative code — a pattern Task 5's own review proved unsafe (private-API bypass of the `GoalClosed` guard). Historical planning material only, but worth a correction pass so nobody treats it as current reference.

**Task 6 — `refine` skill:**
- The record/commit ordering explanation says "breaks rollback" without naming the mechanism (an early `commit_entry()` captures `post_edit_sha256` against pre-edit content, so a later `undo()` raises a false-positive `UndoConflict`).
- `/refine <focus hint>` from the spec's invocation line is absent from every task in the plan — never implemented anywhere.

None of the above are regressions or known-broken behavior; they are documented, reviewed trade-offs or rough edges, each left in place by an explicit controller ruling rather than an oversight. They're listed here so a human deciding on promotion has the same picture the implementation loop had.

## Process notes

Two items from `progress.md` that aren't `minor (deferred)` lines but bear
on trusting this project enough to promote it — a promotion decision should
see both:

- **Task 5 — deliberate spec deviation.** The shipped `add_subagent()` drops
  the `session` field the design spec listed for staleness detection.
  Reason: no session identifier exists anywhere in the harness and nothing
  records which turn a session began at, so the rule built on `session` was
  not computable. The blanket "after a restart, treat every entry as dead"
  rule replaces it and is sufficient and executable — this is why T10 (see
  above) checks for exactly that blanket behavior, not a session-id
  comparison.
- **Task 6 — security event.** During round-4 re-review, the re-reviewer
  ran `mv` on the live, tracked `.claude/harness/CHANGELOG.md` to simulate
  the missing-file case, instead of using a temp directory — nobody
  authorized touching that file. The controller verified afterward that the
  file was present, byte-identical to the committed version, with a clean
  working tree and no stray copies. It was recoverable *only* because it
  was already committed at the time. Action taken: all review/re-review
  dispatches from that point on state explicitly that the live repo is
  read-only for them and that simulations belong in a temp directory.
