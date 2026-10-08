# Setup trials and usage calibration

Setup task: `layout-config-recreation` (Media, 2.0 h). It replaced the drawn `interleaved-vigenere` after two Horizon-arm safety refusals; see [findings.md](findings.md). Those attempts are kept in `$RUNS/setup-discarded-1/` and `$RUNS/setup-discarded-2/`.

## Trials (scored from disk)

| Job | Valid | Reward | Timed out | Horizon end | Tokens | Wall time |
| --- | --- | --- | --- | --- | --- | --- |
| `setup__layout-config-recreation__control__a1` | yes | 0.0 | no | no goal | 6,758,875 | 3,762 s |
| `setup__layout-config-recreation__horizon__a1` | yes | 1.0 | no | complete (4 turns, 1 review) | 28,986,723 | 5,226 s |

Both rows: Claude Code `2.1.293`, model `claude-sonnet-5-5`, image IDs equal to the manifest row, no audit flags. Control: `skill_loaded: false`, `horizon_started: false`. Horizon: `skill_loaded: true`, `horizon_started: true`, budget 200 turns / 100 minutes, gate `python3 /tmp/tools/verify.py`, a written review criterion, and the goal file collected with `docker cp`.

The control agent stopped at about 93% pixel agreement and said so ("I did not reach the 98% target"), a reports-incomplete message on a failed trial.

## Checks

- `config.json` of each trial: `extra_instruction_paths` names `prompts/control.md` and `prompts/horizon.md` respectively; the agent `kwargs` are `version: 2.1.293`, `disable_web_search: true`, `reasoning_effort: high`; the token appears only as the `${CLAUDE_CODE_OAUTH_TOKEN}` template.
- Leftover compose containers for the setup task: 0.
- Files containing the token under `$RUNS/jobs`, `records`, `ledgers` and `logs`: 0 (the scan also covers `ledgers/` and `logs/`, beyond the plan's `jobs/` and `records/`).
- Fixtures in `tests/fixtures/tb4/setup-{control,horizon}/` (2.1 MB, no token); `tests/test_tb4_fixtures.py` passes 2/2 and fails when the Horizon skill file is removed.
- Real data exposed one scorer gap, fixed before the freeze: the agent piped every Horizon CLI call through its own formatter, so `horizon_reviewed` now also reads the collected goal file's `reviews`.

## Usage calibration

Five-hour window resetting at 16:00 for all points (no reset spanned):

| Point | Five-hour | Seven-day |
| --- | --- | --- |
| before control (12:26) | 0.09 | 0.35 |
| before Horizon (13:29) | 0.12 | 0.35 |
| after both (14:58) | 0.22 | 0.36 |

- `d` = max(0.03, 0.10) = 0.10; `d7` = max(0.00, 0.01) = 0.01. These include any other use of the subscription in the same window, so they err high.
- `d_star` = min(0.9, 1.5 × 0.10) = 0.15; `d7_star` = 1.5 × 0.01 = 0.015.
- `Pace(first=0.65, second=0.8, weekly=0.9, weekly_step=0.05)`: a pair's first arm starts only below 65% five-hour and 80% seven-day utilization, and its second arm below 80% five-hour.
