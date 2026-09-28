# Task9 unchanged-code coverage resolution

The task reviewer requested cross-task confirmation of two matrix rows outside the Task9 diff. Root inspected the following existing tests and the specific rejection paths at ea0770c; no unchanged passing suite was rerun.

- Corrupt packet: `tests/test_horizon_steps.py:110` damages or removes the saved packet, requires both begin replay and attach to reject, and verifies the execution revision remains1.
- Corrupt update and oversized input: `tests/test_task_state.py:102` checks duplicate keys, non-finite JSON and65537-byte input rejection. `harness/steps.py:287` reads the update before candidate preparation or any commit. `harness/task_state.py:303` only reads and validates bytes; it has no state write or partial merge.
- Malformed goal: `tests/test_goal.py:684` rejects malformed task entries and malformed attempts. `harness/goal.py:348–408` reads/validates saved state and raises on malformed or unsupported execution. It never replaces or creates a goal. `tests/test_horizon_steps.py:1161–1170` supplies schema_version99 to the real CLI and requires exit2, update_accepted false, and no guessed execution revision.
- Oversized candidate: `tests/test_horizon_steps.py:390` rejects before gate dispatch, asserts the counter is absent, the attempt stays attached and accepted entries remain empty. `harness/steps.py:316–338` constructs a separate candidate and checks its packet bound before pending state is committed.
- Explicit archive: `tests/test_task_state.py:7` checks omitted fields retained, input task unchanged, entry removed only from the candidate, and both the exact old entry and supplied reason present in audit.
- Other malformed or immutable operations: `tests/test_task_state.py:81` requires StateError and unchanged input task.

These existing tests passed in the final integrated530-test run. The tests directly establish rejection and archive preservation; the focused source inspection establishes that those rejection paths do not create replacement goals or partially commit updates. This resolves the review's two cross-task “Cannot verify from diff” items. The separate newly added review-criterion equality and per-new-invariant negative controls remain assigned to the Task9 fix round.
