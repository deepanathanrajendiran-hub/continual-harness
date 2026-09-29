PASS

Evidence: fresh gate run passed `test_total_and_boundaries`; 1 test ran, `OK`. Recomputed tree hash is `9c194161eec7b1885b9892bdb0848a314b6bf737e1a07b76c7e76f624c6de87e`, matching the checkpoint. `tests/test_acceptance.py` remains present with required SHA-256 `cb50420a69e7abef79d5b50043ef39e82bfbffb16edb1b58b0f4202d5693442d` and mtime_ns `1790650615692122880`; its unchanged seed hash proves it was not edited, and the sole seeded test remains. `checkout.total` still calls `discounted` imported from `pricing`, while `pricing.discounted` computes `amount * (100 - percent) // 100`, applying the discount once. This satisfies 270, empty-cart 0, and zero-discount 300. Git-isolation evidence records the required non-repository exit 128.

Unknowns: a full exported worker tool transcript and host usage/cost are absent; neither is required by the frozen acceptance criterion.
