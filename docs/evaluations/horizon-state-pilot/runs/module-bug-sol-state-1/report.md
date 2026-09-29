# Frozen Horizon state-mode pilot report

- Row: model `gpt-5.6-sol`, mode `state`, repeat `1`
- Goal slug: `fix-the-checkout-integration-and-the-underlying-discount-def`
- Final Horizon status: **complete**
- Budget used: 2 of 4 worker attempts; completion remained within the 15-minute ceiling
- Accepted checkpoint: `f300209453b11170de50dab9afd7ccfa49d084a2d859c7fb6dacd44e822261be`
- Gate: **pass** — exact command ran one test, with zero failures and `OK`
- Independent review: **pass** — judge `/root/pilot_module_bug_sol_state_1/independent_reviewer_2`
- Usage/cost: null; the host did not report consistent usage for all roles

## Actual outcome

The defect was fixed in `pricing.discounted`: it now returns `amount * (100 - percent) // 100`, applying the requested discount exactly once. `checkout.total` remains unchanged and still delegates every amount to `pricing.discounted`. The acceptance gate confirms `total([100, 200], 10) == 270`, an empty cart totals 0, and a zero discount preserves 300.

The protected evaluator artifact `tests/test_acceptance.py` retained SHA-256 `cb50420a69e7abef79d5b50043ef39e82bfbffb16edb1b58b0f4202d5693442d` and mtime_ns `1790575157073913255`; its test method and all three assertions remain. `checkout.py` also remained byte-identical to seed. Final hashes and packet byte counts are in `artifact-hashes.csv`.

## Native roles

- Coordinator: `/root/pilot_module_bug_sol_state_1`
- Editing worker: `/root/pilot_module_bug_sol_state_1/state_worker_request_001`
- Fresh verification worker: `/root/pilot_module_bug_sol_state_1/state_worker_request_002`
- Current independent reviewer: `/root/pilot_module_bug_sol_state_1/independent_reviewer_2`

Role boundaries and terminal host observations are in `role-records.md` and the worker evidence files. Coordinator-written tool accounts are labeled separately; no complete exported worker tool transcript was available.

## Format repairs and deviations

The first worker update required one permitted formatting-only repair: two `set` operations used `path` instead of the required `field`. No implementation change was requested during that repair.

Checkpoint 1 passed, but the harness rejected its review because a newly created evidence-file path changed the Git-status portion of the fingerprint after verification. The coordinator recorded the rejection, predeclared all remaining evidence paths, and used request-002 with a fresh no-edit worker to create a new stable checkpoint. A fresh reviewer passed that exact checkpoint, and the harness then completed the goal. Full details are in `protocol-events.md`.

## Evidence

The lifecycle record runs from `lifecycle-00-doctor.txt` through `lifecycle-14-status-final.txt`. The final gate is in `raw-gate-output.txt`; the accepted independent verdict is in `independent-review-2.txt`; source inspection is in `coordinator-source-inspection.txt`.
