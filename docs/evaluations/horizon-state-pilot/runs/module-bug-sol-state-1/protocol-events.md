# Protocol events and deviations

1. Seed hashes were inspected before launch. `checkout.py`, `pricing.py`, and protected `tests/test_acceptance.py` matched the supplied seed hashes; the protected test also matched its required nanosecond mtime.
2. The coordinator ran the exact doctor, start, and initial status lifecycle. Goal slug: `fix-the-checkout-integration-and-the-underlying-discount-def`; execution: state; watch: `.`; budget: four attempts and 15 minutes.
3. Request-001 was reserved, attached to the actual editing-worker handle, observed terminal, and accepted. The worker's first JSON used `path` instead of `field` for set ops. One permitted formatting-only repair request produced valid JSON. This was the only format repair.
4. Checkpoint 1 passed the exact gate. The first independent reviewer returned PASS. Recording that review failed with `GateNotPassed: Artifacts changed after verification; run the gate again.` The new evidence-file path had changed Git porcelain, which is part of the fingerprint. No stale review or completion was accepted.
5. All remaining evidence paths were predeclared before request-002. Request-002 used a fresh worker and no source edits; it re-inspected the fixed code and protected test. The harness accepted a fresh passing gate checkpoint at tree hash `f300209453b11170de50dab9afd7ccfa49d084a2d859c7fb6dacd44e822261be`.
6. A new independent reviewer passed the exact criterion for checkpoint 2. The harness recorded the review and completed the goal.
7. Final source/test hashes and the protected mtime were rechecked. The current fingerprint independently recomputes to the accepted checkpoint hash.

Protocol deviations: one stale-review rejection and one additional no-edit state attempt were required because an evidence path changed the repository-status component of the watched fingerprint. No protected artifact was edited; no test was removed; no worker was duplicated for an active attempt; no lifecycle command was delegated to a worker.
