# Task 1 report: process-owned goal locks

Status: DONE_WITH_CONCERNS

Commit: `58906cd` — `fix(horizon): serialize goal writes with process-owned locks`

## Implementation

- Added `filelock.goal_locked(target, timeout=10.0)` using a persistent `.<target>.flock` inode and nonblocking exclusive `flock` retries on Darwin/Linux. It never reclaims or unlinks an aged goal lock. A holder crash releases the kernel lock; the inode remains. Permission/open errors propagate before entry, and the descriptor closes on every exit path.
- Added `filelock.state_supported()`. On other platforms, `goal_locked` falls back to the existing `locked` primitive for legacy goal operations.
- Routed goal creation, checkpoint, review recording, and the shared wrapper for complete/abandon/reopen/add_subagent through `goal_locked`. Refine's calls to `locked` are unchanged.

Changed files: `harness/filelock.py`, `harness/goal.py`, `tests/test_filelock.py`, `tests/test_concurrency.py`.

## TDD and verification

All commands below ran in the isolated worktree with this environment:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages'
```

Focused command: `python3 -m pytest tests/test_filelock.py tests/test_concurrency.py -q -p no:cacheprovider --tb=short`.

1. Baseline before edits: `9 passed in 1.08s`.
2. After adding permission and real-process stale/killed-holder regressions, before production code: `2 failed, 9 passed in 1.13s`. Expected failures: `AttributeError: module 'filelock' has no attribute 'goal_locked'` and missing `state_supported`.
3. After adding the strict primitive and correcting the subprocess test fixture: `11 passed in 1.29s`.
4. After adding goal call-site denial tests and a real second-process create-lock test, before changing `goal.py`: `8 failed, 11 passed in 1.61s`. The denied lock allowed creation/checkpoint/abandon/add_subagent to mutate; review/complete/reopen proceeded into their ordinary lifecycle validation; the second process created a goal while `CREATE` was held.
5. After routing goal call sites: `19 passed in 1.65s`.
6. Additional goal/CLI regression command: `python3 -m pytest tests/test_goal.py tests/test_horizon_cli.py -q -p no:cacheprovider --tb=short` → `89 passed in 8.98s`.
7. `git diff --check` passed. Diff was reviewed before commit and contained only the four Task 1 files.

The new process test ages the held lock inode, verifies a waiter times out instead of stealing it, kills the holder, then verifies immediate reacquisition with the same persistent inode. The create-lock process test verifies goal creation cannot persist until the holder releases `CREATE`. Denied-open tests verify all current goal mutation entry points fail closed without changing goal JSON.

## Staged dependencies and concerns

- No state-mode creation path exists in this baseline. Task 3 must use `state_supported()` to refuse state-mode creation on untested platforms. Legacy operations already use the specified fallback.
- Existing legacy review/completion snapshot hashing remains inside the goal critical section. The controller explicitly assigned moving those hash checks outside the lock to Task 6.
- This task did not change the active installation or stop writers. The isolated checkout is ready for integration without mixing old/new writers against one goal directory.
