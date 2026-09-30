# Frozen pilot report: module-bug-sol-state-2

## Outcome

- Result: **complete / pass**
- Goal slug: `fix-the-checkout-integration-and-the-underlying-discount-def`
- Model, mode, repeat: `gpt-5.6-sol`, `state`, `2`
- Attempts used: `1 / 4`
- Final execution revision: `7`
- Checkpoint tree hash: `c5dec7772338bdc483e707136114e37f6949ee1df6c3a978dc3b079e05221d8f`
- Change: `pricing.discounted` now returns `amount * (100 - percent) // 100`, so the percentage is applied once. `checkout.total` remains unchanged and still sums `pricing.discounted(amount, percent)`.

## Native roles

- Coordinator: `/root/pilot_module_bug_sol_state_2`; lifecycle commands, evidence capture, completion decision.
- Editing worker: `/root/pilot_module_bug_sol_state_2/native_worker_001`; fresh context, `gpt-5.6-sol` high, one implementation increment and one schema-version-1 update.
- Independent reviewer: `/root/pilot_module_bug_sol_state_2/independent_reviewer`; fresh context, `gpt-5.6-sol` high, read-only evaluation against the exact frozen criterion.
- Editing and review roles were distinct. Both reached host-observed terminal completed status before their lifecycle results were accepted.

## Gate and review

- Frozen gate: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`
- Harness gate result: exit `0`; `1` test ran, `0` failures, `OK`.
- Fresh coordinator pre-completion gate: exit `0`; `1` test ran, `0` failures, `OK`.
- Independent review: **PASS**. The reviewer also reran the exact gate read-only and observed the same pass.
- Protected `tests/test_acceptance.py`: SHA-256 `cb50420a69e7abef79d5b50043ef39e82bfbffb16edb1b58b0f4202d5693442d`, mtime_ns `1790650615706767718`; both equal the seed record.
- No test was removed. Test inventory remained exactly `tests/test_acceptance.py`.
- `checkout.py` remained at seed hash `82de323e0cddff692abb6cea7fc7ff3ed6794a769bb5b48ec39edbf36fd103bb` and still imports/calls `pricing.discounted`.
- Final `pricing.py` SHA-256: `d90b510771d75fa0fbc4b7b42115c97812bbb6e3d494d56e9b495925f38a2a12`.

## Isolation and lifecycle evidence

- Before marker creation or dispatch, `git rev-parse --show-toplevel` failed as required with exit `128`: the trial project is outside every Git repository.
- The trial-local `.codex` marker was then created. State remained project-local under the trial project, and lifecycle commands ran with working directory under `TRIAL_HOME`.
- Initial `doctor`, `start`, and `status` outputs are retained. The start used state mode, the exact objective/gate/review, `--max-turns 4`, `--max-minutes 15`, and `--watch .`.
- Packet bytes/hash, final goal/audit bytes/hash, attempt audit-object bytes/hash, update, worker/reviewer terminal observations, source hashes/mtimes, gate outputs, lifecycle JSON, and evaluator phase barriers are retained in this directory.

## Repairs, deviations, and accounting

- Update-format repairs: none.
- Recovery operations: none.
- Protocol deviations: none observed.
- Reviewer omission recorded as unknown: the reviewer did not independently recompute the harness checkpoint tree-hash algorithm because lifecycle commands were prohibited; it confirmed the recorded hash from raw step-finish evidence and corroborated the snapshot with direct source/hash inspection. This did not conflict with any required evidence.
- Full native tool transcripts were not exposed by the host. Native final outputs are stored separately from coordinator-written tool accounts in `worker-final-001.txt`, `independent-review.txt`, and `coordinator-tool-account.md`.
- Usage/cost: `null`; the host did not report coordinator, worker, and reviewer usage consistently.
