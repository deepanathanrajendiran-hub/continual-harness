# Task 6 implementation report

## Implementation

- Added `steps.recover(...)` with revision and attempt checks, idempotent replay, contradictory replay rejection, content-addressed evidence, outside-lock snapshot hashing, failed recovery checkpoints, preserved worker edits/task entries, and no budget refund.
- Recovery accepts `not-started` only for an unbound reserved attempt with no gate record. Attached and finishing attempts require `stopped`. An accepted attempt cannot be recovered, and recovery does not compare the saved procedure digest, so interrupted older-procedure attempts remain recoverable.
- A finishing recovery first acquires the attempt runner lock with zero wait. If a finish runner owns it, recovery returns `StepBusy` without changing goal state.
- Replaced unsafe English keyword inference with the controller-approved plain-text assertion contract for finishing evidence:
  - exactly one standalone, case-insensitive `gate-state: stopped|not-started` header;
  - at least 40 UTF-8 bytes of supporting coordinator observation prose after recognized headers are removed;
  - if a saved gate record exists, `gate-state` must be `stopped` and exactly one `gate-pid` header must match the saved diagnostic PID;
  - without a saved gate record, `not-started` is allowed and any `gate-pid` header is rejected;
  - `stopped` asserts the gate and its full process group/descendants are stopped. The PID only binds the coordinator assertion to the saved diagnostic record; Python does not probe or signal it.
- Added `_persist_mutation_locked`, `_snapshot_transaction`, `_apply_review`, and `_apply_completion`. Review/completion fingerprints are computed before the goal lock, then canonical saved state is compared under the lock before applying the mutation.
- Routed state-mode review, completion, abandon, reopen, and subagent writes through one revision increment and idle-attempt guards. State-mode legacy checkpoint calls are refused, and `cli.check` refuses before running a gate.
- Kept legacy conversation-mode persistence and completion/review semantics intact.
- Fixed `commit_revision` so malformed candidate execution data is wrapped as `GoalStateError` instead of leaking `KeyError`/`TypeError`.
- Reserved the mandatory recovery next-action size in packet admission. A packet admitted at exactly 24,576 canonical UTF-8 bytes can recover and begin the next attempt without dropping entries or inventing padding.

## Files changed

- `harness/steps.py`
- `harness/goal.py`
- `harness/task_state.py`
- `harness/cli.py`
- `tests/test_horizon_steps.py`
- `tests/test_goal.py`
- `tests/test_task_state.py`

The small `harness/cli.py` change is the pre-gate state-mode refusal explicitly required by Task 6's Interfaces paragraph. No Task 7 step-command integration was added.

## TDD evidence

### Baseline

Command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages python3 -m pytest tests/test_horizon_steps.py tests/test_goal.py tests/test_task_state.py -q -p no:cacheprovider --tb=short
```

Output before new tests:

```text
201 passed in 9.16s
```

### RED: recovery, lifecycle, transaction, validation, and packet reservation

The first raw test run also found two test-plumbing errors: a missing test import and a goal directory outside the fixture project. Those were corrected without production edits by importing the module and moving the fixture to the standard excluded `.claude/harness/goals` location.

Corrected RED command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages python3 -m pytest tests/test_horizon_steps.py tests/test_goal.py tests/test_task_state.py -q -p no:cacheprovider --tb=short -k 'recovery or forge_required_review or public_writers or checkpoint_and_cli or mutated_while or revisioned_transactions or malformed_candidate or mandatory_recovery'
```

Relevant output:

```text
14 failed, 2 passed, 201 deselected in 11.21s
```

Expected failures showed: no `steps.recover`; open attempts did not block all public writers; state checkpoint/check did not refuse; completion still hashed under the goal lock (the concurrent mutation could not acquire it); review did not increment the state revision; malformed execution leaked `TypeError`; and the recovered next action expanded an exact reservation from 24,576 to 24,583 bytes. The two passing cases were the pre-existing immutable worker-update protections, confirming a worker already could not write review state.

### RED: explicit finishing liveness assertions

Command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages python3 -m pytest tests/test_horizon_steps.py -q -p no:cacheprovider --tb=short -k 'finishing_recovery'
```

Relevant output before replacing the word-co-occurrence heuristic:

```text
14 failed, 6 passed, 86 deselected in 1.13s
```

The failures proved that prose saying the gate was still running or that its state was unknown could be accepted, and that missing, duplicate, conflicting, or mismatched headers were not rejected.

### GREEN

Focused liveness command after implementation:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages python3 -m pytest tests/test_horizon_steps.py -q -p no:cacheprovider --tb=short -k 'finishing_recovery'
```

Output:

```text
20 passed, 86 deselected in 1.09s
```

Final assigned and adjacent regression command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages python3 -m pytest tests/test_horizon_steps.py tests/test_goal.py tests/test_task_state.py tests/test_horizon_cli.py tests/test_runtime_separation.py -q -p no:cacheprovider --tb=short
```

Output:

```text
288 passed in 20.62s
```

`git diff --check` also completed with no output.

## Covering tests

- Recovery preserves workspace edits and spends the reserved turn.
- Exact replay succeeds without a revision change; changed reason, worker state, or evidence digest is rejected.
- Accepted attempts cannot be recovered.
- Reserved `not-started`, attached `stopped`, and finishing recovery transitions are covered.
- Runner ownership blocks recovery.
- Both known unsafe gate-liveness prose examples are rejected.
- Missing, duplicate, conflicting, mismatched, and header-only gate assertions are rejected; valid saved-gate `stopped` and no-record `not-started` assertions pass.
- Procedure changes do not block recovery.
- Open attempts block checkpoint, review, complete, abandon, and add-subagent; recovery enables abandon/reopen.
- State-mode checkpoint and CLI check refuse before gate execution.
- Review, completion, abandon, reopen, and add-subagent increment revisions exactly once.
- A state mutation during completion hashing causes `RevisionConflict`.
- A failed required review does not satisfy completion; a later passing review does.
- Worker updates cannot forge review state.
- Malformed revision candidates raise `GoalStateError` and preserve saved state.
- Recovery next-action reservation covers the exact 24 KiB boundary and a real next `begin`.
- Legacy command, coverage, review, reopen, CLI, and runtime-separation paths remain covered by the passing suites.

## Self-review

- Re-read the Task 6 brief, integration notes, and shared contracts against the final diff.
- Confirmed recovery does not call `task_state.procedure`, accept a candidate update, clear pending diagnostics, refund a turn, infer process death, or signal a saved PID.
- Confirmed review/completion tree hashing occurs before the strict goal lock and canonical state is rechecked under the lock.
- Confirmed every requested public state writer either refuses the legacy path or persists through `commit_revision` with an idle guard.
- Confirmed packet reservation compares canonical serialized sizes and never drops active entries.
- Confirmed only the seven scoped source/test files are modified before adding this report; the original checkout was not touched.

## Concerns

None. Whole-suite verification remains assigned to Task 9; this task ran its focused files plus the adjacent CLI/runtime regressions affected by the approved guard.
