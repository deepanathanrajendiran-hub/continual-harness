# Citation audit of `t10-evidence.md`

Every row of `docs/superpowers/t10-evidence.md` opened against the file and
line range it cites, and given a verdict. 29 rows, none sampled, none skipped.

Verdict vocabulary:

- **accurate** — the cited lines genuinely state the claimed guarantee.
- **wrong** — the lines exist but say something else, or the citation is
  displaced far enough that a reader following it lands on the wrong code.
- **missing** — the range is out of bounds, or the guarantee appears nowhere
  in the cited file.

A row citing several ranges gets a sub-verdict per range and takes the worst
one as its overall verdict.

Sources as audited: `.claude/harness/bin/gate.py` (205 lines),
`.claude/harness/bin/goal.py` (478 lines), both at commit `3494661`.

## Result

| | rows |
|---|---|
| accurate | 25 |
| wrong | 4 |
| missing | 0 |
| **checked** | **29 / 29** |

The four wrong rows are **H10, H16, H17** — displaced by roughly ten lines —
and **G11**, off by one. Nothing was fabricated: every guarantee in the note
is genuinely present in the module it names. What failed is the *pointer*,
not the claim.

### Why the three `goal.py` rows drifted

Commit `3494661` — the commit that created the evidence note — also inserted
10 lines into `goal.py` at line 352 (the silent-gate evidence fallback in
`_complete_locked`). The note's later citations were written against the
pre-insertion file and never re-derived, so every one of them past line 352
points ~10 lines short of its target. `H12`'s `463-468` is the exception: it
lands correctly, which means the note's citations were not all captured at the
same moment.

This is the failure mode a line-number citation has and a symbol-name citation
does not. The note is one edit away from being wrong again.

## `gate.py` — rows G1–G12

| # | Cited | Verdict | Evidence at the cited lines |
|---|---|---|---|
| G1 | `gate.py:23-27` | accurate | `# ... It must never compare / # equal to anything, including itself` → `UNKNOWN_HASH = "unknown"` |
| G2 | `gate.py:30-37` | accurate | "An unrunnable gate is a broken goal — a typo, a missing tool — and must stop the loop. A failing gate is work still to do and must continue it." |
| G3 | `gate.py:52-57` | accurate | "Deliberately not a ValueError: ... would otherwise be swallowed by that same handler and silently misrouted" |
| G4 | `gate.py:46-51` | accurate | "there is no way to recompute it correctly — by then the judge has run and the tree may have moved." |
| G5 | `gate.py:67-85` | accurate | "It killed a bare integer with no check that the group still belonged to this goal — the exact unsoundness `filelock` refuses to rely on" |
| G6 | `gate.py:96-104` | accurate | "**Never two skips in a row.** ... a false skip is a correctness bug, a false run costs seconds." |
| G7 | `gate.py:92-94` | accurate | "only when the tree is provably unchanged ... every uncertain path reports changed." |
| G8 | `gate.py:109-110` | accurate | "Anything unequal to the last checkpoint's hash, including the `\"unknown\"` sentinel, runs the gate." |
| G8 | `gate.py:126-128` | accurate | `unchanged = (bool(previous) and UNKNOWN_HASH not in (previous, current_hash) and current_hash == previous)` |
| G9 | `gate.py:176-183` | accurate | "turning fail/fail/pass into fail/skipped/skipped ... never recompute it after the gate has run." |
| G10 | `gate.py:185-188` | accurate | "It can never equal a real digest, nor another `UNKNOWN_HASH`" |
| G10 | `gate.py:190-193` | accurate | the `try: tree_hash.compute(...) except Exception: evaluated = UNKNOWN_HASH` block |
| **G11** | `gate.py:135-142` | **wrong** | off by one — see below |
| G11 | `gate.py:148-157` | accurate | `except subprocess.TimeoutExpired`, `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)`, `proc.wait()  # reap` |
| G12 | `gate.py:13` | accurate | `MAX_OUTPUT = 4000` |
| G12 | `gate.py:168` | accurate | `output = (stdout + stderr)[-MAX_OUTPUT:]` |

**G11 — off by one.** The row claims "the gate child leads its own process
group". The sentence asserting that is at line **134**:

```
134:         # start_new_session=True makes the child the leader of its own
135:         # process group, so a timeout can kill the whole group — including
```

The citation opens at 135, mid-sentence, dropping the clause that names the
mechanism. The mechanism itself (`start_new_session=True,`) is in range at
141, so the claim is still verifiable from the cited window — this is a
cosmetic truncation, not a misdirection. Correct range: `gate.py:134-142`.

## `goal.py` — rows H1–H17

| # | Cited | Verdict | Evidence at the cited lines |
|---|---|---|---|
| H1 | `goal.py:1-6` | accurate | "Nothing here trusts in-memory state." / "survive context loss, session restart, or a /loop firing" |
| H2 | `goal.py:25-44` | accurate | `class GateUnsound(GateRequired)` with the `\| tail` / `\|\| true` examples and "Every other safeguard here is downstream of this one string" |
| H2 | `goal.py:93-120` | accurate | `_assert_sound_gate` — "Refuse a command gate whose exit status is not the work's verdict." |
| H3 | `goal.py:86-90` | accurate | "`&&` is absent deliberately: `a && b` fails when `a` fails" / "`2>&1` is a redirect, not an operator" |
| H4 | `goal.py:96-104` | accurate | "an operator *inside a quoted argument* ... `punctuation_chars=True` is what makes the operators their own tokens." |
| H5 | `goal.py:47-48` | accurate | `"""Raised when goal state is missing or unreadable. Never guess."""` |
| H5 | `goal.py:234-258` | accurate | the `not p.exists()` and `json.JSONDecodeError, OSError` raises |
| H6 | `goal.py:260-277` | accurate | "The elements, not just the containers." / "an exception the skills' error tables never mention" |
| H7 | `goal.py:55-56` | accurate | `class BudgetInvalid` — "a budget that cannot bound it" |
| H7 | `goal.py:195-207` | accurate | "with neither, `budget_exhausted()` can never become True" at `create` |
| H7 | `goal.py:279-288` | accurate | the same refusal at `load` — "the unbounded loop create() refuses to build" |
| H8 | `goal.py:21-22` | accurate | `class GateRequired` — "created without a termination criterion" |
| H8 | `goal.py:182-188` | accurate | "A loop with no termination criterion is an infinite loop." |
| H9 | `goal.py:51-52` | accurate | `class GateNotPassed` |
| H9 | `goal.py:348-353` | accurate | "Budget exhaustion is reported as a partial result, never as success." |
| **H10** | `goal.py:311-314` | accurate | the `checkpoint` guard — `raise GoalClosed("cannot checkpoint: ...")` |
| H10 | `goal.py:344-347` | accurate | the `complete` guard |
| H10 | `goal.py:362-365` | **wrong** | the silent-gate evidence fallback, not a guard — see below |
| H10 | `goal.py:429-441` | **wrong** | `_reopen_locked`'s budget arithmetic — see below |
| H11 | `goal.py:159-177` | accurate | "either entirely the old state or entirely the new one, never half of each" + `os.replace(tmp, target)` |
| H12 | `goal.py:296-305` | accurate | "two concurrent turns would otherwise each read turn N and both write N+1" |
| H12 | `goal.py:209-214` | accurate | "eight concurrent creates of one title produced five state files" + the `CREATE` lock |
| H12 | `goal.py:463-468` | accurate | the `_with_lock` decorator |
| H13 | `goal.py:139-152` | accurate | "the second `create()` would silently overwrite the first" + the `base-2`/`base-3` loop |
| H14 | `goal.py:123-136` | accurate | "`\w` under Unicode keeps letters and digits in any script" + `return s or "goal"` |
| H15 | `goal.py:73-83` | accurate | "Keep the END of oversized text, matching gate.py's truncation." — and the *both modules* claim holds: `gate.py:168` slices `[-MAX_OUTPUT:]`, both bounds are 4000 (`gate.py:13`, `goal.py:17`) |
| **H16** | `goal.py:381-384` | **wrong** | a blank line and the `_reopen_locked` signature — see below |
| H16 | `goal.py:400-403` | **wrong** | the tail of the budget paragraph and the start of the arg-validation loop |
| **H17** | `goal.py:386-390` | **wrong** | the abandonment-was-terminal rationale, which says nothing about budget |
| H17 | `goal.py:414-422` | **wrong** | `state["status"] = "active"` and the `reopen_history` append |

### H10 — two of four ranges misplaced

The row claims all four terminal-state mutators raise `GoalClosed`. Two
citations land; two do not.

- `362-365` is the evidence fallback inside `_complete_locked`
  (`if not evidence: ... state["gate_evidence"] = _bounded(evidence)`), not
  the `abandon` guard. The abandon guard is at **`goal.py:372-375`**.
- `429-441` spans `_reopen_locked`'s `extra_turns` arithmetic and the
  `_add_subagent_locked` signature; only line 441 (the docstring's "guarded
  the same way as every other mutator") touches the claim. The
  `add_subagent` guard is at **`goal.py:449-452`**.

Corrected: `goal.py:311-314`, `344-347`, `372-375`, `449-452`.

### H16 — both ranges displaced

Neither cited range states the guarantee. `381-384` is a blank line plus the
`_reopen_locked` signature; `400-403` is the end of the budget paragraph and
the start of the argument-validation loop. The claim's prose is verbatim at
**`goal.py:392-394`** ("A completed goal has a passing gate on record, and
reopening it would let that evidence stand for later work it never judged"),
and it is enforced at **`goal.py:410-413`**.

### H17 — both ranges displaced

`386-390` is the rationale for why abandonment used to be terminal — it makes
no budget claim at all. The "budget is not refreshed implicitly" text is at
**`goal.py:396-400`**. `414-422` shows `reopen_history` recording the grant
but not the "N more than used" semantics the row asserts; those are at
**`goal.py:424-432`**, where the comment reads "Five more turns" means five
more than have been used and the code is
`state["budget"]["max_turns"] = state["used"]["turns"] + extra_turns`.

Corrected: `goal.py:396-400`, `424-432`.

## Method

Three checkers read the current files independently — one over `gate.py`
G1–G12, two splitting `goal.py` H1–H9 and H10–H17 — each instructed to open
the exact cited range, quote what is actually there, and judge substance as
well as location. Every **wrong** verdict, plus every *accurate* verdict past
`goal.py:352` (the region the same commit shifted), was then re-opened and
confirmed directly rather than taken on the checkers' word.
