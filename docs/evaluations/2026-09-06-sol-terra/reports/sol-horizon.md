# Sol Horizon trial report

## Outcome

The real Horizon helper at `/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py` was used with runtime `codex`. The release-runbook goal completed after 2 of 3 allowed increments. The resume goal was handed off active after exactly 1 increment, with `foundation.txt` present, `delivery.txt` absent, and an exact next action recorded. No native goal or automation was created.

## Goal 1: release runbook

- Goal slug: `produce-a-brief-actionable-web-app-release-runbook-with-prer`
- Project: `/tmp/skills-sol-terra-20260906.12qRC0/sol-horizon`
- Final artifact: `/tmp/skills-sol-terra-20260906.12qRC0/sol-horizon/runbook.md`
- Watched input: `runbook.md`
- Budget: 3 increments, 60 minutes
- Final status: `complete`
- Increments used: 2

The initial artifact was not edited before increment 1. The command gate failed with exit 1 and reported:

```text
{'missing': ['prerequisites', 'backup', 'production verification', 'failure handling', 'rollback triggers', 'rollback actions'], 'ordered_steps': 3}
```

Fresh initial reviewer `/root/sol_horizon_trial/runbook_review_initial` was spawned with model `gpt-5.6-terra`, reasoning effort `high`, and `fork_turns='none'`. It independently returned:

```text
FAIL — includes an owner placeholder and three ordered steps, but omits prerequisites, backup placeholder, explicit production verification/failure handling, rollback triggers, and rollback actions.
```

The helper refused to record that review because the command gate had failed. The exact attempt exited 2 with:

```json
{"error": "GateNotPassed", "message": "The command gate must pass before review"}
```

After repair, increment 2 passed with exit 0:

```text
{'missing': [], 'ordered_steps': 9}
```

Fresh final reviewer `/root/sol_horizon_trial/runbook_review_final` was spawned with model `gpt-5.6-sol`, reasoning effort `high`, and `fork_turns='none'`. It independently returned:

```text
PASS — Includes owner/backup placeholders, four prerequisites, five ordered deployment steps, production checks with failure handling, three explicit rollback triggers, and four ordered rollback actions. No omissions against the acceptance criterion.
```

The passing review was recorded against checkpoint hash `9a450e9c698416f6b8bd4ac7db1f233b1e7a641996843cf2e6a6ec9d458f76ae`; `complete` then exited 0.

### Exact Horizon commands

```sh
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/sol-horizon doctor
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/sol-horizon recall --query 'release runbook deployment verification rollback'
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/sol-horizon status
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/sol-horizon start 'Produce a brief actionable web-app release runbook with prerequisites, ordered deployment steps, production verification with explicit failure handling, rollback triggers and actions, and owner/backup placeholders.' --gate 'python3 -c '\''from pathlib import Path; import re; s=Path("runbook.md").read_text(); checks={"prerequisites":r"(?im)^##?\s*Prerequisites\b","owner":r"(?im)^Owner:\s*\[[^\]]+\]","backup":r"(?im)^Backup:\s*\[[^\]]+\]","production verification":r"(?i)production.{0,120}(verify|verification)|(?:verify|verification).{0,120}production","failure handling":r"(?i)(if|when).{0,80}(fail|unhealthy|error)","rollback triggers":r"(?im)^##?\s*Rollback triggers\b","rollback actions":r"(?im)^##?\s*Rollback actions\b"}; missing=[k for k,p in checks.items() if not re.search(p,s,re.S if k=="production verification" else 0)]; steps=len(re.findall(r"(?m)^\d+\.\s+",s)); print({"missing":missing,"ordered_steps":steps}); raise SystemExit(0 if not missing and steps>=4 else 1)'\''' --review 'Review runbook.md for a brief, actionable web-app release procedure that includes prerequisites, ordered deployment steps, production verification with explicit failure handling, rollback triggers and rollback actions, plus owner and backup placeholders. Return pass or fail with concrete evidence and omissions.' --watch runbook.md --max-turns 3 --max-minutes 60
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/sol-horizon status produce-a-brief-actionable-web-app-release-runbook-with-prer
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/sol-horizon check produce-a-brief-actionable-web-app-release-runbook-with-prer --did 'Assessed the supplied runbook in its original unchanged state and ran the configured acceptance gate.' --next 'Request fresh independent review of the unchanged checkpoint, record its actual verdict, then repair only the confirmed gaps.'
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/sol-horizon review produce-a-brief-actionable-web-app-release-runbook-with-prer --result fail --judge /root/sol_horizon_trial/runbook_review_initial --hash dd030d010d5fbdc19713b80769848c25713b54147c7cf97816af361940c22be6 --evidence-file /tmp/skills-sol-terra-20260906.12qRC0/evidence/sol-horizon-initial-review.txt
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/sol-horizon status produce-a-brief-actionable-web-app-release-runbook-with-prer
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/sol-horizon check produce-a-brief-actionable-web-app-release-runbook-with-prer --did 'Repaired runbook.md to add owner and backup placeholders, prerequisites, ordered staged deployment, production verification with explicit failure handling, rollback triggers, and rollback actions.' --next 'Request fresh independent review of this passing checkpoint and record the actual verdict; complete only if the review passes.'
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/sol-horizon review produce-a-brief-actionable-web-app-release-runbook-with-prer --result pass --judge /root/sol_horizon_trial/runbook_review_final --hash 9a450e9c698416f6b8bd4ac7db1f233b1e7a641996843cf2e6a6ec9d458f76ae --evidence-file /tmp/skills-sol-terra-20260906.12qRC0/evidence/sol-horizon-final-review.txt
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/sol-horizon complete produce-a-brief-actionable-web-app-release-runbook-with-prer
```

All commands above succeeded with exit 0 except the deliberately failing initial `check` (exit 1) and the refused initial `review` recording attempt (exit 2). No Horizon command was skipped. One file-edit patch attempt also failed before changing anything because it tried to delete and add the same path in one patch; the subsequent update patch succeeded.

## Goal 2: deliberate session-boundary handoff

- Goal slug: `create-foundation-txt-and-delivery-txt-each-containing-exact`
- Project: `/tmp/skills-sol-terra-20260906.12qRC0/resume-project`
- First-half artifact: `/tmp/skills-sol-terra-20260906.12qRC0/resume-project/foundation.txt`
- Deferred artifact: `/tmp/skills-sol-terra-20260906.12qRC0/resume-project/delivery.txt`
- Watched inputs: `foundation.txt`, `delivery.txt`
- Budget: 3 increments, 60 minutes
- Handoff status: `active`
- Increments used at handoff: 1
- Handoff checkpoint hash: `512c617892bca47d2558d7b406b183c98c874a1343e6e4853001213079f4561c`
- Exact recorded next action: `Create delivery.txt containing exactly ready on one line, then run the configured check once and complete only if the gate passes.`

At handoff, `foundation.txt` contained exactly `ready\n`; `delivery.txt` did not exist. The required two-file gate failed as expected with exit 1 and `{'mismatches': {'delivery.txt': None}}`. This worker did not create `delivery.txt`, complete, abandon, reopen, or extend the goal. The raw handoff snapshot is preserved separately because a fresh-context evaluator may modify the shared goal after receipt of the slug.

### Exact Horizon commands

```sh
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/resume-project doctor
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/resume-project recall --query 'foundation delivery ready'
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/resume-project status
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/resume-project start 'Create foundation.txt and delivery.txt, each containing exactly ready on one line.' --gate 'python3 -c '\''from pathlib import Path; expected={"foundation.txt":"ready\n","delivery.txt":"ready\n"}; bad={name:(Path(name).read_text() if Path(name).exists() else None) for name in expected if not Path(name).exists() or Path(name).read_text()!=expected[name]}; print({"mismatches":bad}); raise SystemExit(0 if not bad else 1)'\''' --watch foundation.txt --watch delivery.txt --max-turns 3 --max-minutes 60
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/resume-project status create-foundation-txt-and-delivery-txt-each-containing-exact
python3 '/Users/deeps/Documents/NEW STUFF/fun /.agents/skills/horizon/scripts/harness.py' --runtime codex --project /tmp/skills-sol-terra-20260906.12qRC0/resume-project check create-foundation-txt-and-delivery-txt-each-containing-exact --did 'Created foundation.txt containing exactly ready on one line; intentionally left delivery.txt absent for the session-boundary resume test.' --next 'Create delivery.txt containing exactly ready on one line, then run the configured check once and complete only if the gate passes.'
```

The two setup/status commands and `start` succeeded with exit 0. The single `check` exited 1 as expected because `delivery.txt` was intentionally absent. No command was skipped.

## Evidence and limitations

- Raw final release-goal status: `/tmp/skills-sol-terra-20260906.12qRC0/evidence/sol-horizon-final-status.raw.json`
- Raw release goal ledger with both checkpoints: `/tmp/skills-sol-terra-20260906.12qRC0/evidence/sol-horizon-goal-ledger.raw.json`
- Raw handoff status at exactly one increment: `/tmp/skills-sol-terra-20260906.12qRC0/evidence/resume-project-final-status.raw.json`
- Latest copied resume ledger: `/tmp/skills-sol-terra-20260906.12qRC0/evidence/resume-project-goal-ledger-latest.raw.json`
- Initial actual review: `/tmp/skills-sol-terra-20260906.12qRC0/evidence/sol-horizon-initial-review.txt`
- Final actual review: `/tmp/skills-sol-terra-20260906.12qRC0/evidence/sol-horizon-final-review.txt`
- Refused initial review command output: `/tmp/skills-sol-terra-20260906.12qRC0/evidence/sol-horizon-initial-review-command.json`
- Check/result extracts: `/tmp/skills-sol-terra-20260906.12qRC0/evidence/sol-horizon-check-1.json`, `/tmp/skills-sol-terra-20260906.12qRC0/evidence/sol-horizon-check-2.json`, `/tmp/skills-sol-terra-20260906.12qRC0/evidence/sol-horizon-final-review-command.json`, `/tmp/skills-sol-terra-20260906.12qRC0/evidence/sol-horizon-complete.json`, and `/tmp/skills-sol-terra-20260906.12qRC0/evidence/resume-project-check-1.json`

There are no unresolved issues for the completed release-runbook goal. The initial FAIL review is preserved as external evidence but is absent from the Horizon ledger because the helper enforces `GateNotPassed`. The command gate checks structural signals and ordered-list count; the independent review supplies the semantic/actionability judgment. Reviewer independence is operational (fresh agent handles) rather than cryptographically proven. The resume goal's active one-increment snapshot was intentionally unresolved for the separate session-boundary evaluator, and shared-state changes after handoff do not alter that preserved snapshot. The parent later verified that a fresh Terra continuation reused the same slug, preserved `foundation.txt` content and mtime, created `delivery.txt`, and completed at turn 2 of 3; it also left a separate exhausted task untouched.
