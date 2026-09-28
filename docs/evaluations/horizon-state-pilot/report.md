# Horizon state-mode pilot report — incomplete

No canonical manifest row has been scored.  The original module-bug / Sol /
state / repeat 1 run is retained as supplemental raw evidence but excluded from
the comparison: it completed with two accepted attempts, a reported format-only
repair, passing gate and independent review, then required a second no-edit
attempt/review because evaluator-log changes in an ancestor Git repository
changed its fingerprint.  The setup probe retained at
`evidence/environment-isolation-probe.txt` distinguishes this from a product
defect.  Its canonical isolated rerun is pending at
`runs/module-bug-sol-state-1/isolated-rerun/`; `results.jsonl` remains empty.

There are therefore no canonical success counts, false-completion counts,
recovery outcomes, elapsed-time measurements, packet sizes, token totals,
costs, or mode claims to report.

When raw trial evidence exists, independently score one JSON object per
manifest row in `results.jsonl` and replace this section with raw counts by
fixture, model, and mode.  Keep model usage and cost `null` unless the host
reports coordinator, worker, and reviewer usage consistently in both arms.
Packet bytes are not billed-token or total-context estimates.  Describe
different turn semantics, unavailable hosts, aborted launches, actual handoff
and interruption observations, and deviations.  This remains a pilot of the
combined structured-state/fresh-worker feature; it cannot attribute a result to
one component or generalize beyond the sample.
