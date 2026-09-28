# Task 9 discriminatory evidence map

Every numbered file records the exact disposable mutation, mutated-file
SHA-256, unified diff, exact pytest command, raw output, and exit status. All
numbered controls exited 1 because the intended shipped assertion failed; no
import, collection, or setup failure is counted. The disposable copies were
outside the worktree and are not product changes.

| Shipped invariant/test | Discriminatory evidence |
| --- | --- |
| Distinct begin requests retain one winner and classify the loser busy/conflict | `01-begin-distinct-conflict.txt`: generic conflict classification fails both runtime cases at the loser-class assertion. |
| Identical begin requests replay the one stored reservation | `02-begin-identical-replay.txt`: suppressing the replay flag fails both runtime cases. |
| A duplicate finish cannot launch a second gate | `03-duplicate-finish-gate.txt`: running the gate before reporting runner-lock contention produces two counter bytes and fails both runtimes. |
| Recovery cannot pass a live finish runner | `04-live-recovery-lock.txt`: using a different recovery lock makes both runtimes accept instead of raising `StepBusy`. |
| A pre-dispatch crash keeps its charged reservation | `05-reservation-charge.txt`: erasing the post-begin reservation/charge fails both runtimes. |
| Recovery checkpoints remain failed/unverified | `06-recovery-fabricates-pass.txt`: fabricating `gate=pass` fails reservation, pre-Popen, and pre-terminal-commit recovery cases in both runtimes. |
| Workspace artifact edits survive recovery | `07-recovery-deletes-artifact.txt`: deleting the edited artifact fails both runtimes. |
| Edited evidence is stale in the next packet | `08-edited-evidence-current.txt`: forcing evidence current fails both runtimes. |
| No gate-process record exists before Popen | `09-pre-popen-metadata.txt`: injecting diagnostic metadata into the finishing commit fails both runtimes. |
| A saved PID is diagnostic and recovery never signals it | `10-saved-pid-signal.txt`: blind `killpg` reaches the test's prohibiting monkeypatch in both runtimes. |
| Before terminal commit, the old accepted task remains authoritative | `11-preterminal-publish.txt`: publishing the pending candidate in the finishing commit fails both runtimes. |
| Terminal finish replay does not rerun the gate | `12-terminal-replay-gate.txt`: rerunning it creates two counter bytes and fails both runtimes. The shipped case also asserts the durable checkpoint count remains one. |
| Goal creation waits at the actual shared CREATE lock acquisition | `13-create-lock-target.txt`: acquiring a distinct lock lets the child state file appear while the parent owns CREATE, failing the no-file assertion. |
| Gate, review criterion, budget, and watch paths are immutable to worker updates | `14-immutable-controls.txt`: persisting each attempted control mutation fails all eight runtime/field cases. The review cases fail at the direct `review_criterion` before/after assertion. |
| Recovery does not replace the accepted task entry | `15-recovery-task-clobber.txt`: changing only the stored entry fails the new preservation assertion in both runtimes. |
| Harness bookkeeping is hash-neutral | `16-tree-bookkeeping-neutrality.txt`: disabling the exclusion changes the hash during begin and fails both runtimes. |
| Real source edits invalidate the tree hash | `17-tree-real-edit-invalidation.txt`: a constant digest fails the real-edit inequality in both runtimes. |
| Saved gate metadata binds to the actual live handle; cleanup retains that handle | `18-live-handle-binding.txt`: persisting an off-by-one PID fails both runtime cases while each fixture's `finally` still releases and collects the real `Popen`. |
| Popen succeeded but handle persistence failed | Genuine pre-fix RED in `task-9-report.md`: both runtimes failed because `StepConflict` was not raised; the captured live process was already reaped. This discovered defect was fixed in production and is not represented by a test-only mutation. |

The unchanged-code corrupt-state, oversize, and archive matrix rows are resolved
by `task-9-controller-verification.md`, which maps their existing tests and
read-only/precommit source paths. The review fix focused success output is in
`../task-9-fix1-focused.txt`.
