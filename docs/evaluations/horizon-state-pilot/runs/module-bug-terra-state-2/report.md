# Frozen native pilot report: module-bug-terra-state-2

## Outcome

Completed. Goal slug: `fix-the-checkout-integration-and-the-underlying-discount-def`.
The state-mode lifecycle accepted one worker attempt (`request-001`) out of the
four-attempt budget, recorded a passing frozen gate, recorded a passing fresh
independent review, and `complete` returned `status: complete`.

## Gate and source result

The fixed gate was `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`.
Its retained output reports one passing test (`test_total_and_boundaries`) and
`OK`; see `step-finish-request-001.json` and `complete-request-001.json`.

Raw source inspection in `pre-finish-source-inspection.txt` establishes that
`checkout.total` still sums `pricing.discounted(amount, percent)` and that
`pricing.discounted` computes `amount * (100 - percent) // 100`. This applies
the percentage once and satisfies the empty and zero-discount behavior covered
by the acceptance test.

The protected evaluator-owned `tests/test_acceptance.py` is preserved. Its final
SHA-256 is `cb50420a69e7abef79d5b50043ef39e82bfbffb16edb1b58b0f4202d5693442d`
and its final mtime_ns is `1790650615748766403`, matching `seed-hashes.csv`.
The final test inventory retains `tests/test_acceptance.py`; no test was removed.
Current source/test hashes and mtimes are retained in `final-source-hash-mtime.csv`.

## Lifecycle and native roles

| Role | Native handle | Observation |
| --- | --- | --- |
| Coordinator | `/root/pilot_module_bug_terra_state_2` | Ran the prescribed state lifecycle and retained coordinator-written records. |
| Editing worker | `/root/pilot_module_bug_terra_state_2/state_worker_001` | Bound with `step-attach`; completed. Its exact update is `worker-update-request-001.json`; terminal observation is `worker-terminal-request-001.txt`. |
| Independent reviewer | `/root/pilot_module_bug_terra_state_2/independent_reviewer_001` | Fresh reviewer; returned PASS. Its exact verdict is `reviewer-result-request-001.txt`; terminal observation is `reviewer-terminal-request-001.txt`. |

The state sequence is retained in `status-before-request-001.txt`,
`step-begin-request-001.json`, `step-attach-request-001.json`,
`step-finish-request-001.json`, `review-request-001.json`,
`complete-request-001.json`, and `status-final.txt`. The packet SHA-256 was
`16574ca71832b15ba871435003337ebd04b039412cd39064c4ffd5c050f199dc`; packet,
update, and review byte counts are in `packet-update-review-byte-counts.txt`.

## Independent review

The reviewer applied the frozen review criterion and returned PASS. It confirmed
the gate, protected acceptance hash/mtime, retained test inventory, checkout
delegation, and one-time discount expression. It recorded one unknown: there is
no separate evaluator review/report artifact; it found no conflicting completion
claim. The coordinator recorded that exact verdict with the reviewer handle and
checkpoint tree hash `b574657e1656a676853d0d6c5f30d95f8f53a0eb421bb8111d1645b170f84e5a`.

## Git isolation, repairs, deviations, and accounts

The required pre-dispatch `git rev-parse --show-toplevel` was run from the
trial project and failed as required (exit `128`), retained in
`git-isolation-precheck.txt` and `git-isolation-precheck.exit`; therefore the
trial project was outside a Git repository before marker creation and dispatch.

No update-format repair was requested. No protocol deviations were observed.
No protected evaluator-owned artifact was edited, removed, moved, or regenerated.
Usage/cost is `null`: the host did not provide consistent coordinator, worker,
and reviewer usage for paired-arm accounting.

Coordinator-written tool accounts are the lifecycle JSON/text captures,
hash/mtime CSVs, inventories, byte counts, and manifest in this evidence
directory. Exported native transcripts are separately represented only by the
worker update, reviewer verdict, and the two terminal-observation records named
above; no full native tool transcript was exported by the host.

