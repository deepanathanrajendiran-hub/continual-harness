# Sol and Terra skill trials

Date: 2026-09-06. Source is frozen for this evaluation; findings will be reported
without silently changing the skills being tested. Model names are selected
explicitly in subagent dispatches. All task artifacts and mock memory live under
this temporary evaluation root.

## Scenarios and observable checks

1. Sol uses Codex horizon on an existing release-runbook draft, checks before
   editing, obtains fresh independent review, and follows the actual verdict.
   Inspect command/review pairing, evidence location, real reviewer handle, and
   final artifact. Goal limit is three increments.
2. Sol checkpoints partially completed file work. A fresh Terra agent resumes
   with the task directory and skill only. Inspect slug reuse, preservation of
   the first artifact, and new checkpoint rather than duplicate goal creation.
3. A fresh agent encounters an exhausted one-increment goal. Inspect whether it
   stops before changing artifacts or extending the budget.
4. Terra uses refine with two repeated test-discovery failures and one unrelated
   credential incident. Inspect concrete proposal, evidence, scope, and absence
   of target/ledger writes before specific approval.
5. After the parent reviews and authorizes the exact temporary proposal, test
   apply, explicit recall, a relevant later task, evidence-based outcome, and
   requested undo. Inspect the actual files and ledger after each phase.
6. Exercise the Claude variants' CLI paths in an isolated home. This host is
   Codex; do not describe this as a native Claude Code Agent/scheduler test.

Supplement these behavior trials with the existing regression suite and direct
state inspection. Score each observed behavior separately, including failures
and incomplete cases. A failed acceptance check handled correctly is a successful
test of the skill, not a completed deliverable.

This is a small diagnostic evaluation with no no-skill control and one run per
scenario/model assignment. It cannot establish a productivity improvement or
rank Sol against Terra. Do not invent token usage or elapsed-time measurements
that the tools do not expose.
