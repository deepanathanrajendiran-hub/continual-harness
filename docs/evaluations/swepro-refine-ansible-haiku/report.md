# SWE-bench Pro refine study, Haiku on ansible: stopped at the gate

**Result: no test phase.** Claude Code with Haiku 5.5 passed all 30 ansible
practice tasks, above the pre-registered ceiling of 26. The study stopped
before the notes were frozen or any test task was run. Nothing here says
whether refine helps or hurts.

## What ran

- **Pool and split.** The same 80 validated ansible tasks and the same seeded
  30 practice / 50 test split as the Sonnet run (`split.json`).
- **Pilot.** 7 of 8 (0.875), just over 26/30, so Amendment 2's rule said
  stop. The user chose to run practice anyway and let the 30-task gate
  decide.
- **Practice.** Claude Code with `claude-haiku-5-5` solved each practice task
  in order. After each one, a refine session was told only "passed" or
  "failed: K of N graded tests failed" and could apply at most one edit to
  memory, skills, agents or `CLAUDE.md`.

## Gate

| | |
|---|---|
| Practice passes, in-sandbox | 30 of 30 |
| Practice passes, pristine re-grade | 30 of 30 |
| Pre-registered rule | stop if ≥ 26 or ≤ 4 |
| Decision | `stop_high` |
| Refine edits applied | 9, all memory (M) |
| Refine sessions with no change | 21 of 30 |
| Mean cost per agent run | $0.05 |
| Mean cost per refine session | $0.01 |
| Mean tokens per agent run | 985k |
| Seven-day usage spent on practice | about 1% |
| Projected seven-day usage of the test phase | about 8% |

## What refine learned

With no failures, refine still wrote nine memory notes, all from friction
inside passing runs:

- import the repo's ansible with `PYTHONPATH=/app/lib`, never `python3 -I`;
- scratch-run gotchas: no `ANSIBLE_CONFIG=/dev/null`, keep pytest's
  `--reruns`, diff behaviour against `git archive HEAD`;
- a new `basic.py` import also needs its path in the recursive-finder test
  list;
- one config unit test aborts broad runs, so compare the pass count with the
  collected total;
- some display and executor tests fail on HEAD in combined runs, so diff
  failure lists against HEAD;
- module unit-test traps (the `patch_ansible_module` parametrize, and
  patching `get_best_parsable_locale` when mocking `run_command`);
- a new facts key needs `os.sched_getaffinity` mocked in the expected table;
- filters on templated vault values need the lazy-marker flags;
- `store_true` rejects `const=`.

The notes were never frozen or tested.

## What it means

- Haiku is no weaker than Sonnet on this pool: 30/30 against 29/30.
- Refine does produce notes without failures, but with every task passing
  there is no headroom for them to show a gain.
- The ceiling held on openlibrary too, including with a minimal agent; see
  `../swepro-refine-openlibrary-mini/report.md`.

## Deviations

See `deviations.md`. Practice ran past a pilot stop on the user's explicit
choice; the 30-task gate was applied as pre-registered.

## Credit

SWE-bench Pro by Scale AI, MIT License,
<https://github.com/scaleapi/SWE-bench_Pro-os>, commit
`66f92766bba642462d4bbe5479e83f91f9211862`.
