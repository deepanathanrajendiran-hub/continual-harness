# Root-instantiable measured-trial briefs

This is the frozen coordinator dispatch protocol.  For a manifest row, root may
substitute only the following declared values.  `OBJECTIVE`, `GATE`,
`REVIEW_CRITERION`, watch input, source obligation, protected-artifact hashes,
phase barriers, reasoning setting, and all other instructions remain the fixed
fixture values below.

```text
MODEL = gpt-5.6-sol | gpt-5.6-terra
MODE = conversation | state
REPEAT = 1 | 2 | 3
TRIAL_PROJECT = absolute disposable project path outside any Git repository
TRIAL_HOME = absolute trial-scoped state/home path
EVIDENCE_DIR = absolute manifest-matched run-evidence path
SKILL_FILE = absolute frozen .agents/skills/horizon/SKILL.md path
HARNESS = absolute scripts/harness.py beside SKILL_FILE
SHARED_REFERENCE = absolute frozen .agents/skills/horizon/references/commands.md
```

`SKILL_FILE`, `HARNESS`, and `SHARED_REFERENCE` are environment/path
substitutions, not invitations to use a global skill or repaired fixture.  The
shared reference may be read by coordinator, worker, and reviewer; the
`reference-only/` directory must never be copied into a trial project, packet,
worker prompt, coordinator context, or reviewer prompt.

`TRIAL_HOME` is a trial-local native-role scratch/state location, never a global
home override.  The CLI's durable state is selected by the trial-local marker
and `--project "$TRIAL_PROJECT"`; the lifecycle commands do not set `HOME` or
`CODEX_HOME`.

## Common coordinator dispatch template

```text
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
```

## Common fixed lifecycle values

```text
GATE = PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
WATCH = .
MAX_TURNS = 4
MAX_MINUTES = 15
```

Every fixture starts with and retains the exact CLI fingerprint argument
`--watch .` from `start` through every barrier and recovery.  It is a source
fingerprint input, not a preservation list.
Each fixture separately identifies protected evaluator-owned artifacts below.

The immutable common review criterion is:

```text
Independently inspect raw lifecycle, source, gate, and evaluator evidence.
Confirm the fixed gate result; confirm every listed protected artifact has its
required hash/mtime; confirm no evaluator-owned acceptance file was removed or
edited; confirm no test was removed; confirm the fixture-specific source
obligation; and reject any reported completion that conflicts with gate or
required-review evidence. Record missing observations as unknown.
```

For every row, construct the exact `REVIEW_CRITERION` by concatenating that
common string, one space, and the fixture's **review suffix** below.  Root must
not invent, omit, or reword a criterion.

## module-bug

**Objective:** Fix the checkout integration and the underlying discount defect:
`total([100, 200], 10)` must be 270, the empty cart 0, and zero discount must
preserve the total.

**Protected evaluator-owned artifact:** `tests/test_acceptance.py`, SHA-256
`cb50420a69e7abef79d5b50043ef39e82bfbffb16edb1b58b0f4202d5693442d`.

**Review suffix:** `Confirm checkout.total still uses pricing.discounted and
the price calculation applies the discount once.`

## api-refactor

**Objective:** Rename `normalize` to `normalize_name` in `names.py`, update
both project callers, and retain `normalize` as a compatibility alias.  Both
names must trim/case-fold identically and existing imports must stay valid.

**Protected evaluator-owned artifact:** `tests/test_acceptance.py`, SHA-256
`cabb3c9379120181bc94744b6915cd9add3bb489c5009cf8553d532928ce9297`.

**Review suffix:** `Confirm greet.py and tags.py import and use normalize_name,
while the old normalize symbol remains a working compatibility alias.`

## test-repair

**Objective:** Repair `parse_count` validation and add regression tests without
removing tests.  Positive decimal strings and zero pass; booleans, negative
values, and malformed strings raise `ValueError`.

**Protected evaluator-owned artifact:** `tests/test_acceptance.py`, SHA-256
`0dd145fbaa42b2393bf9f3d12c0017401b464005afd88a9f020daf84be2e35d5`.

**Review suffix:** `Confirm validation rejects booleans and negative values
before returning a count.`

## checkpoint-handoff

**Objective:** Preserve the completed `foundation.slug` implementation, then
add `delivery.slugs(values)` using it so mapped and empty-list output pass.

**Protected evaluator-owned artifacts:** `tests/test_acceptance.py`, SHA-256
`949adcf37b09bd6ffeb49d55e5fc9a198d10ecc2c485a45fc68f31b2945b9f54`; and
`foundation.py`, seed SHA-256
`8748b469317b07cb9de810c6504c4f24806c7738db4977f07a7d29d33486ad72`,
whose mtime and bytes must remain unchanged after seed copy and throughout the
fresh-coordinator handoff.

**Phase barrier:** The initial coordinator's first increment only inspects
`foundation.py` and saves a checkpoint recording its completed state.  It must
not implement `delivery.py`.  Root then starts a fresh coordinator with
`fork_turns: none`, supplying only the goal slug, workspace location, resolved
runtime/skill/editor environment, and this same fixture brief.  It must not
receive the first coordinator conversation or a reference repair.

**Review suffix:** `Confirm delivery.slugs delegates to foundation.slug and
foundation.py bytes and mtime are unchanged across the forced handoff.`

## interrupted-edit

**Objective:** Fix CSV rendering for embedded commas and the empty row while
preserving the observed partial edit through recovery.

**Protected evaluator-owned artifact:** `tests/test_acceptance.py`, SHA-256
`51741aad445173fc00caa9c95ccd3bde03a74227f8b67bd3976f1d589dca9a1f`.

**Phase barrier:** After the worker's first relevant source edit, it reports the
actual changed path and waits before returning its update or invoking `check`,
as the selected mode permits.  The evaluator verifies that edit, interrupts the
actual live native worker handle, records its terminal observation, and releases
the coordinator to perform that mode's recovery procedure.  Preserve the edit;
do not reset the workspace, duplicate a reservation/gate, or claim completion
without observed recovery.

**Review suffix:** `Confirm output quotes embedded commas, empty output is an
empty string, and raw evidence proves the observed edit, actual interruption,
and recovery without duplicate reservation/gate or false completion.`

## stale-fact

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
