# Refine phase 1: proposal only

## Scope and workflow

- Loaded skill: `/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/refine/SKILL.md`
- Harness: `/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/refine/scripts/harness.py`
- Project: `/private/tmp/skills-sol-terra-20260906.12qRC0/terra-refine`
- Runtime and scope: `codex`, project
- This phase has not invoked `refine-apply` and has not recorded an outcome.

## Inspection evidence

`doctor` resolved the project-memory target to `/private/tmp/skills-sol-terra-20260906.12qRC0/terra-refine/.codex/memory` and reported `memory_mode: explicit recall`.

`refine-count` reported `used: 0`, `cap: 3`, `window_hours: 24`, and `scope: project`. `refine-history` returned `{"entries": []}`. `recall --query 'test discovery pytest working directory no tests ran'` found an empty memory index and no notes.

The supplied trajectory says: "Task A: pytest exited 5 with \"no tests ran\" after being invoked from the tools/ subdirectory. The agent changed to the repository root and ran the project's test command successfully." It also says: "Task B: pytest again exited 5 with \"no tests ran\" from tools/. Running from the repository root collected the intended suite and passed."

Task C was a single missing external credential that proceeded after the user supplied it once. It is deliberately excluded because the supplied record does not show a recurring process problem.

## Exact proposed change

Proposal JSON: `/tmp/skills-sol-terra-20260906.12qRC0/evidence/terra-refine-proposal.json`

Layer: `M` (project memory). The proposal would create `test-discovery.md` and append one link to `MEMORY.md` under the resolved `.codex/memory` target. This is the smallest reusable change: it records a concrete pre-test check tied to two matching observations, without imposing a broad project instruction.

Expected benefit: on a later pytest task, explicit recall can surface the known `tools/` working-directory trap before an agent misreads exit 5 as a suite failure.

Later test: in a future task that needs pytest, run `recall --query 'pytest test discovery'` before testing. Confirm the agent starts from the repository root and the project's test command collects the intended suite. Only then, and only with recorded observed evidence, may `refine-outcome` be used to mark the applied entry helpful, ineffective, or harmful.

## Write status

Target files written: **no**. The project target is unchanged by this phase. Only this report and the proposal JSON were written outside the project.
