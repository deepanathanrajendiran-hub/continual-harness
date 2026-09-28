# Task 4 implementation report

**Status:** DONE. Commit `9d32129` (`feat(horizon): reserve durable worker attempts before dispatch`).

Implemented `steps.begin`, `steps.attach`, `steps.report`, and content-addressed blob storage in `harness/steps.py`. `begin` checks for an existing request first, prepares a packet against a loaded snapshot outside the goal lock, saves canonical bytes in a SHA-256 named object, then reloads under the strict goal lock and reserves exactly one turn through `goal.commit_revision`. It refuses changed revisions, snapshots, and procedure digests without charging a turn. The packet includes a project-relative `audit_path` to the goal JSON record; this is added to the packet input only and is not persisted as a goal field.

`attach` records the actual runtime and native worker handle and increments the execution revision once. A repeated binding to the same handle returns the saved/current outcome before checking its old expected revision; a different handle conflicts. It verifies saved packet identity and procedure digest. It permits project edits after reservation because the native worker may run before its handle is attached. Neither function launches a worker.

The shared fixture in `tests/conftest.py` exercises both Codex and Claude runtime markers in an isolated project whose path ends in a space. New tests cover reservation and binding replay, one-turn accounting, content-addressed packet references, packet corruption or loss, busy/spent/expired admission, handle conflicts, changed procedure, stale snapshot and revision, replay after closure, and attaching after worker edits. `tests/test_tree_hash.py` verifies that goal bookkeeping does not change the project hash.

## TDD evidence

- Initial RED: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_horizon_steps.py tests/test_tree_hash.py -q -p no:cacheprovider --tb=short` produced `24 failed, 12 passed in 0.78s`; the failures were missing `steps.begin` and `steps.store_blob`.
- Initial GREEN with implementation: the same focused command produced `36 passed in 1.50s`.
- Worker-edit timing RED: `python3 -m pytest tests/test_horizon_steps.py -q -p no:cacheprovider --tb=short -k attach_accepts_worker_edits` with the same environment produced `2 failed, 22 deselected`; both failures were `RevisionConflict: Project snapshot changed since reservation`. Removing the attach-time snapshot check resolved the issue while retaining begin-time validation.
- Audit path RED: the focused `-k content_addressed_packet` run produced `2 failed, 22 deselected`; both packets had `audit_path: None`. Supplying the ephemeral project-relative goal path resolved it.
- Final GREEN: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_horizon_steps.py tests/test_tree_hash.py tests/test_goal.py tests/test_task_state.py -q -p no:cacheprovider --tb=short` produced `157 passed in 2.22s`. `git diff --check` and `git diff --cached --check` exited 0.

## Files changed

- `harness/steps.py` (new)
- `tests/conftest.py` (new)
- `tests/test_horizon_steps.py` (new)
- `tests/test_tree_hash.py` (extended)

## Self-review and integration notes

Reviewed the staged diff against the Task 4 brief and shared contracts. The content-addressed blob reader verifies the digest and project-relative path; request replay checks the immutable packet before returning it; reservations are not refunded. The final tests covered both runtimes. Task 5 owns finishing and the separately recorded future packet growth fix; Task 6 owns recovery, and Task 7 owns CLI wiring. The full suite was intentionally left for Task 9 per the assignment. Task 4's terminal replay test manually supplies a saved attempt result to check `report`'s overlay behavior; persistence of the real terminal result and replay after actual completion are integration checks for Tasks 5–6. There are no remaining Task 4 concerns.

## Fix round 1 — commit `2aebdda`

Review found that `attach` derived a lock path before validating the slug. A path-like slug could create a directory and lock file outside the goal directory before rejection. The controller also found that the attempt-ID pattern was incorrectly applied to goal slugs, rejecting Unicode and leading-underscore slugs returned by `goal.slugify`. Added a separate Unicode-aware, single-component slug validator for `_state`, `store_blob`, and `attach`; `attach` now calls it before `goal._path` or `goal_locked`. The request and attempt IDs retain their original ASCII/length contract.

RED 1: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_horizon_steps.py -q -p no:cacheprovider --tb=short -k path_like_slug` produced `2 failed, 26 deselected in 0.09s`. Both failed at `assert not escaped.exists()`: the escaped directory had been created by lock acquisition.

RED 2: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_horizon_steps.py -q -p no:cacheprovider --tb=short -k created_unicode_and_underscore` produced `4 failed, 28 deselected in 0.14s`. All four failed with `steps.StepError: slug must match [A-Za-z0-9][A-Za-z0-9_-]{0,63}` before reservation.

GREEN: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_horizon_steps.py -q -p no:cacheprovider --tb=short -k 'path_like_slug or created_unicode_and_underscore'` produced `6 passed, 26 deselected in 0.24s`. The assigned covering command, `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_horizon_steps.py tests/test_tree_hash.py -q -p no:cacheprovider --tb=short`, produced `46 passed in 1.66s`. `git diff --check` exited 0.

Fix files: `harness/steps.py`, `tests/test_horizon_steps.py`. Self-review confirmed slug validation happens before every slug-derived write or lock path and accepts the current `goal.slugify` alphabet without imposing the attempt-ID length limit. Terminal result persistence remains assigned to Tasks 5–6.
