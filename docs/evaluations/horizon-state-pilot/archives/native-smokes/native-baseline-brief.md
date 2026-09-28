# Native Codex baseline task

Use Horizon state mode to fix the parser in this disposable project. Use exactly two work increments: first investigate the empty-input bug and save the findings without changing parser source, then fix the parser. Preserve the supplied acceptance tests. Require independent review before marking the goal complete. Use Sol at high reasoning for the Codex run. Read the supplied project Horizon skill and its linked reference. Follow the runtime's native worker tools; report any missing capability rather than silently substituting a different mode.

## Environment

- Project: `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/native-baseline-project`
- Horizon skill: `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.agents/skills/horizon/SKILL.md`
- Harness entrypoint: `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.agents/skills/horizon/scripts/harness.py`
- Evidence directory: `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/native-baseline-evidence`
- Reserved disposable home directory: `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/native-baseline-home`
- Acceptance: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`, run in the project.

The parser must reject empty input while preserving valid integers and zero. The acceptance test file is evaluator-owned. Use the supplied skill to carry out the task. This is a bounded native behavioral test; the root evaluator remains separate from your coordinator and any native workers/reviewer you dispatch. You may use native subagents to perform this task. Their model setting is `gpt-5.6-sol`, reasoning `high`.

Standing workspace rules apply to you and every editing worker: discover the AST editor and call `list_symbols` before structural Python/config edits; use the AST editor for those edits. Preserve evaluator-owned tests. Restrict edits to the disposable project and designated evidence directory. Do not modify the harness or skill. Do not install tools, change global configuration, or start authentication flows.

Keep your observed command/tool outputs and native handles/status observations in the evidence directory. Save actual output when available; distinguish your written account from a complete tool transcript if export is unavailable. Report the goal location, actual outcome, worker/reviewer handles, completed increments, any repair requests or unavailable capabilities, and remaining gaps in `report.md` there. Return a concise result to the evaluator. Do not read other implementation plans, review reports, or evaluation arms.
