# Horizon state-mode Sol/Terra pilot

This directory freezes the Task 10 protocol before any measured run.  It is a
72-run comparative pilot: six fixtures × two models × two execution modes ×
three repetitions.  It is not a model API runner and it contains no measured
outcome yet.

Each row in [manifest.csv](manifest.csv) has four allowed increments and a
15-minute allowance.  Both arms use the same frozen checkout, Horizon skill,
fixture, objective, gate, review criterion, protected acceptance bytes, and
`high` reasoning setting.  The sole experimental selector is `mode`, either
`conversation` or `state`.  `gpt-5.6-sol` and `gpt-5.6-terra` are the only
models.  The manifest order is frozen: fixture order, then model, repetition,
and the prescribed alternating mode order.

The evaluator material is deliberately separated from worker material:

* [fixtures.md](fixtures.md) and `fixtures/**/*.py.txt` are the canonical,
  non-collected seed reconstruction.  A trial starts by restoring these bytes
  into a new disposable project; it never starts from a repaired copy.
* `reference-only/` proves that independent known repairs pass the unchanged
  acceptance cases.  Root and the evaluator may consult it for fixture
  validation, but it must not be copied into a trial project, packet, worker
  prompt, or coordinator context.
* `archives/` retains byte-identical Task 1–8 implementation-review and native
  smoke evidence.  Those records are historical evidence, not Task 10 runs.

Root runs one native trial at a time.  Before `doctor`, `status`, or `start`,
root must create the trial-local `.codex` or `.agents` marker in that disposable
project and use project-scoped state/home paths.  This prevents root discovery
from climbing to this checkout's ancestor marker.  Do not change host-level
Codex configuration; record any host-isolation limitation as a trial deviation.

Use [trial-briefs.md](trial-briefs.md) to instantiate a coordinator/worker
brief.  Only the listed model, mode, repeat, and environment path placeholders
may change.  `runs/<fixture>-<sol|terra>-<state|conversation>-<repeat>/` is
created only when its manifest row actually begins; it must retain the raw
command output, goal/audit bytes and hashes, worker/reviewer records, evaluator
observations, source hashes, and any protocol deviation.  Empty reserved
directories or a completed-looking JSON record are not evidence.

[results.jsonl](results.jsonl) is intentionally empty.  Append exactly one
schema-valid record only after independent evaluator scoring of a run's raw
evidence.  Preserve unknown values as JSON `null`, not zero.  The current
[report.md](report.md) is intentionally incomplete and must remain so until
actual trials or a specific external limitation are recorded.

The source and skill snapshot is [source-snapshot.md](source-snapshot.md).
The seed/repaired preflight evidence is in `evidence/preflight/`; the seed
checks are expected failures except for the initial stale-fact old contract,
and the separate reference repairs are expected to pass.  The stale parser
transition itself is an evaluator event during a measured run, not a worker
instruction to pre-repair the consumer.
