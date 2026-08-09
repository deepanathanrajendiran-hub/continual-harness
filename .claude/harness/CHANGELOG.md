# Harness changelog

Every edit `refine` applies, newest last. Format:

`YYYY-MM-DD | layer | target | rationale | evidence`

Layers: `rho` (CLAUDE.md), `G` (skills), `K` (subagents), `M` (memory).
`REVERTED` lines are written by `/refine --undo`.
2026-08-09 | M | /Users/deeps/.claude/projects/-Users-deeps-Documents-NEW-STUFF-fun-/memory/project-dir-has-trailing-space.md | record that the project dir name ends with a space so paths are always quoted | cd "/Users/deeps/Documents/NEW STUFF/fun" -> "(eval):cd:1: no such file or directory"; fixed by keeping the trailing space
2026-08-09 | M | /Users/deeps/.claude/projects/-Users-deeps-Documents-NEW-STUFF-fun-/memory/prefers-no-additional-api-keys.md | record the preference for existing-primitive solutions over third-party API keys | user: "is there any way we can make this as a skill so we dont need to add any api keys as such"
2026-08-09 | M | /Users/deeps/.claude/projects/-Users-deeps-Documents-NEW-STUFF-fun-/memory/verify-regression-tests-discriminate.md | record that a regression test must be observed failing against the pre-fix code | Task 1's regression test passed against pre-fix commit 6d03005, guarding nothing
