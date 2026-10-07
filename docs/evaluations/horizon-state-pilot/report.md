# Horizon state-mode pilot report — incomplete

Seventeen of 72 (17/72) canonical manifest rows have been scored: fourteen completed
with passing acceptance and independent review; rows five, thirteen and sixteen are
incomplete after external interruptions.
No false completion was observed, and no fixture-observed regression was found
among rows with final verification. Row thirteen's final regression state is
unknown.
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

The fourth row, state repeat 2, passed in one accepted attempt with no reported
formatting repair. Its packet was 1820 bytes, goal wall time was 338.98915
seconds, and root post-dispatch to goal completion was 465.534524 seconds.
Protected hash/mtime and immutable controls passed evaluator checks. Evidence
is in `runs/module-bug-sol-state-2/`.

The fifth row, state repeat 3, stopped after its worker edited pricing but hit a
host usage limit before returning a usable update. One recovery closed the
attempt, preserved the edit, and recorded a failed checkpoint. Its 15-minute
budget expired during an overnight interruption. Root's separate acceptance
check passed, but the Horizon gate and independent review did not run, so the
goal is incomplete. Its saved review criterion also collapsed the frozen line
breaks; normalized words match, bytes do not. Both deviations remain in its
canonical record and [raw evidence](runs/module-bug-sol-state-3/).

The sixth row, conversation repeat 3, passed in one checkpoint within budget.
Its worker edited both checkout and pricing so checkout calls
`pricing.discounted` dynamically. Root verified the frozen gate, protected
acceptance hash/mtime, and exact controls; the reviewer independently checked
the module integration. Goal wall time was 654.49199 seconds, with 800.040653
seconds from root dispatch to persisted completion. Evidence is in
`runs/module-bug-sol-conversation-3/`.

The first Terra run, state repeat 1, passed in one accepted attempt with a
1844-byte packet and no reported format repair. Goal wall time was 251.581996
seconds, with 266.990596 seconds from root dispatch to completion. Its
protected acceptance and unchanged checkout bytes/mtimes match the seed.
The saved state has a summary and next action but no evidence-backed entry
for the pricing edit. This is a possible handoff weakness, not an observed
handoff failure. Evidence is in `runs/module-bug-terra-state-1/`.

The paired Terra conversation repeat 1 also passed in one checkpoint, with
goal wall time 270.809415 seconds and 299.427658 seconds from root dispatch to
completion. Its worker returned state-style JSON without a formatting repair.
The saved review criterion collapsed frozen line breaks; the words match but
the bytes differ. That deviation limits a strict paired comparison. Evidence
is in `runs/module-bug-terra-conversation-1/`.

Terra conversation repeat 2 passed in one checkpoint with exact frozen
controls and no reported format repair. Goal wall time was 278.082121 seconds;
root dispatch to completion was 286.072359 seconds. The protected acceptance
and checkout bytes/mtimes matched seed. Evidence is in
`runs/module-bug-terra-conversation-2/`.

Terra state repeat 2 passed in one accepted attempt with one evidence-backed
state observation and no reported format repair. Checkout dynamically calls
`pricing.discounted`, which applies the percentage once. Goal wall time was
312.097267 seconds, with 324.591123 seconds from root dispatch to persisted
completion; its packet was 1821 bytes. Protected acceptance hash/mtime and
frozen controls passed evaluator checks. Evidence is in
`runs/module-bug-terra-state-2/`.

Terra state repeat 3 passed in one accepted attempt, with a passing fixed gate
and independent review, exact frozen controls, protected acceptance hash/mtime,
and no reported format repair. Its 1821-byte packet accompanied an elapsed
289.089398 seconds from root dispatch to completion and 261.423992 seconds of
goal wall time. Like Terra state repeat 1, its saved summary and next action
had no evidence-backed entry for the pricing edit. This is a state omission,
not an observed handoff failure. Evidence is in
`runs/module-bug-terra-state-3/`.

Terra conversation repeat 3 passed in one checkpoint, with the exact frozen
criterion, passing fixed gate and independent review, and preserved protected
acceptance hash/mtime. Elapsed time from root dispatch to completion was
393.153669 seconds; goal wall time was 337.951126 seconds. Its worker returned
optional state-style JSON with null attempt fields, but no format repair or
extra worker launch followed. A post-completion hash command from the wrong
directory was corrected without source mutation. Evidence is in
`runs/module-bug-terra-conversation-3/`.

The first api-refactor / Sol conversation row reached a passing checkpoint
and recorded independent review, then its coordinator hit a host usage limit
before completion. On the October 6 resumption, the temporary project and
goal had no remaining files. Its durable source account supplied four
hash-verified historical snapshots, but its final live acceptance/regression
check is unavailable. The same coordinator reported incomplete without
recreating the goal or source. The initial command-wrapper SyntaxError and
reviewer's excluded cache creation are retained. Evidence is in
`runs/api-refactor-sol-conversation-1/`.

The api-refactor / Sol state repeat 1 row passed in one accepted attempt with
the exact frozen controls, preserved protected test hash/mtime, a passing fixed
gate, and matching independent review. Its 1897-byte packet accompanied
396.012075 seconds from root dispatch to saved completion and 309.470892 seconds
of goal wall time. The saved state contains summary and next action but no
evidence-backed entry for the rename or caller changes. This is a possible
handoff weakness, not an observed handoff failure. Ten final files are archived
in `runs/api-refactor-sol-state-1/`.

The api-refactor / Sol state repeat 2 row passed in one accepted attempt with
exact controls and protected test hash/mtime. One permitted formatting-only
follow-up repaired the worker's initial JSON envelope without changing its
reported work or saved summary/next action. Its state entries remain empty.
Root independently recomputed the passing checkpoint/review hash, resolving a
reviewer unknown. Packet size was 1890 bytes; elapsed time was 347.658905
seconds from root dispatch and 307.346654 seconds from goal start. The
coordinator reports 28.9 seconds across seven scoped-write round trips,
including permission review and transport; that account does not isolate
approval overhead. Ten final files are archived in
`runs/api-refactor-sol-state-2/`.

The api-refactor / Sol conversation repeat 2 row stopped on an external host
usage limit after worker launch, before any durable source edit or checkpoint.
The original fifteen-minute budget expired overnight. Its persistent project
survived with exact seed hashes/mtimes, controls and goal; the same coordinator
resumed only to inspect and export the incomplete state. The external evaluator
check fails on the seed's missing new function name. No Horizon gate/review ran,
no false completion occurred, and no source regression was introduced. Five
final source/goal files are archived in `runs/api-refactor-sol-conversation-2/`.
Elapsed and usage/cost remain unknown; the reported 7.2-second scoped-write
call is a combined tool round trip, not isolated approval latency.

The api-refactor / Sol conversation repeat 3 row passed in one checkpoint with
the exact controls, protected hash/mtime, fixed gate and matching independent
review. The plain worker report needed no format repair. A Git-precheck capture
wrapper was corrected before role dispatch without project mutation. The
reviewer disclosed a read-only gate rerun; root independently recomputed the
checkpoint hash to resolve its hashing unknown. Elapsed time was 501.561164
seconds from root dispatch and 432.691424 seconds from goal start. Five final
source/goal files are archived in `runs/api-refactor-sol-conversation-3/`.

The 55 later rows have prepared briefs but have not run. Their empty temporary projects were
restored into a persistent directory outside Git with exact
seed bytes and original per-row nanosecond mtimes. Only allowed project/home
path substitutions changed. Original briefs and Git observations are retained
in [environment migration evidence](evidence/environment-migration.md). The
path transition and any sandbox approval overhead limit timing comparisons
with earlier rows; all frozen source and control values remain unchanged.

The original module-bug / Sol /
state / repeat 1 run is retained as supplemental raw evidence but excluded from
the comparison: it completed with two accepted attempts, a reported format-only
repair, passing gate and independent review, then required a second no-edit
attempt/review because evaluator-log changes in an ancestor Git repository
changed its fingerprint.  The setup probe retained at
`evidence/environment-isolation-probe.txt` distinguishes this from a product
defect. Its outcome remains supplemental and is not a second canonical row.

These small-fixture paired observations supply no basis for a mode
superiority or recovery claim. External interruptions, incomplete state and
conversation arms, unavailable final verification after temporary-file loss,
review-criterion byte deviations, and the extra JSON repair in
conversation repeat 2 prevent clean paired efficiency comparisons.

When raw trial evidence exists, independently score one JSON object per
manifest row in `results.jsonl` and replace this section with raw counts by
fixture, model, and mode.  Keep model usage and cost `null` unless the host
reports coordinator, worker, and reviewer usage consistently in both arms.
Packet bytes are not billed-token or total-context estimates.  Describe
different turn semantics, unavailable hosts, aborted launches, actual handoff
and interruption observations, and deviations.  This remains a pilot of the
combined structured-state/fresh-worker feature; it cannot attribute a result to
one component or generalize beyond the sample.
