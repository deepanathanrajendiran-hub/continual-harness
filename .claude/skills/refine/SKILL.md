---
name: refine
description: Use when asked to learn from a completed task or refine the agent's working instructions. Proposes a small evidence-based memory, skill, subagent, or instruction change, applies authorized edits, and tracks later outcomes.
---

# Refine for Claude Code

Improve the next task using actual evidence. A long session alone does not justify
another instruction. Resolve `HARNESS` to the absolute `scripts/harness.py`
beside this loaded SKILL.md and `PROJECT` to the working project. Quote both.

```bash
python3 "$HARNESS" --runtime claude --project "$PROJECT" doctor
python3 "$HARNESS" --runtime claude --project "$PROJECT" refine-count
python3 "$HARNESS" --runtime claude --project "$PROJECT" refine-history
python3 "$HARNESS" --runtime claude --project "$PROJECT" recall --query "observed issue"
```

Invoke as `/refine`. Default to project scope. Add
`--scope global` **before the subcommand** only for an explicitly desired
cross-project change; it has a separate ledger and cap.

## Select and propose

Read the trajectory, failed command or review, and current target. Quote the
evidence. Check existing notes for duplicates and contradictions. Choose the
narrowest useful layer from `doctor`'s target paths:

- `M`: project memory for a reusable fact or lesson.
- `G`: a skill for a repeatable procedure.
- `K`: a subagent definition for a recurring specialist responsibility.
- `rho`: CLAUDE.md for a broad, repeatedly demonstrated constraint.

Claude skills use `.claude/skills`; subagents use `.claude/agents/*.md`.
Use the CLI's existing Claude project-memory route under `~/.claude/projects`;
do not guess the encoded directory name.
For memory, add a focused note and one link in `MEMORY.md`. Keep the index brief.
Memory stays project-specific even with a global ledger.

If no reusable improvement is supported, say so and stop. Otherwise present the
exact target, smallest diff, quoted evidence, expected benefit, scope, and a later
task that could test the lesson. Avoid universal prohibitions from one incident.

## Apply and undo

Read [the proposal schema](references/commands.md#refinement-proposals) when
preparing an edit. Build the JSON proposal in a temporary file outside the project.
Apply when this specific change is authorized; prior explicit approval counts.
An ordinary refine invocation authorizes analysis and a proposal.

```bash
python3 "$HARNESS" --runtime claude --project "$PROJECT" refine-apply "$PROPOSAL_FILE" --approved
```

The ledger saves undo snapshots and permits three applies per rolling 24 hours
per scope and runtime. `--override-cap` requires explicit authorization.
Inspect the result and report the entry ID.

The refinement API protects horizon/refine, shared harness code, runtime config,
hooks, and bookkeeping from self-directed edits. Do not bypass it with another
writer. A direct user request to maintain this implementation is ordinary
authorized development, outside this self-refinement workflow.

For a requested rollback, use `refine-undo --entry "$ENTRY_ID"` in the same scope.
Undo refuses to overwrite later changes. Inspect conflicts first;
`--force --approved` requires authorization to discard those changes.

## Observe later outcomes

On a relevant later task, retrieve the note and inspect actual behavior:

```bash
python3 "$HARNESS" --runtime claude --project "$PROJECT" refine-outcome "$ENTRY_ID" \
  --outcome helpful --task "$LATER_TASK_REFERENCE" --evidence-file "$OBSERVATION_FILE"
```

Choose `helpful`, `ineffective`, or `harmful` from observed evidence.
If no later task exercised the lesson, leave it unassessed. Harmful lessons warrant
a proposed correction or undo. An observation is an audit record, not a causal
benchmark; an applied edit alone does not demonstrate benefit.
