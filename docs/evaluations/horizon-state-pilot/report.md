# Horizon state-mode pilot report — incomplete

No measured native trial has run as of the protocol-freeze commit.  There are
therefore no success counts, false-completion counts, recovery outcomes,
elapsed-time measurements, packet sizes, token totals, costs, or mode claims
to report.

When raw trial evidence exists, independently score one JSON object per
manifest row in `results.jsonl` and replace this section with raw counts by
fixture, model, and mode.  Keep model usage and cost `null` unless the host
reports coordinator, worker, and reviewer usage consistently in both arms.
Packet bytes are not billed-token or total-context estimates.  Describe
different turn semantics, unavailable hosts, aborted launches, actual handoff
and interruption observations, and deviations.  This remains a pilot of the
combined structured-state/fresh-worker feature; it cannot attribute a result to
one component or generalize beyond the sample.
