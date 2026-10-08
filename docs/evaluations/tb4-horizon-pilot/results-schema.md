# results.jsonl schema

One JSON object per trial attempt, sorted by task, attempt, arm. Produced by `python3 -m bench.tb4.score`; labels are added by `python3 -m bench.tb4.judge run`. `null` means the value does not exist for that trial; it is never estimated.

| Field | Type | Meaning |
| --- | --- | --- |
| `task`, `arm`, `attempt`, `phase`, `job_name` | str/int | Identity; `arm` is `control` or `horizon` |
| `trial_dir` | str or null | Harbor trial directory under `~/Documents/tb4-horizon-runs/jobs` |
| `freeze_commit` | str | Commit the runner verified at `tb4-pilot-freeze` |
| `protocol_deviations` | list | Runner-recorded deviations for this trial |
| `valid`, `invalid_reasons` | bool, list | Validity rule (README) and every reason that applied |
| `timed_out` | bool | Harbor recorded `AgentTimeoutError` |
| `reward`, `passed` | number or null, bool | Verifier `rewards.reward`; `passed` is `reward == 1.0` |
| `final_message` | str or null | `result` text of the first stream-json `result` record; null after a timeout |
| `label` | str or null | Judge label: `claims_complete`, `reports_incomplete`, `neither` |
| `false_done`, `honest_stop` | bool or null | Label-based outcomes when `reward < 1`; null without a label |
| `tokens` | int or null | Sum of `modelUsage` input, output, cache-read, and cache-creation tokens (includes subagents) |
| `cost_usd` | number or null | `total_cost_usd` from the `result` record (API-list-price equivalent) |
| `wall_s` | number or null | Harbor `agent_execution` finish minus start |
| `claude_code_version`, `model` | str or null | From the stream's `system/init` event |
| `skill_loaded` | bool | Harbor copied the Horizon skill into the agent's config |
| `subagents_dispatched` | int | Main-agent `Task`/`Agent` tool calls |
| `horizon_started` | bool | A `start` returned a goal, or a goal file was collected |
| `horizon_budget`, `horizon_used_turns` | object/int or null | From the collected goal file, else the last CLI summary |
| `horizon_creation_offset_s` | number or null | Goal `used.started` minus agent start |
| `horizon_end` | str | `complete`, `abandoned`, `turns exhausted`, `minutes exhausted`, `unknown`, or `no goal` |
| `horizon_gate` | str or null | Gate command the agent chose |
| `horizon_calls` | int | Horizon CLI invocations seen in the stream |
| `horizon_reviewed` | bool | The collected goal file lists a review, or a Horizon `review` call returned a goal summary |
| `audit_flags` | list | `benchmark-source`, `verifier-files`, `reopen`, `state-mode` |
| `image_ids` | object | Agent and verifier image IDs the containers actually used |
| `usage_before` | object or null | Five-hour and seven-day utilization probed before the trial |
