### Spec Compliance

- ❌ Issues found: Step 2 requires discriminatory RED evidence for each new test. The report records one genuine pre-fix failure and two test-only negative controls, then explicitly says the remaining already-correct crash transitions have no negative-control evidence (`task-9-report.md:71-100`). The controller ruling allows a narrow test-only negative control when no compatible historical snapshot exists; it does not waive the per-test discrimination requirement. The new boundary cases at `tests/test_state_concurrency.py:140-618` therefore remain incompletely evidenced.
- ❌ Issues found: the matrix requires attempts to overwrite gate/review/budget/watch controls to be rejected with the corresponding immutable fields unchanged. The parametrization includes `review_criterion` (`tests/test_horizon_steps.py:1260-1266`), but the postconditions assert `reviews` rather than `review_criterion` (`tests/test_horizon_steps.py:1288-1294`), so that field's immutability is not actually verified.
- ⚠️ Cannot verify from diff: the corrupt packet/update/goal/unknown-schema and oversized-update/archive rows are attributed only to pre-existing tests (`task-9-report.md:51-52`); those tests are outside this task diff. The controller should confirm the named tests cover rejection without partial merge or replacement-goal creation, and archive retention of both old value and reason.

### Strengths

- The two begin-race variants assert one charged turn and one stored attempt, while distinguishing idempotent replay from a conflicting request (`tests/test_state_concurrency.py:139-190`).
- The duplicate-finish case follows the required start/release handshake and external one-byte counter, so it distinguishes a busy response from two sequential gate launches (`tests/test_state_concurrency.py:194-216`).
- The crash-boundary tests use explicit markers, bounded polling, live `Popen` handles, and disk-state assertions across reservation, finishing, gate execution, pre-commit, and post-commit boundaries (`tests/test_state_concurrency.py:246-618`).
- The production correction is narrow: callback-persistence uncertainty is tagged after cleanup and only that condition becomes `StepConflict`, preserving ordinary unrunnable-gate behavior (`harness/gate.py:160-166`, `harness/steps.py:384-391`).
- The deferred Task 1 synchronization problem is fixed at the actual lock-attempt boundary rather than with a timing delay (`tests/test_concurrency.py:116-145`), and the bookkeeping hash test now proves both neutrality and real-edit invalidation (`tests/test_tree_hash.py:207-212`).
- Supplied final evidence is clean: `task-9-integrated-suite.txt:1-10` records 530 passes with exit status 0, and `task-9-entrypoints.txt:1-44` records successful doctor/status flows for both entrypoints.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

- `task-9-report.md:87-103` / `tests/test_state_concurrency.py:140-618`: most newly added assertions were never shown to fail for the intended reason. This misses explicit Step 2 and leaves false-positive fixtures undetected. Run and preserve a narrow test-only negative control for each remaining already-correct invariant, grouping only cases defeated by the same mutation; use a real pre-fix RED for any newly discovered production defect.
- `tests/test_horizon_steps.py:1288-1294`: the review-control case checks `after.get("reviews")`, not `after["review_criterion"]`. A mutation that changed only the review criterion could pass this test. Add the direct before/after equality assertion for `review_criterion` (or assert the complete immutable control-field projection).
- Focused outside-diff check for the named review-control risk: `rg` found no existing before/after `review_criterion` immutability assertion elsewhere in `tests/test_horizon_steps.py` or `tests`, so the missing postcondition is not supplied by pre-existing coverage.

#### Minor (Nice to Have)

None.

### Assessment

**Task quality:** Needs fixes

**Reasoning:** The concurrency fixtures and narrow uncertainty fix are technically strong, and the supplied final suite is clean. The task still misses its mandatory per-test discrimination evidence and one explicit immutable-field assertion, so it is not ready to pass this task-scoped gate.
