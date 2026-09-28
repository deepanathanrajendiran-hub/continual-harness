### Spec Compliance

- ❌ Issues found: `harness/goal.py:352` still decodes saved goals with default `json.loads`, which accepts duplicate object keys and non-finite JSON constants. The shared JSON contract requires both to be rejected. A state goal can therefore load a malformed record after one value silently replaces another.
- ✅ Explicit opt-in and legacy preservation: `harness/goal.py:300-336` adds a keyword-only mode, keeps the conversation creation path, and checks platform support before asking for the goals directory. `harness/goal.py:319-333` previews a maximum-length attempt ID and verdict reservations before the CREATE lock, then saves the state goal once at revision 0.
- ✅ State consistency and revisions: `harness/goal.py:267-286` checks sequential attempt turns, `used.turns`, and terminal/checkpoint turn correspondence; `harness/goal.py:398-401` translates execution validation failures to `GoalStateError`. `harness/goal.py:654-667` checks the saved revision, copies the candidate, increments once, validates, and atomically saves.
- ✅ Shared summary and isolated import: `harness/goal.py:670-688` adds mode, revision, active attempt, turn unit, and next action to the legacy summary fields. `.claude/harness/bin/task_state.py:1` makes the new import available to bin-only callers, with a subprocess regression in `tests/test_goal.py`.
- ⚠️ Integration to verify in Task 7: the unchanged `harness/cli.py:81-91` still has its own `status` formatter, so CLI status does not yet expose the new summary fields. The Task 3 brief lists only `goal.py` and its tests for modification; the controller should confirm the planned CLI task switches this call site to `goal.summary`.

### Strengths

- `harness/goal.py:319-333` keeps packet feasibility outside the creation lock and assigns the unique slug inside it, while `tests/test_goal.py` checks oversized immutable fields and counts the initial save.
- `harness/goal.py:267-286` adds cross-record validation beyond the execution schema. The new tests exercise malformed attempts, turn/checkpoint mismatches, revision conflicts, and preservation of the old JSON after failed atomic replacement.
- `.claude/harness/bin/task_state.py:1` addresses the real symlink import layout; the isolated subprocess test supplies only the legacy bin directory on `PYTHONPATH` from an unrelated working directory.

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

- `harness/goal.py:352-354`: Use a strict JSON decoder for saved goals that rejects duplicate keys and non-finite numbers, and translate those parse errors to `GoalStateError`. `task_state.read_update` already applies these hooks to updates (`harness/task_state.py:280-309`); the goal loader currently silently normalizes malformed JSON, contrary to the binding contract. Add a focused goal-load regression for duplicate keys and `NaN`/`Infinity`.

#### Minor (Nice to Have)

- `harness/goal.py:661-665`: `candidate["execution"]["revision"]` is accessed before the validation `try`, so a missing or non-object execution block raises a raw `KeyError` or `TypeError` instead of `GoalStateError`. Move that access into the guarded validation path. This does not write a bad candidate, but weakens the helper's malformed-input error contract.

### Assessment

**Task quality:** Needs fixes.

**Reasoning:** The mode, packet-preview, revision, consistency, and legacy-import paths match the requested shape, and the reported focused tests passed cleanly. Strict goal JSON decoding remains a binding malformed-state requirement. I checked only the named `task_state` packet/decoder dependency and the `cli.status` call site outside the diff; no test rerun was needed because the issues are evident from those code paths.
