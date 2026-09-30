# Frozen native pilot report — module-bug-terra-state-3

## Outcome

The Horizon state-mode goal `fix-the-checkout-integration-and-the-underlying-discount-def` completed after one of four reserved attempts. `pricing.py` now calculates `amount * (100 - percent) // 100`; `checkout.total` still calls `pricing.discounted` for each amount. The checkpoint tree hash was `250e250cdbab4c9e714515fd93c68eb8bf54aeb23431a6d40f07f1aebfc69d9c`.

The fixed gate passed at the accepted checkpoint: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` ran `test_total_and_boundaries` and reported `OK` (one test). The independent reviewer returned `pass` under the exact frozen criterion, and `complete` recorded status `complete`.

## Integrity and review

`checkout.py` retained seed SHA-256 `82de323e0cddff692abb6cea7fc7ff3ed6794a769bb5b48ec39edbf36fd103bb` and mtime_ns `1790650615755903259`. The evaluator-owned `tests/test_acceptance.py` retained seed SHA-256 `cb50420a69e7abef79d5b50043ef39e82bfbffb16edb1b58b0f4202d5693442d` and mtime_ns `1790650615756218384`; the test inventory still contains only that test file. `pricing.py` changed from its seed hash as required for the underlying defect.

The reviewer recorded one unknown: the seed-hash file does not separately label which entries are protected. Its source and evaluator checks nevertheless found the two artifacts that must remain unchanged (`checkout.py` and the acceptance test) unchanged, with the necessary `pricing.py` change applying the discount once.

## Lifecycle and native roles

- Coordinator: `/root/pilot_module_bug_terra_state_3`.
- Fresh editing worker (gpt-5.6-terra, high): `/root/pilot_module_bug_terra_state_3/state_worker_001`; attached for `request-001`, then observed completed before `step-finish` accepted its update.
- Fresh independent reviewer (gpt-5.6-terra, high): `/root/pilot_module_bug_terra_state_3/state_reviewer_001`; observed completed before its pass review was recorded against the checkpoint hash.
- Usage/cost: `null`; host usage was not consistently reported for coordinator, worker, and reviewer.

Before creating the local `.codex` marker or invoking the lifecycle CLI, `git rev-parse --show-toplevel` from the trial project failed as required with exit status 128; the raw result is in `git-isolation-precheck.txt`.

Format repairs: none. Protocol deviations: none. No evaluator-owned acceptance artifact was edited, removed, moved, or regenerated.

## Evidence accounts

### Exported tool transcripts and raw lifecycle records

`doctor.txt`, `start.txt`, `status-initial.txt`, `status-before-request-001.txt`, `step-begin-request-001.json`, `step-attach-request-001.json`, `step-finish-request-001.json`, `review-request-001.json`, `complete.json`, and `status-final.txt` preserve CLI responses. `worker-update-request-001.json` preserves the editing worker's returned update; `reviewer-evidence-request-001.md` preserves the independent review. `post-finish-inspection.txt` preserves seed/hash/mtime and test-inventory observations. The initial packet is 1,821 bytes with SHA-256 `d595d1802a3ba699aaede34a8786e3501766d18bf3770e33868e61585cd4835b`.

### Coordinator-written tool accounts

`git-isolation-precheck.txt` records the required pre-dispatch Git isolation check. `worker-terminal-request-001.txt` records the coordinator's observed host terminal status. `evidence-manifest-pre-report.txt` records the first evidence hash inventory; this report and the final manifest are coordinator-written terminal accounts.
