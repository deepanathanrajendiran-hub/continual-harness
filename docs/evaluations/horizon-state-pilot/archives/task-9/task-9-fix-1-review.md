### Finding Verdicts

- **Most newly added assertions lacked intended-failure evidence; preserve a narrow negative control for each remaining already-correct invariant and a real RED for any production defect** — **ADDRESSED**. `task-9-controls/README.md:3-29` maps 18 disposable mutations to every already-correct Task 9 invariant and separately maps the Popen-persistence defect to its genuine pre-fix RED. The referenced raw records contain the mutation diff, focused command, intended assertion failure, and `exit_status=1`; sampled boundary evidence includes loser classification (`task-9-controls/01-begin-distinct-conflict.txt:30-42`), duplicate gate execution (`task-9-controls/03-duplicate-finish-gate.txt:20-36`), all three failed-recovery checkpoint cases (`task-9-controls/06-recovery-fabricates-pass.txt:19-69`), all immutable controls (`task-9-controls/14-immutable-controls.txt:28-100`), and live-handle PID binding (`task-9-controls/18-live-handle-binding.txt:20-34`). No record fails during import, collection, or fixture setup.
- **The review-control case lacked a direct before/after `review_criterion` equality assertion** — **ADDRESSED**. `tests/test_horizon_steps.py:1290-1292` now compares the saved gate's `review_criterion` directly with its pre-finish value; control 14 makes both runtime review cases fail at that assertion (`task-9-controls/14-immutable-controls.txt:36-43`, `task-9-controls/14-immutable-controls.txt:67-73`). The amended focused selection is green with 33 passes (`task-9-fix1-focused.txt:1-4`).

### New Breakage in the Fix Diff

None. The fix diff changes assertions only: it adds the direct review-criterion check and strengthens the reservation/artifact recovery postconditions (`tests/test_horizon_steps.py:1290-1292`, `tests/test_state_concurrency.py:281`, `tests/test_state_concurrency.py:345-349`). The focused run covers every changed test and reports 33 passes (`task-9-fix1-focused.txt:1-4`).

### Out-of-Scope Observations

None. The controller's focused unchanged-code inspection resolves the earlier corrupt-state, oversize, and archive verification warnings with named tests and precommit/read-only paths (`task-9-controller-verification.md:3-12`).

### Verdict

**Fix round:** All findings addressed, no new Critical/Important breakage.
