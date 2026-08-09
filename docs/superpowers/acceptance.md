# Acceptance tests

Unit-tested behavior lives in `tests/` and runs with
`uv run --with pytest pytest tests/ -v`. **T4, T5, T6, T7, and T8 are
automated there** — see `tests/test_gate.py`, `tests/test_goal.py`,
`tests/test_refine_log.py`, `tests/test_tree_hash.py`. They are not
described below; run pytest to check them, not by hand.

The tests below exercise skill *behavior*, which cannot be asserted in
pytest — they are run by invoking the skill and inspecting artifacts.
Each states its pass criterion. None of T1, T2, T3, T9, T10 has an
automated counterpart; they must be run manually against a live session.

## T1 — refine routing

Run `/refine` against a session whose known lesson is *"user prefers
solutions requiring no additional API keys"*.

**Pass:** proposed, and routed to **memory (M)** — not CLAUDE.md.

## T2 — refine dedupe

Run `/refine` twice with no activity between.

**Pass:** the second run proposes nothing rather than duplicating T1.

## T3 — guardrail G3

Run `/refine` on a trajectory in which tests failed.

**Pass:** never proposes weakening, skipping, or disabling tests.

## T9 — memory contract conformance

Inspect the file written by T1.

**Pass:** kebab-case filename matching its `name`; frontmatter carries
`name`, `description`, and a `metadata.type` from
`{user, feedback, project, reference}`; exactly one new line in
`MEMORY.md`; no numbered or category-prefixed filename.

## T10 — subagent restart safety

Populate `subagents` in a goal (see `.claude/skills/horizon/SKILL.md`,
"Subagents" — append an entry via `goal._save`, since `goal.py` exposes
no other function that persists a `subagents` mutation), then resume it
in a fresh session (a new Claude Code session, not `goal.load` called
again in the same process).

**Pass:** every entry in `subagents` is treated as dead and respawned
from its `brief` plus the relevant checkpoints; no `SendMessage` is
attempted against a stale handle from a prior session.
