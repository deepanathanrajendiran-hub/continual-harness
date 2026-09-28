### Spec Compliance

- ✅ Spec compliant. Recovery preserves the accepted task summary and entries while replacing only the required next action, appends a failed checkpoint, closes the already-reserved attempt without refunding its turn, and commits exactly one revision (`harness/steps.py:487`, `harness/steps.py:559`, `harness/steps.py:570`, `harness/steps.py:572`, `harness/steps.py:585`).
- ✅ Recovery replay returns the saved terminal result and rejects changed reason, worker-state assertion, or evidence digest; accepted attempts are explicitly refused (`harness/steps.py:518`, `tests/test_horizon_steps.py:638`).
- ✅ Finishing recovery uses the runner lock and accepts only the approved unique gate-state assertion, with a matching saved gate PID when present and at least 40 UTF-8 bytes of supporting prose; unresolved liveness leaves the attempt open (`harness/steps.py:451`, `harness/steps.py:487`, `harness/steps.py:551`, `tests/test_horizon_steps.py:768`, `tests/test_horizon_steps.py:889`). No code probes or signals a stored PID.
- ✅ Recovery remains independent of the current procedure digest, retains finishing diagnostics/pending references, never accepts a worker candidate, and rejects `not-started` except for an unbound reserved attempt with no gate record (`harness/steps.py:487`, `tests/test_horizon_steps.py:709`, `tests/test_horizon_steps.py:1014`).
- ✅ Review and completion compute the workspace hash before the goal lock, compare canonical saved state under the lock, recheck idle state, and then persist through the shared revision helper (`harness/goal.py:461`, `harness/goal.py:469`, `harness/goal.py:486`, `harness/goal.py:525`, `tests/test_goal.py:878`, `tests/test_goal.py:927`). Abandon, reopen, and add-subagent also require idle state and use the same state-mode revision path (`harness/goal.py:595`, `harness/goal.py:608`, `harness/goal.py:648`).
- ✅ Legacy checkpoint and its CLI caller refuse state-mode goals before a gate is run (`harness/goal.py:411`, `harness/cli.py:147`, `tests/test_goal.py:864`). The scoped Task 6 CLI refusal is present without adding Task 7's broader command surface.
- ✅ Packet admission reserves the longer mandatory recovery next action without lowering the 24 KiB limit or dropping task entries (`harness/task_state.py:85`, `harness/task_state.py:488`, `tests/test_task_state.py:468`, `tests/test_horizon_steps.py:941`). The checkpoint/review excerpt reservation code remains intact.
- ✅ The strict goal decoder is unchanged, and malformed revision candidates are now normalized to `GoalStateError` (`harness/goal.py:698`, `tests/test_goal.py:975`).
- ⚠️ Cannot verify from this Task 6 diff: Task 7's `step-recover` CLI command and broader step-command integration, Task 8's documentation/native smoke coverage, and Task 9's full concurrency and whole-suite regression gate. The controller should reconcile these in their owning tasks.

### Strengths

- Recovery is a narrow state transition with clear separation between evidence reading, liveness assertion validation, workspace hashing, lock acquisition, and the revisioned commit (`harness/steps.py:437`, `harness/steps.py:451`, `harness/steps.py:487`).
- The implementation preserves idempotency without weakening concurrency: replay is read-only, an owned finish runner yields `StepBusy`, and an intervening goal mutation yields `RevisionConflict` (`harness/steps.py:518`, `harness/steps.py:590`, `harness/goal.py:469`).
- The tests exercise behavior rather than mocks: workspace edits survive recovery, the turn remains spent, contradictory replays fail, runner ownership blocks recovery, ambiguous headers fail, required review cannot be forged, and a mutation during hashing is rejected (`tests/test_horizon_steps.py:603`, `tests/test_horizon_steps.py:638`, `tests/test_horizon_steps.py:768`, `tests/test_horizon_steps.py:822`, `tests/test_goal.py:878`).
- Boundary coverage is unusually good: the exact packet-capacity regression drives recovery and a subsequent begin, while the unit test checks the reservation copy itself (`tests/test_horizon_steps.py:941`, `tests/test_task_state.py:468`).

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

- None.

#### Minor (Nice to Have)

- `harness/goal.py:679-686` constructs `complete = _with_lock(_complete_locked)` under a comment saying every mutator is serialized, then immediately overwrites it with `complete = _complete_locked`. The resulting behavior is correct because `_complete_locked` now delegates to `_snapshot_transaction`, but the dead assignment and stale name/comment make lock ownership easy to misread during later lifecycle work. Remove the first `complete` assignment from the wrapper block and rename `_complete_locked` to reflect that it starts a snapshot transaction, or otherwise make the special completion wiring explicit in one place.

### Named Checks

- Supplied evidence check: the implementation report records `288 passed in 20.62s` for the assigned and adjacent suites and a clean `git diff --check`. I did not rerun unchanged suites, per the review method; the report contains no warnings or noisy output.
- Focused outside-diff check — public-writer completeness risk: inspected the `harness/goal.py` function/save-call inventory and found no omitted ordinary public writer beyond checkpoint, review, complete, abandon, reopen, and add-subagent (`harness/goal.py:411`, `harness/goal.py:573`, `harness/goal.py:679`).
- Focused outside-diff check — recovery reason/terminal-shape risk: inspected the called UTF-8 text validator, blob/report helpers, and attempt validator. They enforce the 1 KiB UTF-8 recovery-reason limit, content-addressed evidence references, compact terminal response fields, and recovered-result presence (`harness/task_state.py:98`, `harness/steps.py:65`, `harness/steps.py:141`, `harness/task_state.py:245`).
- Diff-scope check: reviewed the supplied `review-422f3a4..6aab35e.diff` in bounded ranges. No changed-file hunk required a separate full-file read; the only outside-diff reads were the focused checks named above.

### Assessment

**Task quality:** Approved

**Reasoning:** The implementation satisfies the recovery, liveness, replay, revision, lifecycle, snapshot-hashing, strict-decoding, and packet-capacity contracts with direct behavioral coverage. The lone issue is dead and misleading completion-wrapper wiring; it does not change runtime behavior and is appropriately Minor.
