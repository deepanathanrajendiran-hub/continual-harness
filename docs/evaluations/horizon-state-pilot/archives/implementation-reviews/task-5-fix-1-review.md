### Finding Verdicts

- **Complete checkpoint/review excerpts exceed the 2 KiB serialized allowance** — **ADDRESSED**. `harness/task_state.py:418` makes `_packet_excerpt` measure the full envelope with the candidate verdict, and `harness/task_state.py:447` plus `harness/task_state.py:461` pass the checkpoint and review envelopes into that calculation. Future reservation projections use the same envelope-aware calculation at `harness/task_state.py:475`. Tests assert the complete long-text projections and reserved projections are at most 2,048 bytes (`tests/test_task_state.py:334`, `tests/test_task_state.py:362`) and assert maximal-metadata checkpoint and review projections serialize to exactly 2,048 bytes (`tests/test_task_state.py:445`).

### New Breakage in the Fix Diff

- None. The helper retains its original behavior when no envelope is supplied, actual packet excerpts still contain real text, and reservation padding remains confined to the measured copy.

### Out-of-Scope Observations

- The previously recorded duplicate-regex/repeated-`_KINDS` Minor remains outside this fix round and does not block this verdict.

### Checks

- Read the supplied `fd9c0c5..422f3a4` fix diff once and compared it to the verbatim prior finding; no source files or git state were read separately.
- The appended fix report provides RED evidence for the original 2,162-byte checkpoint overflow and missing envelope API, then GREEN evidence of `3 passed in 0.03s` for the long and exact-boundary cases. It also reports `112 passed in 7.69s` for `tests/test_task_state.py tests/test_horizon_steps.py`, clean `git diff --check`, and successful compilation. I did not rerun those suites.

### Verdict

**Fix round:** All findings addressed, no new Critical/Important breakage.
