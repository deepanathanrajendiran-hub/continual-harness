# Sol and Terra skill evaluation

Date: 2026-09-06. Tested the current horizon/refine skills with explicitly selected
`gpt-5.6-sol` and `gpt-5.6-terra` subagents. The workers used the actual skill
files and CLI in disposable projects, with source files held fixed. The parent
checked saved files, goal state, fingerprints, and undo records independently.

Three worker agents and two reviewers were used, all with high reasoning effort.
The initial runbook reviewer used Terra and the final reviewer used Sol; both
reviewers were spawned with fresh contexts.

## Results

| Trial | Model | Observed result |
| --- | --- | --- |
| Horizon: review and repair a release runbook | Sol, with fresh reviewers | Completed in 2/3 increments; initial command and review failed, repaired artifact passed both checks |
| Horizon: resume another agent's unfinished work | Sol starts, fresh Terra resumes | Same goal completed at 2/3 increments; existing file's bytes, hash, and modification time unchanged |
| Horizon: exhausted budget with urgent handoff | Terra | Stopped at 1/1; did not create the artifact, extend the budget, or report completion |
| Refine: proposal before authorization | Terra | Chose project memory from repeated evidence; no target or ledger entry written before approval |
| Refine: apply, recall, and later task | Terra | Applied one entry, recalled it from tools/, ran the root-level test successfully, and recorded supporting evidence |
| Refine: undo after a later edit | Terra | Normal undo returned UndoConflict and preserved the addition; explicitly authorized forced undo restored both targets to absence and retained the ledger/outcome |
| Claude variants: CLI and routing | Sol | Horizon completed in 1/2 increments; refine inspected the successful task and correctly made no proposal |

These are diagnostic cases, not independent repeated samples suitable for a
success-rate estimate.

## Findings

### 1. Refinement proposal had incorrect newline encoding

Terra's original JSON proposal decoded to one physical line containing three
literal backslash-n sequences. The CLI applied that exact content, so the Markdown
note was malformed. Terra identified the issue on readback, reported it, and
preserved the approved content instead of silently making another change.

The evaluator noticed the encoding error before the temporary apply and approved
the exact disposable proposal to test downstream detection. The original JSON and
actual target bytes were retained. Explicit recall still returned the intended
instruction, and the later task passed, but that does not erase the formatting
defect. The observation's serialized newline formatting also deserves preview.

Suggested improvement: show the decoded target content or rendered Markdown as
part of proposal review before applying. Validate intended multiline formatting
without banning literal backslashes in legitimate code/documentation. No skill or
implementation fix was made during this evaluation.

Evidence: [original proposal](evidence/terra-refine-proposal-original.json),
[target contents](evidence/terra-refine-memory-targets.txt),
[Terra's report](reports/terra-refine-phase2.md).

### 2. Failed reviews cannot be recorded while the command gate fails

The first independent runbook review returned FAIL. Sol tried to record that real
review, and the CLI returned `GateNotPassed: The command gate must pass before review`.
The review was preserved in an external evidence file. After the command passed,
the final independent PASS was recorded normally and completion succeeded.

This is the current ordered-check contract. It limits the goal ledger's record of
an exploratory review, and our trial explicitly requested review before editing
the incomplete draft. Completion checks remained effective. If early review is a
supported workflow, consider storing its observation independently of whether it
can satisfy a completion requirement; otherwise make that sequencing clearer in
the short skill instructions.

Evidence: [initial review](evidence/sol-horizon-initial-review.txt),
[refused recording](evidence/sol-horizon-initial-review-command.json),
[Sol's report](reports/sol-horizon.md).

## Evidence and verification

- Regression suite: **306 passed in 22.03 seconds**, using the existing cached
  pytest environment. No implementation changes were made before rerunning it.
- Before/after SHA-256 checks matched for all **four SKILL.md files and seven
  shared Python modules**. [Source fingerprints](source-fingerprints.md).
- Parent inspection confirmed command/review/checkpoint hash agreement for the
  completed runbook, one goal per project, unchanged foundation content and mtime,
  exhausted budget left untouched, both undone memory targets absent, and the
  reverted entry still containing its outcome.
- Approval and rollback phases were controlled by the evaluator inside temporary
  fixtures. This tests the agent's handling of supplied authorization, not a
  separate human-approval UI.
- The later test was deliberately small: pytest from tools/ returned exit 5 with
  no tests; from the root it collected and passed one test checking fixture
  visibility. The helpful label records observed use, not causal proof of benefit.

[Scenario design](reports/evaluation-design.md),
[resume/budget report](reports/terra-resume.md),
[proposal-only report](reports/terra-refine-phase1.md),
[conflicted undo](reports/terra-refine-phase3.md),
[approved undo](reports/terra-refine-phase4.md),
[Claude portability](reports/sol-claude-portability.md).

## Limits and conclusion

The behavior trials support using horizon for checkpointed continuation and refine
for reviewed, reversible lessons. Horizon preserved work and stopped honestly at
its budget. Refine respected authorization stages and rollback conflicts, with a
concrete proposal-formatting defect worth correcting.

This was one small assignment per model/scenario, without a no-skill control,
randomized repetitions, or measured model-token usage. It does not establish that
Sol outperforms Terra or that the skills improve productivity. The interruption
was a deliberate checkpoint handoff to a fresh context, not a mid-write process
kill. Claude portability was exercised from Codex; native Claude Agent behavior,
automatic memory loading, scheduling, and long-term learning were not tested.
