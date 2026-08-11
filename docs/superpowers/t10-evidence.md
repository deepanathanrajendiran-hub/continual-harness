# The harness's stated guarantees

Every guarantee the two core harness modules state in their own docstrings
and comments, using the words *never* / *always* / *cannot* / *refuses*.
Collected by reading the source; each line cites `file:line`.

## `gate.py` — gate execution

| # | Guarantee | Where |
|---|---|---|
| G1 | The `"unknown"` hash sentinel **must never compare equal to anything, including itself** — two unreadable turns in a row would otherwise look like an unchanged tree and skip the gate, "the one direction this module may not fail in". | `gate.py:23-27` |
| G2 | An unrunnable gate is a broken goal and must stop the loop; a failing gate is work still to do and must continue it. Conflating them spends the whole turn budget re-running a command **that was never going to run**. | `gate.py:30-37` |
| G3 | `CoverageGate` is deliberately **not** a `ValueError`: a coincidental `ValueError` from elsewhere in the call chain would otherwise be swallowed by the same handler and silently misrouted. | `gate.py:52-57` |
| G4 | `CoverageGate.tree_hash` carries the digest the work was evaluated against, because **there is no way to recompute it correctly** once the judge has run and the tree has moved. | `gate.py:46-51` |
| G5 | The orphan reaper was removed, not repaired: it killed a bare pid group with no check that it still belonged to this goal — the exact unsoundness `filelock` **refuses to rely on**. The timeout path, which holds a real handle on what it kills, is now the only thing here that signals anyone. | `gate.py:67-85` |
| G6 | **Never two skips in a row.** Skip is an absorbing state; one forced run breaks the cycle. Stated asymmetry: a false skip is a correctness bug, a false run costs seconds. | `gate.py:96-104` |
| G7 | Skipping happens **only** when the tree is provably unchanged; every uncertain path in `tree_hash` reports *changed*. | `gate.py:92-94` |
| G8 | Anything unequal to the last checkpoint's hash — including the `"unknown"` sentinel — runs the gate. | `gate.py:109-110`, enforced at `gate.py:126-128` |
| G9 | The hash returned by `run_gate_at` is the one the gate actually judged; pass it straight to `goal.checkpoint()` and **never recompute it after the gate has run**. Getting this backwards turns fail/fail/pass into fail/skipped/skipped. | `gate.py:176-183` |
| G10 | On an unreadable watch tree the hash **cannot** be computed, so the sentinel is returned rather than losing the checkpoint entirely; it can **never** equal a real digest, so the next turn is guaranteed to run the gate. | `gate.py:185-188`, `gate.py:190-193` |
| G11 | The gate child leads its own process group, so a timeout kills the whole group — grandchildren included — not just the shell. | `gate.py:135-142`, `gate.py:148-157` |
| G12 | Output is bounded to `MAX_OUTPUT` (4000 chars), keeping the **tail**. | `gate.py:13`, `gate.py:168` |

## `goal.py` — goal state

| # | Guarantee | Where |
|---|---|---|
| H1 | Nothing here trusts in-memory state; checkpointing after every increment is what lets work survive context loss, restart, or a `/loop` firing. | `goal.py:1-6` |
| H2 | A gate whose exit status is not the work's verdict is **refused** (`GateUnsound`): `\| tail`, `; echo`, `\|\| true` are "always 0" and every other safeguard is downstream of this one string. | `goal.py:25-44`, `goal.py:93-120` |
| H3 | `&&` is deliberately **not** an exit-masking operator — `a && b` fails when `a` fails — and `2>&1` is a redirect that shlex never yields as a bare token. | `goal.py:86-90` |
| H4 | The soundness check tokenises with `shlex(punctuation_chars=True)`, so an operator inside a quoted argument (`sh -o pipefail -c '…'`) is not mistaken for a top-level one, and `-q;` cannot hide a `;` inside a word. | `goal.py:96-104` |
| H5 | Goal state that is missing or unreadable raises `GoalStateError` — **never guess**. | `goal.py:47-48`, `goal.py:234-258` |
| H6 | Element-level validation, not just container types: a malformed checkpoint raises `GoalStateError` rather than a bare `KeyError` the skills' error tables never mention. | `goal.py:260-277` |
| H7 | A budget that **cannot** bound is refused at `create` *and* at `load` — with neither `max_turns` nor `max_minutes`, `budget_exhausted()` can **never** become True, the unbounded loop a gate exists to prevent. | `goal.py:55-56`, `goal.py:195-207`, `goal.py:279-288` |
| H8 | A goal cannot be created without a termination criterion. | `goal.py:21-22`, `goal.py:182-188` |
| H9 | Completion is refused unless the **last** checkpoint's gate is `pass`; budget exhaustion is reported as a partial result, **never as success**. | `goal.py:51-52`, `goal.py:348-353` |
| H10 | Every terminal-state mutator (`checkpoint`, `complete`, `abandon`, `add_subagent`) raises `GoalClosed` when the goal is not active; writing the state file any other way skips that guard. | `goal.py:311-314`, `344-347`, `362-365`, `429-441` |
| H11 | Writes are atomic (write-beside-then-rename): the file is either entirely the old state or entirely the new one, **never half of each**, because a torn write loses the goal. | `goal.py:159-177` |
| H12 | Every mutator is a read-modify-write and is serialised under a file lock — two concurrent turns would each read turn N and both write N+1, losing one turn's record entirely. Includes `create`, which was the one left unlocked (eight concurrent creates of one title produced five files). | `goal.py:296-305`, `goal.py:209-214`, `goal.py:463-468` |
| H13 | Two goals with the same title must not share a state file; `_unique_slug` suffixes rather than letting the second `create()` silently overwrite the first. | `goal.py:139-152` |
| H14 | Slugs preserve non-Latin scripts (`\w` under Unicode), so a non-ASCII goal title is still nameable and resumable; an all-punctuation title becomes `"goal"`, never a hidden `.json`. | `goal.py:123-136` |
| H15 | Truncation keeps the **end** of oversized text in both modules — a failing gate's diagnosis and a coverage judge's verdict both come last, and the two modules disagreeing about direction is worse than either choice. | `goal.py:73-83` |
| H16 | Reopen only works from `abandoned`. A completed goal's passing gate must **never** stand as evidence for later work it did not judge. | `goal.py:381-384`, `goal.py:400-403` |
| H17 | Reopening does **not** refresh the budget implicitly; `extra_turns` on a minutes-only goal means "N more than used", not a grant silently dropped while `reopen_history` records it as honoured. | `goal.py:386-390`, `goal.py:414-422` |
