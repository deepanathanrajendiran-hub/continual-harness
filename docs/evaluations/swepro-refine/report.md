# SWE-bench Pro refine study: stopped at the go/no-go gate

**Result: no test phase.** Sonnet 5.5 passed 29 of the 30 practice tasks,
above the pre-registered ceiling of 26. The tasks leave too little room for
refine's notes to show a gain, so the study stopped before the notes were
frozen or any test task was run. Nothing here says whether refine helps or
hurts.

## What ran

- **Pool.** The 82 ansible tasks in SWE-bench Pro v2
  (`scaleapi/SWE-bench_Pro-os` at `66f92766`), minus the smoke-test task and one task Scale names as
  timing-sensitive.
  All 80 remaining tasks passed local validation (oracle 1, empty patch 0) on
  Colima with the agent offline except for `api.anthropic.com`.
- **Split.** Seeded 30 practice / 50 test, committed before any practice run
  (`split.json`, commit `31acc2c`).
- **Practice.** Claude Code with `anthropic/claude-sonnet-5-5`, effort high,
  solved each practice task in order. After each one, a refine session was
  told only "passed" or "failed: K of N graded tests failed" and could apply
  at most one edit to memory, skills, agents or `CLAUDE.md`.
- **Network.** Three egress probes during practice all passed.

## Gate

| | |
|---|---|
| Practice passes, in-sandbox | 29 of 30 |
| Practice passes, pristine re-grade | 29 of 30 (same failing task) |
| Pre-registered rule | stop if ≥ 26 or ≤ 4 |
| Decision | `stop_high` |
| Refine edits applied | 4, all memory (M) |
| Refine sessions with no change | 26 of 30 |
| Mean cost per agent run | $0.17 |
| Mean cost per refine session | $0.05 |
| Mean tokens per agent run | 245k |
| Seven-day usage spent on practice | about 1% |
| Projected seven-day usage of the test phase | about 8% |

## What refine learned

With one failure to learn from, refine wrote four memory notes, all general
working habits rather than task answers:

- **Verify each spec requirement.** On tasks with a detailed requirements
  list, exercise every bullet with a throwaway mock-based script; the
  existing unit tests only cover old behaviour.
- **Pytest reruns and baseline.** This checkout injects `--reruns=3`; pass
  `--reruns=0`, and check a failing test on a stashed baseline before
  blaming the change.
- **Keep slow checks separate.** Run edits, pytest and `ansible-doc` in
  separate bounded calls; a module run directly blocks on stdin.
- **New module from sibling.** When adding an f5 module and test, copy a
  recent sibling's skeleton and test imports.

The notes were never frozen or tested.

## What it means

- At this difficulty, Sonnet 5.5 rarely fails, so refine rarely has anything
  to learn from: 26 of 30 sessions changed nothing.
- A ceiling here is a property of the task pool, not of refine. A fair test
  needs tasks the model fails about half the time.
- Options for a next run, none pre-registered yet:
  - a harder SWE-bench Pro repository, chosen by a short pilot;
  - a weaker or cheaper model on the same ansible pool;
  - the whole multi-repository pool rather than one repository.

## Deviations

See `deviations.md`. The run was operated under the user's delegation, and
the gate rule was applied as pre-registered.

## Credit

SWE-bench Pro by Scale AI, MIT License,
<https://github.com/scaleapi/SWE-bench_Pro-os>, commit
`66f92766bba642462d4bbe5479e83f91f9211862`. The README at that commit gives
no citation entry.
