# Refine phase 3: normal rollback attempt

The documented normal undo command was run for project-scoped entry `0001` without `--force`:

```text
python3 /Users/deeps/Documents/NEW\ STUFF/fun\ /.agents/skills/refine/scripts/harness.py --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/terra-refine refine-undo --entry 0001
```

It exited with status `2` and returned `UndoConflict`. The harness identified `/private/tmp/skills-sol-terra-20260906.12qRC0/terra-refine/.codex/memory/test-discovery.md` as changed since entry `0001` was applied and refused the undo. The exact command output is in `../evidence/terra-refine-undo-attempt.txt`.

Readback confirms the target retains the later line: `User-added context for the rollback test: preserve this later edit.` The history continues to show entry `0001` as unreverted with its earlier helpful outcome. No force option was used, no target was changed by this phase, and the conflicted note remains intact.
