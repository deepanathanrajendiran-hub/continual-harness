# Horizon state-mode pilot report — incomplete

Three of 72 canonical manifest rows have been scored, all passing acceptance
and independent review, with no false completion or fixture-observed regression.
The first paired
module-bug / Sol comparison passed acceptance and independent review in both
modes, with one editing increment each, no false completion, and no
fixture-observed regression. The state /
repeat 1 passed acceptance and independent review with one accepted attempt,
one checkpoint, an 1819-byte packet, and no coordinator-reported formatting
repair. The evaluator verified the protected test's hash and nanosecond mtime.
There was no false completion or fixture-observed regression. The worker
explicitly lacked an external protected-file baseline in its packet; the
coordinator and evaluator recovered the exact comparison from the seed record.

This run exceeded its 15-minute wall budget while waiting for an attached
worker. The coordinator late-finished the existing terminal attempt without
extending the budget or opening another attempt. A pre-goal usage interruption
also prevents a clean dispatch-time comparison. `elapsed_seconds`, total tokens,
cost, and unavailable complete event metrics remain null. Goal start to
completion was 2063.934759 seconds, including external waiting. Raw evidence is
in `runs/module-bug-sol-state-1/isolated-rerun/`.

The paired conversation run finished within its budget: 354.825291 seconds
from goal start to completion, or 400.703097 seconds from root post-dispatch
observation to persisted goal completion. These are wall times, not active
compute measurements. Its protected acceptance and checkout hashes/mtimes
were unchanged, and it used one checkpoint and no state packet. Evidence is
in `runs/module-bug-sol-conversation-1/`.

The third row, conversation repeat 2, also passed in one checkpoint. Goal-only
wall time was 336.261403 seconds; its pre-goal usage interruption makes original
dispatch elapsed unavailable. This worker returned state-style JSON and the
coordinator requested one formatting repair, although conversation lifecycle
does not require update JSON. That extra role behavior is retained as a
deviation, not silently treated as necessary conversation overhead. A reviewer
reported missing terminal-result evidence; the coordinator subsequently saved
the actual host-delivered final and disclosed the visibility discrepancy.
Evidence is in `runs/module-bug-sol-conversation-2/`.

The fourth row, state repeat 2, is active. The remaining 68 rows have prepared
briefs but have not run.

The original module-bug / Sol /
state / repeat 1 run is retained as supplemental raw evidence but excluded from
the comparison: it completed with two accepted attempts, a reported format-only
repair, passing gate and independent review, then required a second no-edit
attempt/review because evaluator-log changes in an ancestor Git repository
changed its fingerprint.  The setup probe retained at
`evidence/environment-isolation-probe.txt` distinguishes this from a product
defect. Its outcome remains supplemental and is not a second canonical row.

This single correctness comparison supplies no basis for a mode superiority
or recovery claim. The state arm's external interruption prevents a useful
paired efficiency comparison.

When raw trial evidence exists, independently score one JSON object per
manifest row in `results.jsonl` and replace this section with raw counts by
fixture, model, and mode.  Keep model usage and cost `null` unless the host
reports coordinator, worker, and reviewer usage consistently in both arms.
Packet bytes are not billed-token or total-context estimates.  Describe
different turn semantics, unavailable hosts, aborted launches, actual handoff
and interruption observations, and deviations.  This remains a pilot of the
combined structured-state/fresh-worker feature; it cannot attribute a result to
one component or generalize beyond the sample.
