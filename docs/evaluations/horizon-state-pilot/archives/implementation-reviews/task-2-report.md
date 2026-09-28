# Task 2 report: validated task state and bounded packets

## Status

Implemented in commit `6fd53cf` (`feat(horizon): validate compact task state and worker packets`). The module is intentionally standalone: it does not import `goal` or `steps`.

## Implementation

- Added `harness/task_state.py` with canonical JSON serialization, strict state/update schemas, immutable lifecycle field checks, explicit `set`/`upsert`/`archive` operations, and non-mutating candidate/audit construction.
- Added strict update-file decoding: 64 KiB read bound, UTF-8 parsing, duplicate-key rejection, and rejection of non-finite JSON values.
- Added evidence reference validation with strict resolution under the project, special-file rejection, streaming SHA-256 verification, and derived freshness diagnostics. `unknown` snapshots are always `unverified`.
- Added state execution validation, runtime-bound worker procedure digests using the in-checkout Horizon skill, and 24 KiB packet construction. Packet construction retains all active entries and original objective/gate/watch paths; verdict reservations and freshness labels are counted before accepting a reserved packet.
- Added focused tests covering archival preservation, malformed updates, JSON parser failures, UTF-8 boundaries, regular/missing/symlink evidence, evidence categories, stale historical state, unknown snapshots, packet limits and reservation accounting, and non-mutation after a rejected later operation.

## RED evidence

All commands ran from `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state` with `PYTHONDONTWRITEBYTECODE=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, and the cached pytest `PYTHONPATH` from the shared contract.

1. `python3 -m pytest tests/test_task_state.py -q -p no:cacheprovider`
   - Initial supplied preservation test: `1 failed`; `ModuleNotFoundError: No module named 'task_state'`.
2. The same command after adding the full schema/evidence/packet tests against the archive-only implementation:
   - `14 failed, 4 passed`; failures were missing validation/parser/packet APIs and unsupported upserts.
3. The same command after adding the unknown-snapshot regression:
   - `1 failed, 20 passed`; expected `unverified`, got `stale`.
4. The same command after adding reservation accounting:
   - `1 failed, 21 passed`; a 23,000-byte objective fitted only because absent verdicts had not been reserved.

## GREEN evidence

1. Initial archival merge implementation: `1 passed`.
2. Full standalone suite before the final edge cases: `18 passed`.
3. Final focused command:

   `python3 -m pytest tests/test_task_state.py -q -p no:cacheprovider`

   Result: `23 passed in 0.03s`.
4. Direct checks run with the final suite:

   `python3 -m py_compile harness/task_state.py`

   `rg -n "^import (goal|steps)|^from (goal|steps)" harness/task_state.py || true`

   `git diff --check`

   All succeeded; the import-direction scan produced no matches.

## Changed files

- `harness/task_state.py`
- `tests/test_task_state.py`

## Self-review and concerns

- Confirmed merges deep-copy before applying operations and validate both input state and final candidate, so rejected updates do not alter accepted state.
- Confirmed packet overflow raises rather than truncating objective, gate, watch paths, or entries.
- Confirmed evidence inspection derives warnings in separate data and never rewrites persisted entries.
- The legacy `.claude/harness/bin/task_state.py` symlink and isolated runtime import regression are deliberately not changed here; they are assigned to Task 3 in the integration ledger.
- Per controller direction, the full repository baseline is deferred to Task 9. This task is a new standalone module, so no existing production module is directly affected.

## Fix round 1/5 (review of `6fd53cf`)

### RED

After adding regressions for the scoped review findings, ran:

`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_task_state.py -q -p no:cacheprovider`

Result: `4 failed, 23 passed in 0.06s`.

- `validate_execution` accepted `schema_version=True` and did not enforce malformed, duplicate, or active attempt lifecycle records.
- `merge_update` accepted `update.schema_version=True` and incorrectly treated `set summary` plus entry ID `summary` as contradictory.
- Reserved packet measurement replaced checkpoint/review records wholesale, missing returned metadata and accepting an oversized packet.
- The overflow-float assertion was in the same regression test; `1e999` was covered by the correction to `read_update`'s float parser.

### Implementation and GREEN

- Added exact attempt record, reference, worker, gate-process, and pending-reference validation plus the one-nonterminal/active-attempt invariant. Event and result payload contents remain open where the shared contract leaves them open.
- Made execution and update schema versions reject booleans and other non-integer values.
- Added `parse_float` finite checking so `1e999` is rejected along with literal non-finite constants.
- Separated the operation field and entry-ID conflict namespaces.
- Made packet construction first enforce the actual returned packet size, then measure a metadata-preserving reserved copy that replaces only verdict excerpts.

Final verification command was the same focused pytest invocation above.

Result: `27 passed in 0.03s`.

Additional checks:

`PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile harness/task_state.py`

`git diff --check`

Both succeeded. The full suite remains deferred to Task 9 per controller direction.

## Fix round 2/5 (review of `5288f1c`)

### RED

Added one focused regression covering a list-valued attempt `status` and a list-valued worker `runtime`, then ran:

`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_task_state.py -q -p no:cacheprovider`

Result: `1 failed, 27 passed in 0.05s`. The status case raised `TypeError: cannot use 'list' as a set element` instead of `StateError`.

### Implementation and GREEN

- Added explicit string checks before testing attempt statuses and worker runtimes for membership in their allowed sets.
- The regression now verifies both malformed JSON shapes raise `StateError` with the expected field context.

Final focused verification used the same pytest command.

Result: `28 passed in 0.04s`.

Also ran:

`PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile harness/task_state.py`

`git diff --check`

Both succeeded. No full-suite run was performed, per controller direction.
