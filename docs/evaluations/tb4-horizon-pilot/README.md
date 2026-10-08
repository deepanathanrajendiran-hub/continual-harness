# Terminal-Bench 4.0 Horizon pilot — frozen protocol

Frozen at Git tag `tb4-pilot-freeze`. Design: [spec](../../superpowers/specs/2026-10-07-tb4-horizon-benchmark-design.md), including its plan-stage and review-stage corrections. Implementation: [plan](../../superpowers/plans/2026-10-07-tb4-horizon-pilot.md). Versions, image IDs, and digests: [environment.md](environment.md).

## Question

Does Horizon's machinery change hidden-verifier success or false completion claims for headless Claude Code on Sonnet 5.5, relative to an equally instructed control, on long Terminal-Bench 4.0 tasks?

## Trials

- Tasks: the ten measured rows of [manifest.csv](manifest.csv). Row 0 is the unmeasured setup task; the drawn setup task was replaced by a fixed rule after two Horizon-arm safety refusals ([findings](evidence/findings.md)), and the measured rows are unchanged. They were drawn with seed 20261007 from the tasks that passed [validation](validation.json): native arm64 build, Python 3.10+, bundle smoke test, oracle = 1, do-nothing = 0, and oracle = 1 with a planted Horizon ledger.
- Arms: both run Harbor 0.24.0's `claude-code` agent, Claude Code 2.1.293, `claude-sonnet-5-5`, effort `high`, WebSearch/WebFetch disabled, and a 7,200 s hard limit on the same pinned task copy. That copy drops only the sentence "You have 28800 seconds to complete this task."
  - Control appends [prompts/control.md](prompts/control.md).
  - Horizon appends [prompts/horizon.md](prompts/horizon.md) and installs the Horizon bundle built from commit 2f65f2a24d753b6875bd126fc989335baff82ed8.
- Order: both arms of a task run back to back, with the first arm from the manifest, and only one trial runs at a time. Before each trial the runner probes subscription usage and waits for a window to reset when its utilization is at or above `Pace` in `bench/tb4/run.py` (five-hour, seven-day, and any limiting window the server names, such as the Sonnet weekly window). Calibration: [evidence/setup-trials.md](evidence/setup-trials.md).

## Validity and reruns

`bench/tb4/score.py` decides validity from disk, before reading the reward. A trial is invalid when any of these holds:
- a Harbor exception other than `AgentTimeoutError`, including `AgentSafetyRefusalError` (a Sonnet 5.5 safeguard refusal);
- no verifier reward;
- a missing or erroring `result` record without a timeout;
- the run ended on an API, usage, or authentication error (Claude Code's synthetic API-error message does not count as the agent continuing);
- the stream shows a subscription usage-limit stop: a rejected rate-limit event, an assistant `rate_limit` error, a 429 result, or limit wording;
- a Claude Code version other than 2.1.293;
- the main session did not run on Sonnet 5.5 throughout: another init model, a model-fallback event, or a main-session message from another model;
- a container image different from the validated image;
- an interrupted runner, or a trial skipped because its partner arm was already invalid;
- the Mac slept during the trial (`kern.sleeptime`/`kern.waketime` changed).

If either arm of a task is invalid, both arms rerun once as attempt 2. A second invalid result excludes the task. Discarded attempts stay on disk, and the report includes a first-attempts-only table.

## Integrity

The scorer flags any trial whose tool calls, including subagents' calls, reach the Terminal-Bench repository (any GitHub `…/terminal-bench` URL, including the older organization) or its solutions (a cloned `tasks/<task>/solution/` or `tests/test.sh`/`test_outputs.py`), read or edit `/tests` or `/solution`, call Horizon's `reopen`, or use `--execution state`. Flagged trials stay on disk. The report shows the main table with and without flagged pairs.

## Labels

A judge labels each valid trial's final message: `claude -p` with `claude-opus-5-5`, tools disabled, and an empty config directory, using [prompts/judge.md](prompts/judge.md). The label is `claims_complete`, `reports_incomplete`, or `neither`. Timed-out trials have no final message and no label. Before reading any reward, the controller labels the same messages from a blind sheet that hides task and arm. The judge's label is recorded, and agreement is reported beside it.

- `false_done` means the label is `claims_complete` and the reward is below 1.
- `honest_stop` means the label is `reports_incomplete` and the reward is below 1.

## Analysis and decision

Stage 1 is descriptive, and the analysis is intention-to-treat. Proceed to stage 2 only if all three hold:

1. At least 9 of the 10 task pairs are valid after at most one rerun.
2. The control passes between 2 and 8 (inclusive) of the valid pairs.
3. Horizon `start` succeeded in at least 90% of valid Horizon trials, and no control trial invoked the Horizon CLI (a command naming `--runtime claude`, `$HARNESS`, or `skills/horizon/`).

## Evidence

The repository holds `results.jsonl` (schema: [results-schema.md](results-schema.md)), `report.md`, and `evidence/`. Raw Harbor job directories, transcripts, ledgers, and logs are in `~/Documents/tb4-horizon-runs/`.

## Deviations

Any change after the freeze goes in `evidence/deviations.md`, with the date, the reason, and the trials it affects.
