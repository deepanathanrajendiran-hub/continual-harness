# EvoCode-Bench first look: Horizon v2 against plain Claude Code

This is a first look, not a definitive comparison: 10 tasks were analysed (N = 10 pre-registered; 0 dropped tasks were replaced by reserves), with one attempt per arm. Every task's result is shown.

Setup: anthropic/claude-sonnet-5-5 at effort high, Claude Code 2.1.293, Harbor 0.24.0, a fresh session every round. Both arms get the same time-budget paragraph; the Horizon arm also gets the Horizon v2 skill and one sentence asking it to use the skill.

## Primary result

Outcome: the share of a task's rounds passed (reward 1). A missing, aborted or timed-out round counts as failed. Analysis: exact sign-flip permutation, two-sided, alpha 0.05, on d = Horizon - control per task.

- Tasks analysed: 10
- Mean d: +0.02
- 95% interval (test inversion over shifts in steps of 0.01): [-0.05, +0.09]
- Two-sided permutation p: 0.5625
- Horizon won / lost / tied: 3 / 2 / 5

## Per-task results

| Task | Rounds | Control | Horizon | d | Status |
| --- | --- | --- | --- | --- | --- |
| theme_d1_w5_code_build_integration_e2e_wiring | 8 | 8/8 (1.00) | 8/8 (1.00) | +0.00 | valid |
| theme_d5_w1_data_engineering_greenfield_implementation | 13 | 11/13 (0.85) | 11/13 (0.85) | +0.00 | valid |
| theme_d8_w5_cloud_devops_integration_e2e_wiring | 11 | 2/11 (0.18) | 4/11 (0.36) | +0.18 | valid |
| theme_d9_w11_security_automation_scripting | 15 | 15/15 (1.00) | 14/15 (0.93) | -0.07 | valid |
| theme_d10_w4_ml_ai_mlops_migration_upgrade__not_1234 | 13 | 12/13 (0.92) | 10/13 (0.77) | -0.15 | valid |
| theme_d11_w9_scientific_numerical_reproducibility_verification | 8 | 7/8 (0.88) | 8/8 (1.00) | +0.12 | valid |
| theme_d12_w1_automation_productivity_greenfield_implementation | 7 | 5/7 (0.71) | 6/7 (0.86) | +0.14 | valid |
| theme_d1_w11_code_build_automation_scripting | 8 | 6/8 (0.75) | 6/8 (0.75) | +0.00 | valid |
| theme_d10_w9_ml_ai_mlops_reproducibility_verification | 8 | 3/8 (0.38) | 3/8 (0.38) | +0.00 | valid |
| theme_d1_w2_code_build_brownfield_modification | 8 | 8/8 (1.00) | 8/8 (1.00) | +0.00 | valid |

## Secondary outcomes (analysed tasks)

| Outcome | Control | Horizon |
| --- | --- | --- |
| Rounds (reached) | 99 (99) | 99 (99) |
| Rounds passed | 77 | 78 |
| Rounds timed out | 0 | 0 |
| Rounds ended by another Harbor exception | 0 | 0 |
| Case score (mean per-round share of cases passed) | 0.98 | 0.99 |
| Rounds with case counts / without | 99 / 0 | 99 / 0 |
| False "done" rate (failed rounds labeled claims_complete) | 0.82 (18/22) | 0.76 (16/21) |
| Under-claim rate (passed rounds labeled reports_incomplete) | 0.18 (14/77) | 0.32 (25/78) |
| Agent minutes per round: median (mean) | 1.0 (1.7) | 4.3 (5.9) |
| Tokens per round (mean, input + output) | 537,743 (99 of 99 rounds with a final result) | 1,958,837 (99 of 99 rounds with a final result) |
| Total tokens | 53,236,583 (99 of 99 rounds with a final result) | 193,924,870 (99 of 99 rounds with a final result) |
| Cost reported by Claude Code (USD) | 38.33 (99 of 99 rounds with a final result) | 114.71 (99 of 99 rounds with a final result) |
| Horizon start rate (rounds reached) | 0.00 (0/99) | 1.00 (99/99) |
| Horizon CLI calls | 0 | 676 |
| Rounds with more than one result record | 0 | 1 |
| Reached rounds with no result record | 0 | 0 |
| Seven-day usage consumed (jobs summed; jobs across a reset) | 0.050 (10; 0) | 0.110 (10; 0) |

## Validity

- Main runs: control 10 valid, 0 invalid; horizon 10 valid, 0 invalid
- Invalid reasons: none
- Reruns: none
- Dropped tasks: none
- Horizon started in at least 90% of reached Horizon rounds: 1.00 (99/99), met
- Control never invoked Horizon: met
- No round has more than one result record: not met: theme_d10_w4_ml_ai_mlops_migration_upgrade__not_1234 horizon round 13
- No agent read /tests or /logs/verifier: not met: theme_d10_w9_ml_ai_mlops_reproducibility_verification control round 6: verifier-files; theme_d9_w11_security_automation_scripting horizon round 10: verifier-files
- Leftover audit (rounds audited 198 of 198 reached): a claude process killed after 0, other processes still running after 198, files left in /tmp after 198. The listings stay in the run directory.
- Freeze: 3fa39519c38fd288d7a89d9f9a4ccb226d5657df
- Final-message labels: the TB4 blind judge (claude-opus-5-5) sees only the message text; rubric docs/evaluations/tb4-horizon-pilot/prompts/judge.md.

## Deviations

- 2026-10-10: Step 14: informal interim look at 12 of 20 main runs at the user's request (rounds passed per task and arm, read-only, nothing written to rows.jsonl); the run continued unchanged.
- 2026-10-10: Step 14: second informal interim look at 14 of 20 main runs at the user's request (rounds passed per task and arm, read-only, nothing written to rows.jsonl); the run continued unchanged.

## Limits

- Low power: 10 tasks, one attempt per arm. With 8 tasks and a paired SD near 0.30, the smallest reliably detectable difference is about 0.33 of a task's rounds.
- One model (Sonnet) through Claude Code only.
- The task images were patched from linux-amd64 to linux-arm64 and validated with oracle and no-op runs on every round. Scores are not comparable with the public leaderboard.
- No forced mid-round interruption, no ledger-wiped ablation arm and no continuous-session control.
- The TB4 tasks informed the Horizon v2 design. EvoCode material was seen during design; the walkthrough pair (theme_d11_w2_*) is excluded for that reason.
- The judge reads only the final message, but Horizon messages can reveal the arm.
- One operator ran the study.
- The between-round setup hook empties /tmp and ~/.claude/projects, not the rest of ~/.claude, which holds the Horizon ledger and skills when the working directory is $HOME. The design said the hook empties ~/.claude.

## Credit and license

EvoCode-Bench by UniPat-AI (https://github.com/UniPat-AI/EvoCodeBench at f8fcfaa); tasks from the Hugging Face dataset UnipatAI/EvoCodeBench at revision 9fcae3e, licensed CC-BY-NC-4.0. This report is non-commercial. It reproduces no hidden tests, per-case results, reference solutions, round instructions or transcripts.
