### Finding Verdicts

- **Saved goals accept duplicate keys and non-finite JSON numbers** — ADDRESSED. `harness/goal.py:352-359` applies duplicate-key, non-finite constant, and finite-float hooks, then translates their `StateError` to `GoalStateError`. The six regressions in `tests/test_goal.py:774-793` cover duplicate keys in conversation and state goals, plus `NaN`, `Infinity`, `-Infinity`, and overflowing `1e999`. The report records 6 RED failures before the fix and 117 GREEN goal/task-state tests after it.

### New Breakage in the Fix Diff

- None. The fix changes only saved-goal decoding and focused tests; the reused parsing hooks already serve worker-update decoding in `harness/task_state.py`.

### Out-of-Scope Observations

- The previously noted malformed-candidate error path in `harness/goal.py:661-665` remains for Task 6/final review. CLI status routing remains assigned to Task 7. Neither is changed by this fix.

### Verdict

**Fix round:** All findings addressed, no new Critical/Important breakage.
