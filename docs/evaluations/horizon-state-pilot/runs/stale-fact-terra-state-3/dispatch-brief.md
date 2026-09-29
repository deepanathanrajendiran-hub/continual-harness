# Instantiated frozen trial brief

Environment values for the symbolic names in the exact common template:

- MODEL: `gpt-5.6-terra`
- MODE: `state`
- REPEAT: `3`
- TRIAL_PROJECT: `/private/tmp/horizon-state-pilot-20260928-2f65f2a/stale-fact-terra-state-3/project`
- TRIAL_HOME: `/private/tmp/horizon-state-pilot-20260928-2f65f2a/stale-fact-terra-state-3/home`
- EVIDENCE_DIR: `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/docs/evaluations/horizon-state-pilot/runs/stale-fact-terra-state-3`
- SKILL_FILE: `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.agents/skills/horizon/SKILL.md`
- HARNESS: `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.agents/skills/horizon/scripts/harness.py`
- SHARED_REFERENCE: `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.agents/skills/horizon/references/commands.md`

Seed-hash record: `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/docs/evaluations/horizon-state-pilot/runs/stale-fact-terra-state-3/seed-hashes.csv`.

## Exact lifecycle values

OBJECTIVE:
```text
Make consumer.parse follow the parser's current behavior while preserving the evaluator-owned parser change and fixed acceptance bytes.
```

GATE:
```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

REVIEW_CRITERION:
```text
Independently inspect raw lifecycle, source, gate, and evaluator evidence.
Confirm the fixed gate result; confirm every listed protected artifact has its
required hash/mtime; confirm no evaluator-owned acceptance file was removed or
edited; confirm no test was removed; confirm the fixture-specific source
obligation; and reject any reported completion that conflicts with gate or
required-review evidence. Record missing observations as unknown. Confirm consumer matches the changed parser for empty and valid input, parser.py retains the evaluator replacement hash, and the stale observation is explicitly superseded rather than treated as current evidence.
```

## Frozen coordinator instructions

You are the native coordinator for one frozen Horizon state-mode pilot row.

Environment: TRIAL_PROJECT, TRIAL_HOME, EVIDENCE_DIR, SKILL_FILE, HARNESS, and
SHARED_REFERENCE are resolved above.  Make source edits only in TRIAL_PROJECT;
write raw evidence and the report only in EVIDENCE_DIR and trial scratch only
in TRIAL_HOME.  Create the trial project's own .codex or .agents marker before
every Horizon CLI lifecycle command.  Keep state/home project scoped at
TRIAL_HOME; never repurpose global HOME or CODEX_HOME.  Read SKILL_FILE and
SHARED_REFERENCE.  The shared reference supplies the Packet and update schema;
do not access reference-only material or known repairs.

Before creating the marker or dispatching any role, run `git rev-parse
--show-toplevel` from TRIAL_PROJECT.  It must fail because TRIAL_PROJECT is
outside every Git repository; retain its exit/status output in EVIDENCE_DIR.
This pre-dispatch check prevents evaluator-created logs from changing the
fingerprint through an ancestor repository.  Then create the trial-local
.codex or .agents marker and continue the fixed lifecycle.

This row is MODEL / MODE / REPEAT, with all native coordinator, worker, and
independent reviewer roles set to MODEL at high reasoning.  You may dispatch
the native editing worker and independent reviewer needed for this row, record
their actual host handles and role boundaries, and run no other trial.  Do not
create a sidebar task or a native goal outside the trial project.  State-mode
editing roles start in fresh contexts.  Conversation-mode work retains its
conversation context except at the explicitly forced fresh-coordinator barrier.

For Python/config edits, discover the AST editor, call list_symbols, then use
the narrowest structural edit.  Pass this rule and the resolved shared Packet
and update schema to every editing worker.  No generic code-file editing
fallback.

Root has restored and hash-checked the seed before first dispatch.  Inspect the
provided seed-hash record on initial launch.  On resumption or forced
fresh-coordinator handoff, preserve and inspect the existing project and saved
goal; never restore the seed or create a replacement goal.  Treat every
protected artifact as evaluator-owned: do not edit, remove, move, or regenerate
it.  The fixed fingerprint watch input is --watch . from goal creation through
every phase; it covers source, new tests, and acceptance while Horizon's
built-in bookkeeping exclusions remain in effect.

For initial goal creation only, run these lifecycle setup commands exactly,
retaining stdout/stderr and returned goal/packet/audit bytes and hashes in
EVIDENCE_DIR:

  python3 "$HARNESS" --runtime codex --project "$TRIAL_PROJECT" doctor
  python3 "$HARNESS" --runtime codex --project "$TRIAL_PROJECT" start \
    "$OBJECTIVE" --execution "$MODE" --gate "$GATE" \
    --review "$REVIEW_CRITERION" --max-turns 4 --max-minutes 15 --watch .
  python3 "$HARNESS" --runtime codex --project "$TRIAL_PROJECT" status

For an existing supplied SLUG, do not run `start`.  Run `doctor` and
`status "$SLUG"` with the same `HARNESS` and `TRIAL_PROJECT`, then continue
that saved goal through the skill protocol while preserving its original
budgets, objective, gate, review criterion, and `--watch .` input.

Use at most four increments/attempts and 15 minutes.  Before each increment,
inspect saved status and honor the fixture barrier.  In state mode, reserve,
attach, finish, or recover only through the documented state lifecycle, with
observed worker terminal evidence before finish/recovery.  In conversation
mode, retain the prescribed conversation boundary and save the same durable
evidence.  Run the fixed gate when allowed.  Preserve source/test hashes, gate
output, packet byte counts, role records, lifecycle JSON, evaluator events,
host-handle observations, and deviations in EVIDENCE_DIR.  Report completion
only after the gate and independently recorded review pass.

Write EVIDENCE_DIR/report.md before returning.  It must record the actual goal
slug, native handles and roles, gate/review outcome, format repairs, and
protocol deviations, including the Git-isolation precheck.  Label
coordinator-written tool accounts separately from exported tool transcripts.

The reviewer independently evaluates the raw evidence and must use exactly the
frozen REVIEW_CRITERION for this fixture.  It records omissions as unknown;
completion is false if the gate or required review fails.  Usage/cost stays
null unless the host reports coordinator, worker, and reviewer usage
consistently for both paired arms.

## Selected fixture


**Objective:** Make `consumer.parse` follow the parser's current behavior while
preserving the evaluator-owned parser change and fixed acceptance bytes.

**Protected evaluator-owned artifacts:** `tests/test_acceptance.py`, SHA-256
`76c8715d5ecef2c386a754f3ed64dfda9f6d8b335b6f3c33419f0709c9b3830c`;
initial seed `parser.py`, SHA-256
`d170165014bb83537c7b470400c733c756b8971b3c743fbcabf3a6dff9865217`;
and, after the evaluator transition, replacement `parser.py`, SHA-256
`47a9b605388ad834f09374c004ca06a0149392ee3f314a5a4c6b69ded69e8420`.
The `.` fingerprint watch remains fixed before, during, and after this barrier.

**Phase barrier:** After the first saved observation/checkpoint and before the
next increment, the evaluator replaces only `parser.py` with this exact source:

```python
def parse_number(value):
    if value == "":
        raise ValueError("empty input is invalid")
    return int(value)
```

The evaluator records the event outside worker-owned state and releases the
coordinator.  The objective, gate, review criterion, `.` watch input, and
acceptance file never change.  The worker repairs `consumer.py`, preserves the
evaluator-provided parser bytes, and does not promote stale evidence as current.

**Review suffix:** `Confirm consumer matches the changed parser for empty and
valid input, parser.py retains the evaluator replacement hash, and the stale
observation is explicitly superseded rather than treated as current evidence.`
