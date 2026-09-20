# Claude instruction portability trial

## Result

The Claude variants were read from:

- `/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/horizon/SKILL.md`
- `/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/refine/SKILL.md`

Their adjacent CLI entrypoints worked from Codex when invoked with `--runtime claude`. The temporary project is `/tmp/skills-sol-terra-20260906.12qRC0/claude-portability`; state was routed to its `.claude/harness` directory.

Horizon slug `create-ready-txt-containing-exactly-ready-followed-by-one-ne` completed in 1 of 2 allowed increments. `/tmp/skills-sol-terra-20260906.12qRC0/claude-portability/ready.txt` contains exactly `ready\n`. The command-only gate passed with exit 0, required no independent review, and `complete` exited 0. No Horizon command failed or was skipped.

### Exact Horizon commands

```sh
python3 '/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/horizon/scripts/harness.py' --runtime claude --project /tmp/skills-sol-terra-20260906.12qRC0/claude-portability doctor
python3 '/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/horizon/scripts/harness.py' --runtime claude --project /tmp/skills-sol-terra-20260906.12qRC0/claude-portability recall --query 'ready mechanical portability'
python3 '/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/horizon/scripts/harness.py' --runtime claude --project /tmp/skills-sol-terra-20260906.12qRC0/claude-portability status
python3 '/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/horizon/scripts/harness.py' --runtime claude --project /tmp/skills-sol-terra-20260906.12qRC0/claude-portability start 'Create ready.txt containing exactly ready followed by one newline.' --gate 'python3 -c '\''from pathlib import Path; p=Path("ready.txt"); raise SystemExit(0 if p.is_file() and p.read_bytes()==b"ready\n" else 1)'\''' --watch ready.txt --max-turns 2 --max-minutes 30
python3 '/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/horizon/scripts/harness.py' --runtime claude --project /tmp/skills-sol-terra-20260906.12qRC0/claude-portability status create-ready-txt-containing-exactly-ready-followed-by-one-ne
python3 '/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/horizon/scripts/harness.py' --runtime claude --project /tmp/skills-sol-terra-20260906.12qRC0/claude-portability check create-ready-txt-containing-exactly-ready-followed-by-one-ne --did 'Created ready.txt containing exactly ready followed by one newline.' --next 'Complete the goal because the configured command gate passes on the current watched artifact.'
python3 '/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/horizon/scripts/harness.py' --runtime claude --project /tmp/skills-sol-terra-20260906.12qRC0/claude-portability complete create-ready-txt-containing-exactly-ready-followed-by-one-ne
```

## Refine inspection

The successful task was explicitly reviewed for a justified reusable lesson. `refine-count` reported project scope, 0 uses of a 3-apply rolling cap; `refine-history` returned no entries; recall returned an empty index and no notes. The task passed on its first checkpoint and exposed no failure, correction, recurring friction, or durable project fact. No reusable improvement is supported, so no proposal was created and `refine-apply` was not called.

### Exact Refine commands

```sh
python3 '/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/refine/scripts/harness.py' --runtime claude --project /tmp/skills-sol-terra-20260906.12qRC0/claude-portability doctor
python3 '/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/refine/scripts/harness.py' --runtime claude --project /tmp/skills-sol-terra-20260906.12qRC0/claude-portability refine-count
python3 '/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/refine/scripts/harness.py' --runtime claude --project /tmp/skills-sol-terra-20260906.12qRC0/claude-portability refine-history
python3 '/Users/deeps/Documents/NEW STUFF/fun /.claude/skills/refine/scripts/harness.py' --runtime claude --project /tmp/skills-sol-terra-20260906.12qRC0/claude-portability recall --query 'ready file newline horizon cli portability'
```

All four inspection commands exited 0. The resolved memory target was `/Users/deeps/.claude/projects/-private-tmp-skills-sol-terra-20260906.12qRC0-claude-portability/memory`; a read-only existence check after inspection returned `False`. No Claude home-memory target, `CLAUDE.md`, skill, subagent, global setting, native goal, or schedule was created.

## Evidence and limitation

Raw outputs are preserved under `/tmp/skills-sol-terra-20260906.12qRC0/evidence/` as:

- `claude-horizon-doctor.raw.json`, `claude-horizon-recall.raw.json`, `claude-horizon-status-initial.raw.json`
- `claude-horizon-start.raw.json`, `claude-horizon-status-before-work.raw.json`, `claude-horizon-check.raw.json`, `claude-horizon-complete.raw.json`
- `claude-refine-doctor.raw.json`, `claude-refine-count.raw.json`, `claude-refine-history.raw.json`, `claude-refine-recall.raw.json`
- `claude-memory-target-check.raw.txt`, `claude-refine-assessment.txt`, `claude-portability-verification.raw.txt`

This was executed by Codex. It validates the Claude instruction files' CLI entrypoints, `--runtime claude` state routing, mechanical goal lifecycle, and read-only refine inspection. It is not a native Claude Code Agent-tool or Claude session test, and it does not validate Claude's fresh `Agent` review route because this command-only goal did not require review.
