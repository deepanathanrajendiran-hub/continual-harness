# Task 5 implementation report

Status: DONE. Implemented `steps.finish`, gate spawn callbacks and owned-process cleanup, and packet capacity reservations. The work is limited to Task 5 and its authorized packet integration boundary. Commit: `fd9c0c5 feat(horizon): atomically finish attempts with replay-safe verification`. The worktree is clean after the commit; this report is retained at the requested path under the repository's ignored `.superpowers/` directory.

## Changes

- `harness/steps.py`: `finish` takes a nonblocking per-attempt runner lock, validates the attached attempt, canonical update and coordinator terminal evidence, verifies the saved packet and current procedure, merges the candidate without changing accepted task state, and checks a candidate packet with the real project-relative `audit_path` before starting the gate. It persists the update/candidate/audit/evidence objects and a finishing nonce, records spawn diagnostics in a short revisioned save, then writes the task, audit event, checkpoint and accepted result in one terminal `goal.commit_revision`. Replays compare canonical update SHA-256 and return the original `result.checkpoint` and exit code; `goal.summary.last_checkpoint` remains current. The reserved turn is charged only by `begin`. Deadline expiry does not prevent finishing an already attached attempt. Gate failures, skips, coverage awaiting review, timeouts and unknown fingerprints still close the attempt with an honest failed checkpoint. The optional `force` runs an unchanged command gate.
- `harness/gate.py`: `run_gate` and `run_gate_at` accept keyword-only `on_spawn`, preserving positional arguments and return types. Callback errors and timeouts stop and reap only the current call's unreaped `Popen` group. The process group is the child PID because `start_new_session=True`; no stored PID is signaled. `run_gate_at` attaches the pre-gate tree hash to `GateUnrunnable` as it already did for coverage exceptions.
- `harness/task_state.py`: malformed array values for entry kind and set field now raise `StateError`. Packet checkpoint/review projections contain bounded 2 KiB verdict excerpts with durable record references; full records remain in goal/audit files. Freshness reasons are bounded to 256 serialized bytes, carry truncation flags and entry references, and are reserved in both task and snapshot copies. Reservation measurement includes future checkpoint/review shapes and 64-character snapshot hashes. It uses the longer `false` spelling for exact-boundary `truncated` reservations. The returned packet always contains actual verdict/review text; padding is used only on a measurement copy. The public packet limit, function signatures and top-level packet keys did not change.
- Tests cover real gate replay/counter bytes, terminal state and revisions, malformed or oversized updates, missing/large terminal evidence, command failure/skip/force, timeout, unknown hash, coverage review, deadline, historical provenance after a gate edit, process metadata, ownership contention, callback failure cleanup, and future packet growth.

## TDD evidence

Test environment for all commands below: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages`. Commands also used `-p no:cacheprovider --tb=short` where shown; the initial specified RED run omitted `--tb=short`.

| RED command | Observed failure before implementation | GREEN verification |
| --- | --- | --- |
| `python3 -m pytest tests/test_horizon_steps.py tests/test_gate.py -q -p no:cacheprovider` | `2 failed, 54 passed`; both new finish cases raised `AttributeError: module 'steps' has no attribute 'finish'`. | First focused finish/callback run: `3 passed in 0.21s`. |
| `python3 -m pytest tests/test_gate.py::test_spawn_callback_failure_reaps_its_owned_child -q -p no:cacheprovider` | `TypeError: run_gate() got an unexpected keyword argument 'on_spawn'`. | Included in final 135-pass focused run. |
| `python3 -m pytest tests/test_horizon_steps.py -q -p no:cacheprovider --tb=short` | `6 failed, 50 passed`: malformed set field/entry kind leaked `TypeError`; a gate-edit test initially called `goal.complete` without its required `gate_output` argument. | Validator guards and the test call were corrected; included in final run. |
| `python3 -m pytest tests/test_gate.py::test_unrunnable_gate_carries_pre_gate_hash -q -p no:cacheprovider --tb=short` | `AttributeError: 'GateUnrunnable' object has no attribute 'tree_hash'`. | Included in final run. |
| `python3 -m pytest tests/test_task_state.py::test_reserved_packet_covers_future_checkpoint_and_review tests/test_task_state.py::test_reserved_packet_covers_future_missing_evidence_reasons -q -p no:cacheprovider --tb=short` | Future verdict packet was 7471 bytes versus a 4974-byte reservation. The missing-evidence test was sharpened to compare duplicated task/snapshot annotations and then failed at 642 versus 572 bytes. | Included in final run. |
| `python3 -m pytest tests/test_horizon_steps.py::test_fast_gate_passes_even_if_spawn_recording_is_delayed -q -p no:cacheprovider --tb=short` | Both runtimes returned exit code 2 instead of 0; `os.getpgid(proc.pid)` lost the race against an exited fast child. | `proc.pid` is recorded as the new-session group; focused run `4 passed in 0.58s` also covered packet boundaries and owned cleanup. |
| `python3 -m pytest tests/test_gate.py::test_callback_failure_kills_owned_group_after_shell_exits -q -p no:cacheprovider --tb=short` | The exited shell made the old poll-before-signal helper skip its still-live group: `owned process group survived callback failure`. | After changing the helper, direct group-liveness probing returned `PermissionError` in this host sandbox, so the regression was made deterministic with a live owned `Popen` and a `killpg` spy. It verifies signaling the owned group before `wait`, and the existing real timeout process-tree tests passed (`2 passed in 6.37s`). No stored PID path is used. |
| `python3 -m pytest tests/test_horizon_steps.py::test_unknown_gate_hash_saves_failed_checkpoint tests/test_horizon_steps.py::test_finish_replay_keeps_original_checkpoint_after_coverage_review -q -p no:cacheprovider --tb=short` | The unknown-hash cases returned exit code 0 instead of 2; later-review replay cases already passed. | Unknown hashes now save a failed checkpoint with exit code 2; focused rerun `2 passed in 0.12s`, then final run. |
| `python3 -m pytest tests/test_task_state.py::test_freshness_reservation_covers_longer_untruncated_boolean -q -p no:cacheprovider --tb=short` | Duplicated annotations were 1043 bytes versus a 1041-byte reservation: `false` is one byte longer than `true` in each copy. | Reservation uses the longer form; focused run `5 passed in 0.35s` with actual verdict/review content and historical replay cases. |
| `python3 -m pytest tests/test_horizon_steps.py::test_next_packet_keeps_actual_gate_and_review_verdicts -q -p no:cacheprovider --tb=short` | Both runtimes returned synthetic `\\x00` padding instead of `verified-output`. | Returned packet now contains `verified-output` and the actual review text; focused run `5 passed in 0.35s`, then final run. |
| `python3 -m pytest tests/test_task_state.py::test_truncated_freshness_reasons_point_to_durable_entry -q -p no:cacheprovider --tb=short` | `KeyError: 'freshness_reasons_record'`. | Entry and snapshot annotations now point to `execution.task.entries[id]` under `audit_path`; final run passed. |
| `python3 -m pytest tests/test_horizon_steps.py::test_finish_keeps_spawn_metadata_as_terminal_diagnostics -q -p no:cacheprovider --tb=short` | Both runtimes saw `gate_process is None`. | Terminal attempt retains four diagnostic fields; `2 passed in 0.19s`. |
| `python3 -m pytest tests/test_horizon_steps.py::test_terminal_evidence_can_exceed_worker_update_limit -q -p no:cacheprovider --tb=short` | Both runtimes raised the unsupported `worker terminal evidence must ... fit 65536 bytes` error. | Only worker update JSON has that limit; terminal evidence is stored verbatim, and the final focused run passed. |

Final verification: `python3 -m pytest tests/test_horizon_steps.py tests/test_gate.py tests/test_task_state.py -q -p no:cacheprovider --tb=short` returned `135 passed in 16.22s`. `python3 -m pytest tests/test_goal.py -q -p no:cacheprovider --tb=short` returned `89 passed in 0.90s`. `git diff --check` was clean. A probe including `tests/test_state_concurrency.py` reported that file does not yet exist (Task 9); `tests/test_goal.py` was rerun alone successfully. Whole-suite verification belongs to Task 9.

## Self-review and concerns

Checked the six-file diff, Python compilation, duplicate top-level definitions and terminal replay state. The initial real owned-group-after-exit probe was limited by this host's `PermissionError` for direct group-liveness checks; the deterministic callback test verifies that the live `Popen` group is signaled, and existing timeout process-tree tests exercise real cleanup. The touched `task_state.py` still contains Task 2's duplicate unbound regex compilations and repeated `_KINDS`; they have no bearing on finish, and were left for separate triage. Packet format choices above should be reflected in Task 8 runtime documentation: latest checkpoint/review are compact projections, freshness reasons may be truncated, and `audit_path` plus record references locate durable details.

## Fix round 1: complete verification excerpt allowance

Fix commit: `422f3a4 fix(horizon): bound complete verification excerpts`.

Review found that the nested verdict could consume the full 2,048-byte allowance before the checkpoint/review envelope was added. `_packet_excerpt` now accepts the compact envelope used by checkpoint/review projections and measures the complete serialized object during its binary search. `_latest_checkpoint`, `_latest_review`, and future-verdict reservation use this envelope-aware allowance. Returned packets still carry actual bounded gate/review text; only the measurement copy contains reservation padding. No public signature, packet key, or packet-size limit changed.

RED, long complete excerpts:

`python3 -m pytest tests/test_task_state.py::test_packet_bounds_verdict_metadata_and_points_to_durable_records -q -p no:cacheprovider --tb=short`

Result: `1 failed in 0.03s`; checkpoint serialization was `2162 <= 2048` (reviewer's separate probe measured the review at 2,164 bytes).

RED, exact-boundary checkpoint and review:

`python3 -m pytest tests/test_task_state.py::test_complete_verification_excerpt_exact_boundary -q -p no:cacheprovider --tb=short`

Result: `2 failed in 0.04s`; both parameterizations raised `TypeError: _packet_excerpt() got an unexpected keyword argument 'envelope'` before the envelope-aware implementation existed.

GREEN, both long and exact-boundary cases:

`python3 -m pytest tests/test_task_state.py::test_packet_bounds_verdict_metadata_and_points_to_durable_records tests/test_task_state.py::test_complete_verification_excerpt_exact_boundary -q -p no:cacheprovider --tb=short`

Result: `3 passed in 0.03s`. The long checkpoint and review objects are at most 2,048 serialized bytes; the maximal-metadata checkpoint and review boundary cases each serialize to exactly 2,048 bytes. The future reservation test additionally asserts both complete reserved projections remain within the allowance.

Focused integration verification:

`python3 -m pytest tests/test_task_state.py tests/test_horizon_steps.py -q -p no:cacheprovider --tb=short`

Result: `112 passed in 7.69s`. `git diff --check` was clean and the two changed Python files compiled successfully. Self-review confirmed the change is limited to complete excerpt accounting and preserves the real-excerpt/reserved-copy behavior. The duplicate-regex/repeated-`_KINDS` minor remains in the ledger; Task 6 recovery packet growth remains outside this fix.
