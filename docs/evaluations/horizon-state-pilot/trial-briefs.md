# Root-instantiable measured-trial briefs

For a row in `manifest.csv`, root substitutes only these declared values:

```text
MODEL = gpt-5.6-sol | gpt-5.6-terra
MODE = conversation | state
REPEAT = 1 | 2 | 3
TRIAL_PROJECT = absolute disposable project path
TRIAL_HOME = absolute trial-scoped state/home path
EVIDENCE_DIR = absolute run evidence path
```

No source repair, acceptance edit, objective, command, review criterion,
fixture detail, or reasoning setting may be substituted.  Start from the
non-collected seed representation, restore its original runtime filenames, and
verify every listed SHA before dispatch.  Create `.codex` or `.agents` within
`TRIAL_PROJECT` before any Horizon CLI command.  Keep `TRIAL_HOME` project
scoped; never repurpose global `HOME` or `CODEX_HOME`.

All roles use `MODEL` at `high` reasoning and the frozen shared Horizon skill.
The coordinator records actual native host handles and role boundaries.  It
allows at most four increments/attempts and 15 minutes.  State-mode editing
roles receive fresh contexts.  Conversation mode preserves its conversation
context except at the explicitly forced fresh-coordinator handoff.  Acceptance
files are evaluator-owned: workers must neither edit, remove, move, nor
regenerate them.  The evaluator hashes protected files before and after work.
The normal gate is exactly:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Each review checks the command output; protected acceptance hashes; the stated
source obligation; any removed tests; required evaluator dependency/foundation
preservation; and whether a complete report conflicts with gate/review evidence.
It records missing observations as unknown.  Completion must remain false when
the gate or required review fails.

## module-bug

**Objective:** Fix the checkout integration and the underlying discount defect:
`total([100, 200], 10)` must be 270, the empty cart 0, and zero discount must
preserve the total.  Preserve the protected acceptance file.

**Watch list:** `tests/test_acceptance.py` (SHA-256
`cb50420a69e7abef79d5b50043ef39e82bfbffb16edb1b58b0f4202d5693442d`).

**Review-specific obligation:** `checkout.total` still uses `pricing.discounted`
and the price calculation applies the discount once.

**Initial coordinator/worker brief:** Work only in `TRIAL_PROJECT` on this
objective using `MODEL`, `MODE`, and `REPEAT`.  Inspect the seed and current
state before editing.  Use the frozen shared Horizon skill, record concrete
evidence, respect the four-attempt/15-minute bound, and run the exact gate.
Do not access `reference-only/` or any known repair.

## api-refactor

**Objective:** Rename `normalize` to `normalize_name` in `names.py`, update
both project callers, and retain `normalize` as a compatibility alias.  Both
names must trim/case-fold identically and existing imports must stay valid.

**Watch list:** `tests/test_acceptance.py` (SHA-256
`cabb3c9379120181bc94744b6915cd9add3bb489c5009cf8553d532928ce9297`).

**Review-specific obligation:** `greet.py` and `tags.py` import/use
`normalize_name`; the old `normalize` symbol remains a working compatibility
alias, rather than merely passing behavior coincidentally.

**Initial coordinator/worker brief:** Work only in `TRIAL_PROJECT` on this
objective using `MODEL`, `MODE`, and `REPEAT`.  Inspect callers and imports
before editing, use the frozen shared Horizon skill, retain compatibility, and
run the exact gate.  Do not access `reference-only/` or any known repair.

## test-repair

**Objective:** Repair `parse_count` validation and add regression tests without
removing tests.  Positive decimal strings and zero pass; booleans, negative
values, and malformed strings raise `ValueError`.

**Watch list:** `tests/test_acceptance.py` (SHA-256
`0dd145fbaa42b2393bf9f3d12c0017401b464005afd88a9f020daf84be2e35d5`).

**Review-specific obligation:** validation rejects booleans and negative values
before returning a count; no tests were removed.

**Initial coordinator/worker brief:** Work only in `TRIAL_PROJECT` on this
objective using `MODEL`, `MODE`, and `REPEAT`.  Use the frozen shared Horizon
skill, preserve evaluator acceptance, add any regression coverage without
deleting tests, and run the exact gate.  Do not access `reference-only/` or any
known repair.

## checkpoint-handoff

**Objective:** Preserve the completed `foundation.slug` implementation, then
add `delivery.slugs(values)` using it so mapped and empty-list output pass.

**Watch list:** `tests/test_acceptance.py` (SHA-256
`949adcf37b09bd6ffeb49d55e5fc9a198d10ecc2c485a45fc68f31b2945b9f54`) and
`foundation.py` (seed SHA-256
`8748b469317b07cb9de810c6504c4f24806c7738db4977f07a7d29d33486ad72`).

**Phase barrier:** The initial coordinator uses its first increment only to
inspect `foundation.py` and save a checkpoint that records its completed state.
It must not implement `delivery.py`.  Root then starts a fresh coordinator with
`fork_turns: none`, giving only the goal slug, workspace location, required
runtime/skill/editor environment, and this same fixture brief.  It must not
receive the first coordinator's conversation or a reference repair.  Record
foundation bytes and mtime after seed copy and before work, then verify both
unchanged after the fresh-coordinator handoff.

**Review-specific obligation:** `delivery.slugs` delegates to `foundation.slug`;
`foundation.py` bytes and mtime are unchanged across the forced handoff.

**Initial coordinator/worker brief:** Work only in `TRIAL_PROJECT` on this
objective using `MODEL`, `MODE`, and `REPEAT`.  Obey the first-increment barrier
exactly, use the frozen shared Horizon skill, preserve evaluator acceptance, and
run the exact gate.  Do not access `reference-only/` or any known repair.

## interrupted-edit

**Objective:** Fix CSV rendering for embedded commas and the empty row while
preserving the observed partial edit through recovery.

**Watch list:** `tests/test_acceptance.py` (SHA-256
`51741aad445173fc00caa9c95ccd3bde03a74227f8b67bd3976f1d589dca9a1f`).

**Phase barrier:** After the worker's first relevant source edit, it reports the
actual changed path and waits before returning its update or invoking `check`,
as the selected mode permits.  The evaluator verifies that edit, interrupts the
actual live native worker handle, records its terminal observation, and releases
the coordinator to perform that mode's recovery procedure.  Preserve the edit;
do not reset the workspace, duplicate a reservation/gate, or claim completion
without observed recovery.

**Review-specific obligation:** output correctly quotes embedded commas and
empty output is `""`; raw evidence proves the observed edit, actual interruption,
and recovery without duplicate reservation/gate or false completion.

**Initial coordinator/worker brief:** Work only in `TRIAL_PROJECT` on this
objective using `MODEL`, `MODE`, and `REPEAT`.  Use the frozen shared Horizon
skill, honor the visible pause after the first relevant edit, preserve evaluator
acceptance, and run the exact gate only when released.  Do not access
`reference-only/` or any known repair.

## stale-fact

**Objective:** Make `consumer.parse` follow the parser's current behavior while
preserving the evaluator-owned parser change and fixed acceptance bytes.

**Watch list:** `tests/test_acceptance.py` (SHA-256
`76c8715d5ecef2c386a754f3ed64dfda9f6d8b335b6f3c33419f0709c9b3830c`) and,
after the barrier, `parser.py` (new evaluator SHA-256
`47a9b605388ad834f09374c004ca06a0149392ee3f314a5a4c6b69ded69e8420`).

**Phase barrier:** After the first saved observation/checkpoint and before the
next increment, the evaluator replaces only `parser.py` with this exact source:

```python
def parse_number(value):
    if value == "":
        raise ValueError("empty input is invalid")
    return int(value)
```

The evaluator records the event outside worker-owned state and then releases the
coordinator.  The objective, command, review criterion, watch list, and
acceptance file never change.  The worker repairs `consumer.py` and preserves
the evaluator-provided parser bytes; stale state may not be promoted to current
evidence.

**Review-specific obligation:** consumer matches the changed parser for `""`
and valid numbers; parser bytes are the evaluator's new hash; the stale
observation is explicitly superseded rather than treated as current evidence.

**Initial coordinator/worker brief:** Work only in `TRIAL_PROJECT` on this
objective using `MODEL`, `MODE`, and `REPEAT`.  Use the frozen shared Horizon
skill, honor the evaluator's saved-observation barrier, preserve evaluator
acceptance and the supplied dependency change, and run the exact gate.  Do not
access `reference-only/` or any known repair.
