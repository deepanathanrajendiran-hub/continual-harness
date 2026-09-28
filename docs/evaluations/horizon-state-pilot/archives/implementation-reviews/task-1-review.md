### Spec Compliance

- ✅ Spec compliant for Task 1: `harness/filelock.py:118` adds platform detection and `harness/filelock.py:121` adds a persistent-inode, process-held goal lock with timeout and release on every exit. `harness/goal.py:270`, `harness/goal.py:361`, `harness/goal.py:418`, and `harness/goal.py:578` route the goal writer entry points through it. The diff changes exactly the four requested files and leaves Refine's `locked` calls intact.
- ⚠️ Cannot verify from this task diff: state-mode creation refusal on unsupported platforms is assigned to Task 3; moving legacy review/completion snapshot hashing out of lock sections is assigned to Task 6. The controller should check those tasks before integration (`harness/filelock.py:118`, `harness/goal.py:418`).

### Strengths

- `harness/filelock.py:129-151` acquires an exclusive OS lock before yielding, keeps the inode after release, and closes the descriptor even if unlock raises. This addresses both aged-lock theft and holder termination.
- `tests/test_filelock.py:118` checks that an open permission error prevents entry. `tests/test_filelock.py:132` uses another process to test timeout on an aged inode and reacquisition after killing the holder; those tests exercise the relevant kernel behavior.
- `tests/test_filelock.py:181` checks that each current mutation entry point fails before changing goal JSON when lock acquisition is denied. The reported red/green runs discriminate the original missing API and unrouted call sites.
- Focused cross-cutting check for writer bypass: searched harness callers for direct `_save`, `_create_locked`, and `_checkpoint_locked` use, and checked the goal writer symbol/call-site list. No external bypass appeared; `harness/goal.py:587-590` wraps the remaining public mutators. The runtime `.claude/harness/bin` imports resolve to the changed source through symlinks.

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

- None.

#### Minor (Nice to Have)

- `tests/test_concurrency.py:130-131`: the create-lock process test waits a fixed 0.2 seconds after the child prints `ready`, which happens before it calls `goal.create`. A delayed child could make the empty-directory assertion pass without attempting the lock. A handshake at the acquisition attempt, or a child-side completion signal with a bounded wait, would make this test less timing-dependent. The separate real-process lock test and denied-open writer tests still give substantive coverage.

### Assessment

**Task quality:** Approved

**Reasoning:** The lock lifetime, error propagation, and goal writer routing match the scoped requirements. The one test timing weakness is minor because independent tests cover the lock primitive and the goal call sites. The report records passing focused and regression suites with no reported warnings; I did not rerun them because the diff did not raise an unresolved behavioral doubt.
