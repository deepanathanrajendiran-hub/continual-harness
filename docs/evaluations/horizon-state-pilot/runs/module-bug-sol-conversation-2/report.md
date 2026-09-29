# Horizon state pilot report: module-bug-sol-conversation-2

## Outcome

PASS. Goal `fix-the-checkout-integration-and-the-underlying-discount-def` reached Horizon status `complete` in conversation mode after one of four allowed checkpoints and within the frozen 15-minute limit. `pricing.discounted` now applies the requested percentage once. `checkout.total` remains unchanged and still delegates every amount to `pricing.discounted`.

The frozen gate `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` ran one test and passed. Checkpoint tree hash: `c442ef1b2b68ff5c862f85f16689ba6ac13230f1527fddb9b736a4eda0b91396`. Fresh independent review returned `PASS` and was recorded against that exact hash before `complete` succeeded.

## Source and protected artifact evidence

Only `pricing.py` changed:

```diff
-    return amount * (100 - percent * 2) // 100
+    return amount * (100 - percent) // 100
```

Final source state:

| Path | Final SHA-256 | Final mtime_ns | Seed preservation |
| --- | --- | ---: | --- |
| `checkout.py` | `82de323e0cddff692abb6cea7fc7ff3ed6794a769bb5b48ec39edbf36fd103bb` | `1790650615699417737` | Hash and mtime unchanged |
| `pricing.py` | `d90b510771d75fa0fbc4b7b42115c97812bbb6e3d494d56e9b495925f38a2a12` | `1790682724598589866` | Intended implementation change |
| `tests/test_acceptance.py` | `cb50420a69e7abef79d5b50043ef39e82bfbffb16edb1b58b0f4202d5693442d` | `1790650615699779861` | Protected hash and mtime unchanged; byte-identical to seed |

No test was removed. The acceptance suite still contains `test_total_and_boundaries`, covering totals 270, 0, and 300. The reviewer independently reran the frozen gate and compared the protected artifact with the seed snapshot.

## Native roles and boundaries

- Coordinator: `/root/pilot_module_bug_sol_conversation_2`; lifecycle ownership, evidence capture, checkpoint, reviewer dispatch, and completion.
- Editing worker: `/root/pilot_module_bug_sol_conversation_2/editing_worker`; `gpt-5.6-sol`, high reasoning, fresh native context; source inspection/edit/test only, no lifecycle authority. It used AST-editor `list_symbols` on all Python files and `replace_function_body` only on `pricing.discounted`.
- Independent reviewer: `/root/pilot_module_bug_sol_conversation_2/independent_reviewer`; `gpt-5.6-sol`, high reasoning, fresh native context; read-only review against the exact frozen criterion.

`worker-native-final-account.md` preserves the actual host-delivered editing-worker final message. `worker-update.json` is the worker's repaired final update document. `reviewer-verdict.md` contains the verdict text supplied to the lifecycle. `worker-terminal-evidence.md`, lifecycle projections, hash tables, and this report are coordinator-written tool accounts. Full host tool transcripts are not exported by conversation mode and were not reconstructed.

## Lifecycle and isolation

The mandatory pre-dispatch `git rev-parse --show-toplevel` check from the isolated trial project failed with exit 128 as required. The trial-local `.codex` marker existed and no saved goal existed at resumed launch. Initial goal record: 1,382 bytes, SHA-256 `c4ffc4aaf8126d7390bfa7fcfeb8f64d7f38047a1d957634fd13a5ed4fec2d0d`. Final goal record: 5,941 bytes, SHA-256 `232e9ba969b7c1d49fc41f577918f7302913edc13080cadcd7c524c9fdf6080d`. Conversation mode produces no state-mode packet or audit object, so packet/audit byte counts and hashes are not applicable.

## Deviations and observations

- Before this successful run, an external host usage limit interrupted the prior coordinator before any goal or worker was created. Root and this resumed coordinator verified unchanged seed hashes/mtimes and absent saved goal; the seed was not restored and the budget was not changed.
- The worker first ran a default discovery command that collected zero tests and exited 5, then ran the exact frozen `-s tests` command successfully. The lifecycle gate itself ran exactly once and passed.
- The worker's first update used unsupported entry kind `evidence`. The single permitted formatting-only repair changed that kind to `observation`; no source change occurred during repair.
- The reviewer reported the worker terminal transcript/result as missing from the evidence directory, although `worker-terminal-evidence.md` and `worker-update.json` had been written before reviewer completion. This timing/visibility discrepancy is retained as the reviewer's actual omission report; it did not conflict with independently verified gate, source, or protected-artifact evidence.
- Usage/cost is null because the host did not report coordinator, worker, and reviewer usage consistently.

## Evidence index

- `coordinator-git-isolation-precheck.txt`: required Git-isolation exit/status.
- `coordinator-prestart-interruption.md`: external pre-start interruption record.
- `lifecycle-doctor.json`, `lifecycle-start.json`, `lifecycle-status-initial.json`, `lifecycle-check.json`, `lifecycle-complete.json`: lifecycle evidence/projections.
- `worker-native-final-account.md`, `worker-update.json`, `worker-terminal-evidence.md`, `role-record.md`: actual native final message, repaired update, coordinator terminal observation, and role boundaries.
- `source-hashes-after-worker.csv`, `source-diff.patch`: source fingerprint and exact implementation delta.
- `reviewer-verdict.md`: recorded independent review evidence.
- `seed-hashes.csv` and `seed-snapshot/`: evaluator-owned baseline evidence.
