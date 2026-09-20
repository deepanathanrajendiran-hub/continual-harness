# Refine phase 2: approved apply and observed later task

## Applied scope

The original proposal was used unchanged: `/tmp/skills-sol-terra-20260906.12qRC0/evidence/terra-refine-proposal.json`.

The approved `refine-apply` created project-scoped entry `0001` at `2026-09-06T23:03:18.520137+00:00`, layer `M`, with exactly these targets:

- `/private/tmp/skills-sol-terra-20260906.12qRC0/terra-refine/.codex/memory/test-discovery.md`
- `/private/tmp/skills-sol-terra-20260906.12qRC0/terra-refine/.codex/memory/MEMORY.md`

No other lesson, source, or global target was changed. The apply result is saved in `../evidence/terra-refine-apply-result.json`; the exact target contents are in `../evidence/terra-refine-memory-targets.txt`.

## Later task and evidence

The later task began with its working directory at `/private/tmp/skills-sol-terra-20260906.12qRC0/terra-refine/tools`. Explicit recall for `pytest test discovery` returned the newly applied note, including its instruction to begin at the repository root. That raw recall output is in `../evidence/terra-refine-recall-from-tools.txt`.

The suite was then run from the repository root with the requested environment and pytest options. It passed: `1 passed in 0.00s`; raw command output is in `../evidence/terra-refine-pytest-root.txt`. The only test asserts `Path('trajectory.md').is_file()`, so it verifies that the test process is started from a directory where the project fixture is visible. The raw test source is in `../evidence/terra-refine-test-source.txt`.

This constitutes a directly relevant observed use, so entry `0001` was recorded as `helpful` using the evidence file `../evidence/terra-refine-outcome-observation.md`. The outcome result and current history are saved in `../evidence/terra-refine-outcome-result.json` and `../evidence/terra-refine-history-after-outcome.json`.

## Issues observed

The apply, recall, test, and outcome commands completed without an error. Readback did reveal one content-encoding defect in the approved proposal: the `text` content encoded newline markers as `\\n`, so the harness wrote literal backslash-n characters into `test-discovery.md` rather than physical Markdown line breaks. The actual bytes are captured in `../evidence/terra-refine-memory-targets.txt`; the original proposal remains unchanged, and the target was not corrected because no authorization covered an additional edit.

Despite the formatting defect, explicit recall returned the root-directory instruction and the later test task passed. The lesson remains applied. Project memory required the documented explicit `recall` command; it was not assumed to load automatically.
