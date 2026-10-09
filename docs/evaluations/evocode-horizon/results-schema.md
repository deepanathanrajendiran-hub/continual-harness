# EvoCode-Bench first look: results schema

Run data stays in `~/Documents/evocode-horizon-runs` (`RUNS`). The repository holds only `prereg.json`, `prereg.md`, `report.md`, `deviations.md` and this file. `null` means a value does not exist for that run or round; it is never estimated. Final messages, transcripts, verifier output and per-case results are never committed.

## Run record: `RUNS/records/<job_name>.json`

One per Harbor job attempt of the `dry` and `main` phases, written by `python3 -m bench.evo.run`. The job name is `{phase}__{task}__{arm}__a{attempt}`. Task 7's checks write `RUNS/checks/<job_name>/findings.json` instead.

| Field | Type | Meaning |
| --- | --- | --- |
| `job_name` | str | The job name above |
| `phase` | str | `dry` or `main` |
| `task`, `arm`, `attempt` | str, str, int | Identity; `arm` is `control` or `horizon` |
| `started`, `finished` | number or null | Epoch seconds just before and just after `harbor run`; `null` for a job an earlier runner left unfinished |
| `exit_code` | int or null | Exit status of `harbor run` |
| `job_dir` | str | The Harbor job directory, `RUNS/jobs/<job_name>` |
| `trial_dir` | str or null | The job's trial directory |
| `valid` | bool | The job counts toward the analysis |
| `invalid_reason` | str or null | `null`, `usage_limit`, `api_error`, `infrastructure`, `host_slept` or `interrupted` |
| `image_id` | str or null | ID of the validated task image the job was checked against |
| `container_image` | str or null | Image of the kept main container; one other than `image_id` makes the job `infrastructure` |
| `freeze` | str | The `evo-prereg` commit for `main`; `pre-freeze` for `dry` |
| `harbor_version`, `claude_code_version` | str or null | Versions the job ran with, from Harbor's lock file and trial result |
| `command` | list | The `harbor run` argv; the token appears only as `${CLAUDE_CODE_OAUTH_TOKEN}` |
| `usage_before`, `usage_after` | object or null | Rate-limit info (`status`, `five_hour`, `five_hour_resets_at`, `seven_day`, `seven_day_resets_at`, `limit_type`, `limit_utilization`, `limit_resets_at`): from the usage probe before the job, and from the latest round stream that has one |
| `ledger` | object or null | `{candidates, copied}`: the ledger paths the streams named, and where each one copied from the stopped main container landed under `RUNS/ledgers/<job_name>` |

## Round row: `RUNS/rows.jsonl`

One JSON object per round of every valid job, in task order, written by `python3 -m bench.evo.score --phase dry` or `--phase main`. A round the trial never reached keeps the defaults: `reward` 0.0, `passed` false, `end_reason` `not reached`. `label` is filled by `python3 -m bench.evo.analysis label`.

| Field | Type | Meaning |
| --- | --- | --- |
| `job_name`, `phase`, `task`, `arm`, `attempt` | str, str, str, str, int | Identity, as in the run record |
| `round`, `round_index` | str, int | Step name and its position, from 1 |
| `reward` | number | The step's verifier reward (`reward.txt` or `reward.json`); 0.0 when it has none, was not reached, or Harbor recorded an exception for the round |
| `passed` | bool | `reward >= 1.0`; a missing, aborted or timed-out round is `false` |
| `cases_passed`, `cases_total` | int or null | The two counts on the verifier's CASE_SUMMARY line, nothing else |
| `agent_sec` | number or null | Agent phase duration of the round |
| `tokens_in`, `tokens_out` | int or null | Input tokens (cache reads and writes included) and output tokens from the round's last result record; `null` without one or after a timeout |
| `cost_usd` | number or null | `total_cost_usd` from that record |
| `result_records` | int | Result records in the round's stream; more than 1 is flagged |
| `horizon_calls` | int | Horizon CLI invocations in the round |
| `horizon_started` | bool | The round created a Horizon goal, or a Horizon `start` in it returned one |
| `goal_slugs`, `goal_status` | list, object | Goals the round created or changed, and each one's status at the round's end |
| `end_reason` | str | `complete`, `abandoned`, `active`, `no goal`, `unknown` or `not reached` |
| `final_message` | str or null | The round's last result message, `null` after a timeout; read by the judge, never committed |
| `label` | str or null | Judge label: `claims_complete`, `reports_incomplete` or `neither` |
| `audit_flags` | list | `verifier-files` when a tool input named `/tests`, `/solution` or `/logs/verifier`; `benchmark-source` when one named EvoCodeBench or UniPat-AI |
| `leftovers` | object or null | Counts from the collect hook's audit: `killed` processes, `survivors` still running and `tmp_entries` left in `/tmp` (the last two `null` when their file is missing); `null` when no audit was collected |

## Validation record: `RUNS/validation/<task>.json`

One per validated task, written by `python3 -m bench.evo.validate`. A saved record whose `code` differs from the current code is validated again.

| Field | Type | Meaning |
| --- | --- | --- |
| `task` | str | Task directory name |
| `copy_digest`, `validation_copy_digest` | str or null | Tree digests of the agent copy and the validation copy |
| `arm_patch` | object | `{changed, artifacts}` from the copy's `arm-patch.json`: the Dockerfile lines the arm64 patch rewrote, and the bundled Go archives it swapped for go.dev's arm64 ones; absent when the copy failed |
| `image_tag` | str | The local image tag, `evo-local/<task>:<first 12 characters of the dataset revision>` |
| `image_id`, `arch` | str or null | The built image's ID and architecture (`arm64` to pass) |
| `workdir` | str or null | Where Harbor runs the agent, the hooks and the oracle: `[environment].workdir`, else the image WORKDIR |
| `user` | list or null | The sorted distinct users each step's `setup.sh` and agent run as: `[steps.agent].user`, else `[agent].user`, else the image USER; `""`, `"0"`, `root` and a user:group whose user part is one of those (for example `0:0`) are shown as `root`; `null` until the image is inspected |
| `python` | object or null | `{ok, version}`: whether the image has python3 >= 3.10, which the Horizon CLI needs |
| `rounds` | int | Number of steps in `task.toml` |
| `oracle`, `nop`, `planted` | list | Per-round rewards (number or null) of the oracle, nop and planted-ledger oracle runs |
| `oracle_cases` | list | `[passed, total]` from the CASE_SUMMARY line, or null, per oracle round |
| `ok`, `reason` | bool, str or null | `ok` only when every oracle and planted reward is 1, round 1's nop reward is graded and below 1, every other graded nop reward is below 1 (a step's min_reward may stop the nop chain early), `arch` is `arm64` and the image ID did not change during the checks; `reason` names what failed |
| `code` | str | `validate.CODE_DIGEST`: sha256 of `copies.py`, `images.py`, `patch.py`, `steps.py` and `validate.py`, the code that made the copies and judged them |

## Pre-registration: `prereg.json`

Written by `python3 -m bench.evo.prereg write`, committed and tagged `evo-prereg`. Top-level keys:

| Key | Meaning |
| --- | --- |
| `study`, `spec`, `freeze_tag` | Title, the design spec's path and sha256, and the tag name |
| `n`, `n_rule` | N, and the rule's inputs: the choices, the planned rounds per task, the budget, the dry run's minutes per round per arm, its rounds and its task |
| `tasks`, `replaced` | The measured tasks in order; the tasks before them passed over for failing validation, with the reason |
| `reserve` | The pre-registered replacements: the tasks after the Nth measured one whose validation passes the same checks, in order. A main task dropped for an infrastructure failure is replaced by the next unused one; with none left a drop stays a drop |
| `task_details` | For each measured and reserve task: its position in the order, rounds, minutes, agent and verifier timeouts, arm order, image tag, image ID and agent copy digest |
| `arms`, `arm_orders`, `draw` | Arm names, each measured task's seeded arm order, and the seeded draw (seed, domains, pool, excluded prefix, walkthrough, algorithm, order) |
| `prompts` | Each prompt text a measured or reserve task uses, keyed by arm and minutes (for example `horizon@30`), with the sha256 of the text and of the file `copies.write_prompt` writes |
| `bundle` | The Horizon bundle commit, modules and per-file sha256 |
| `versions`, `observed` | Configured settings, and the versions found on the host at the freeze |
| `dataset`, `evocode_code` | The pinned dataset revision, archive and `PIN.json`; the EvoCode code reference |
| `judge` | Judge model and the TB4 rubric's path and sha256 |
| `analysis`, `outcomes` | The pre-registered test and the primary, secondary, validity and running rules |
| `pilot` | The latest attempt of each Harbor behaviour check: job name, attempt, verdict, failures, findings digest, and the probe's recorded facts |
| `code` | sha256 of every tracked file under `bench/evo` and `bench/tb4` at the freeze |
