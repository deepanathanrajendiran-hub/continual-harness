# Task 9 implementation report

Status: DONE. The state-mode concurrency and interruption matrix is covered by
real process races, boundary handshakes, public protocol assertions, and the
existing strict schema/recovery tests. One protocol defect was reproduced and
fixed: failure to persist a spawned gate's diagnostic record was being converted
into an accepted terminal update after the owned child had been reaped.

Base: `c95f1ea451c4bfea41150c18640b8329199c273d`.
Commit: `ea0770ca50df1408d372e6f1f2f0ab2b4237ceed`
(`test(horizon): verify state-mode concurrency and crash recovery`).

## Implementation

- Added `tests/test_state_concurrency.py` with real two-process begin races,
  an externally counted and released duplicate-finish gate, live-runner recovery
  exclusion, and crashes at reservation, artifact-edit, finishing, Popen,
  running-gate, pre-commit, and post-commit boundaries.
- Every launched test process has a bounded deadline and is collected or killed
  through its live `Popen`. Saved goal PIDs remain diagnostic. The running-gate
  test retains its actual live handle, releases and reaps it, then makes recovery
  prove it does not call `killpg` on the saved PID.
- `gate.run_gate` now tags the specific callback-persistence failure after
  reaping the child through its live handle. `steps.finish` converts only that
  tagged uncertainty into `StepConflict`, leaving the durable attempt in
  `finishing` for evidence-bound recovery instead of fabricating an accepted
  checkpoint.
- Replaced Task 1's fixed 0.2-second wait in
  `test_goal_create_waits_for_process_owned_create_lock` with a marker written
  immediately before the child calls the real process-owned lock.
- Added public finish-path rejection coverage for attempts to overwrite gate,
  review, budget, and watch controls.
- Extended the bookkeeping hash test to prove both directions: a state reservation
  is hash-neutral and a real source write changes the hash.

## Adversarial matrix

| Scenario | Coverage and disk assertion |
| --- | --- |
| Two distinct begin requests race | `test_begin_races_reserve_exactly_one_attempt[request_ids0-*]`: one stored attempt, one spent turn, loser is busy/conflict. |
| Two identical begin requests race | Same test's identical-ID cases: both receive the same stored packet digest, exactly one response is replayed, one attempt/turn persists. |
| Duplicate finish while gate runs | `test_duplicate_finish_cannot_start_a_second_gate`: start/release handshake and external byte counter require exactly `b"x"`; second result is `StepBusy`. |
| Recovery while finish runner lives | `test_recovery_is_refused_while_finish_runner_is_live`: syntactically complete PID-bound evidence is still refused and saved state is byte-for-byte equivalent as decoded JSON. |
| Crash after reservation, before dispatch | `test_reserved_attempt_survives_crash_before_dispatch`: exit 73 after a reservation marker leaves one charged reserved turn and no checkpoint; only `not-started` recovery closes it. |
| Crash after artifact edit, before update | `test_artifact_edit_survives_crash_and_marks_old_evidence_stale`: edited artifact survives, accepted task statement remains old, recovery rejects the missing update, next packet marks evidence stale. |
| Crash after finishing marker, before Popen | `test_crash_after_finishing_marker_records_only_recovery_failure`: saved `finishing` state has pending blobs, no gate record/checkpoint; recovery adds only a failed checkpoint. |
| Crash after Popen, before handle persistence | `test_spawn_persistence_failure_is_uncertain_and_reaps_owned_gate`: injected atomic-save failure occurs after real Popen, owned process is reaped, no gate record/checkpoint is fabricated, recovery requires explicit stopped evidence. |
| Crash during gate | `test_crash_during_gate_uses_live_handle_for_cleanup`: a real waiting gate is saved diagnostically, released/reaped via the test's live handle, and recovery never signals its saved PID. |
| Crash after gate return, before atomic commit | `test_crash_after_gate_return_leaves_old_state_authoritative`: gate counter advances, disk remains `finishing`, old task and empty checkpoint list remain authoritative, recovery records failure. |
| Crash after atomic commit, before response | `test_crash_after_atomic_commit_replays_without_gate_or_checkpoint`: disk is accepted with one checkpoint; replay leaves both gate counter and checkpoint count at one. |
| Corrupt packet/update/goal or unknown schema | Existing `test_replay_refuses_missing_or_corrupt_saved_packet`, `test_read_update_rejects_duplicate_keys_nonfinite_and_oversized_input`, execution validation, and the real CLI malformed-schema case reject without guessed state or replacement goals. |
| Oversized update and explicit archive | Existing 64-KiB input rejection, packet/candidate bounds, and `test_update_preserves_omitted_fields_and_records_archives` retain archived before-value and reason. |
| Overwrite gate/review/budget/watch list | New `test_worker_update_cannot_overwrite_goal_control_fields` plus the existing forged-review test reject before gate dispatch and preserve all control fields. |
| Bookkeeping versus real source edits | Extended `test_goal_bookkeeping_does_not_change_hash` proves begin is neutral and a real source file write invalidates the hash. |

## Test-first and discriminatory evidence

The genuine pre-fix focused command was:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_state_concurrency.py tests/test_concurrency.py::test_goal_create_waits_for_process_owned_create_lock tests/test_horizon_steps.py::test_worker_update_cannot_overwrite_goal_control_fields tests/test_tree_hash.py::test_goal_bookkeeping_does_not_change_hash -q -p no:cacheprovider --tb=short
```

Output:

```text
..............FF.................                                        [100%]
2 failed, 31 passed in 3.31s
```

Both failures were
`test_spawn_persistence_failure_is_uncertain_and_reaps_owned_gate`, one
per runtime, with `Failed: DID NOT RAISE StepConflict`. The test had already
captured the actual gate `Popen`; the callback failure path reaped it
(`returncode=-9`) but `finish` then accepted the candidate as an ordinary
unrunnable-gate outcome. This is the reproduced production defect, not an import
or fixture failure.

After the narrow fix, that case returned `2 passed in 0.18s`. The focused
boundary selection returned `35 passed in 3.37s`; the full affected module set
returned `320 passed in 26.15s`; the subsequently strengthened PID-bound
live-runner case returned `2 passed in 0.57s`. After the final explicit
uncertainty marker and source-preservation cleanup, the direct uncertainty and
callback-cleanup selection returned `4 passed in 0.27s`, and the whole new
concurrency module returned `22 passed in 2.73s`.

Most matrix invariants were already correct and had no compatible historical
failing implementation. Two disposable copied-source negative controls were run
and removed:

- Disabling bookkeeping exclusion made both runtime cases fail at begin with
  `RevisionConflict: Project snapshot changed during packet preparation`
  (`2 failed in 0.15s`).
- Pointing recovery at a different lock from the live finish runner made both
  runtime cases accept recovery instead of raising `StepBusy`
  (`2 failed in 0.39s`).

Those controls prove the shipped assertions discriminate the relevant failures
without adding a mutation framework. For the remaining already-correct crash
transitions, the limitation is explicit: no compatible pre-fix snapshot exists.
The tests use boundary-specific exit codes, marker files, saved revisions,
external counters, and disk assertions; setup/import failures were not counted
as RED evidence.

## Final integrated verification

Interpreter and runner:

```text
Python 3.14.4
pytest 9.1.1
```

Exact final command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest -q -p no:cacheprovider --tb=short .
```

Durable output in `task-9-integrated-suite.txt`:

```text
530 passed in 40.68s
exit_status=0
```

An earlier whole-suite process was started before source-preservation review,
its tool handle was lost after partial progress output, and that snapshot was
then invalidated by restoring the pre-existing `run_gate` docstring. It is
excluded from all counts and completion claims. The final result above is the
only integrated result reported.

Both real entrypoints were also run through `doctor` and `status` with the
worktree passed explicitly as `--project`:

```text
.agents/skills/horizon/scripts/harness.py --runtime codex: doctor 0, status 0
.claude/skills/horizon/scripts/harness.py --runtime claude: doctor 0, status 0
```

Both doctors reported `state_supported: true`, both status commands returned
an empty goal list, and full JSON/output is in `task-9-entrypoints.txt`.
`git diff --check` returned no output.

Final source fingerprints:

```text
9ac4961c2ddb733dc2e192c527608084a400bcd35187fad34fc10a41476b6ffc  harness/gate.py
e1bf7b5e517efe0d6aba722789c9c39b875a3243646ec0691be5bb1fdb2df761  harness/steps.py
e72d378059ece48d295098f62560e119cfdd539d2ca05adad5360d2de672d24e  tests/test_state_concurrency.py
d06ada3b10ba7deff0f0ec959bdb7d2b14335dd9db7449e5ff3b3e7d3cbe54cc  tests/test_concurrency.py
c258613c1989137bef6e10eab395ae625a56591fdaa55e5568f23fbcd67f2697  tests/test_horizon_steps.py
2ff5eeb7aa7b057b236b0e051d941afd09775cb3c926a0901cd2a75fe076acc3  tests/test_tree_hash.py
```

## Self-review and limitations

The production diff is limited to the one uncertainty classification at the
live gate callback boundary and the corresponding refusal in `finish`. Ordinary
command failures retain their accepted failed-checkpoint behavior. Recovery
still validates exactly one gate-state header, requires a matching saved PID
when present, never probes or signals that PID, and retains pending evidence.
Legacy conversation behavior, gate timeout cleanup, packet/revision matching,
historical attempt checkpoints, current summary checkpoints, and procedure-change
recovery are unchanged.

All new child processes use marker or release handshakes rather than fixed sleeps
to claim a boundary. Polling sleeps only service bounded handshakes. Cleanup uses
the live process object; the test that intentionally simulates a lost finish
process gives its gate a separate live handle before injecting the crash.

The previously recorded native-host limitations remain unchanged and were not
rerun: native Claude is unavailable because the installed CLI is unauthenticated,
and complete native collaboration/AST transcript export was unavailable for the
Codex smoke runs. The controller preserved those smoke artifacts separately.
Task 9 adds Python protocol, subprocess, CLI-entrypoint, and integrated-suite
evidence; it does not claim a new native-host smoke.

## Review fix round 1

Review base: `ea0770ca50df1408d372e6f1f2f0ab2b4237ceed`.
Review-fix commit: `2f65f2a24d753b6875bd126fc989335baff82ed8`
(`test(horizon): prove interruption assertions`).

The review identified two evidence gaps. The immutable-control test now asserts
the saved `gate.review_criterion` directly against its before value. The crash
tests now explicitly assert that pre-dispatch recovery saves a failed checkpoint,
that the edited artifact still exists after recovery, and that recovery has not
replaced the accepted task entry.

The already-correct invariants now have 18 narrow, disposable discriminatory
controls. Each raw file under `task-9-controls/` contains the mutation
description, mutated-copy path, changed-file SHA-256, unified diff, exact
command, raw pytest output, and `exit_status=1`. Every failure reaches the
intended shipped assertion; import, collection, and setup failures are excluded.
`task-9-controls/README.md` is the compact test-to-control map. It maps the
original genuine Popen-persistence RED separately because that was a discovered
production defect, not an already-correct invariant. Controls 06 and 14 group
only cases defeated by the same mutation; the other controls stay scoped to one
protocol boundary or one related hash direction.

The invalid early indentation probe mentioned during implementation was replaced
and is not counted. The final `01-begin-distinct-conflict.txt` is a valid
two-runtime assertion failure. No production fault switch, mutation framework,
or product source change was added in this fix round.

The controller separately resolved the unchanged-code corrupt-state, oversize,
and archive questions in `task-9-controller-verification.md` through their
existing tests and read-only/precommit source paths. This fix round does not
claim those unchanged tests as newly written or rerun controls.

Exact focused GREEN command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_state_concurrency.py tests/test_concurrency.py::test_goal_create_waits_for_process_owned_create_lock tests/test_horizon_steps.py::test_worker_update_cannot_overwrite_goal_control_fields tests/test_tree_hash.py::test_goal_bookkeeping_does_not_change_hash -q -p no:cacheprovider --tb=short
```

Output, also preserved in `task-9-fix1-focused.txt`:

```text
.................................                                        [100%]
33 passed in 3.53s
exit_status=0
```

Interpreter: `Python 3.14.4`. `git diff --check` returned no output.

Fix-round source fingerprints:

```text
2853e7b09a812e40257468f86cfe6031942a32099375acd352c4a774af8bb5aa  tests/test_horizon_steps.py
c9e48008c78e7d350c5d971453a7500802ecf75b734d0c9174d3c803126164a4  tests/test_state_concurrency.py
d06ada3b10ba7deff0f0ec959bdb7d2b14335dd9db7449e5ff3b3e7d3cbe54cc  tests/test_concurrency.py
2ff5eeb7aa7b057b236b0e051d941afd09775cb3c926a0901cd2a75fe076acc3  tests/test_tree_hash.py
```

The full integrated `530 passed in 40.68s` baseline remains valid because this
round changed assertions only and the focused command covers every amended or
explicitly reviewed test. Per review instructions, the unchanged full suite and
native entrypoints were not rerun.
