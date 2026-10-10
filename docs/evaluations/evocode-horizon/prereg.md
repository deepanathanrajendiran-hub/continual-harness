# EvoCode-Bench first look: pre-registration

Frozen at Git tag `evo-prereg`. Design: [spec](../../superpowers/specs/2026-10-09-evocode-horizon-design.md) (sha256 `0aae7135f722e60c4ef501bc43ec0a8397febf36e650d874af0c4ebfcdf56f75`). Every value here is also in [prereg.json](prereg.json). After the tag, every change goes to `deviations.md` with its date, its reason and the runs it affects.

## Question

On EvoCode-Bench's multi-round coding tasks, does Claude Code with Horizon v2 pass more rounds than plain Claude Code?

## Tasks (N = 10)

The pool is 13 tasks; the walkthrough pair `theme_d11_w2_*` is excluded. Seed 20261009 orders the pool by a round-robin over the domains d1, d5, d8, d9, d10, d11, d12. The measured tasks are the first N in that order that passed validation (arm64 build; oracle and planted-ledger oracle reward 1 on every round; nop reward below 1 on round 1 and on every later round it reached, since a step's min_reward may stop the nop chain early).

| # | Task | Rounds | Minutes | Arm order | Image ID | Agent copy digest |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `theme_d1_w5_code_build_integration_e2e_wiring` | 8 | 30 | control then horizon | `sha256:aea4d7cc55590cd943144101e5bac528f6ce42b6a5766d847f67a509a1df06a7` | `526ece7594baf5744848e4c7222b8b2958f0c02193723dbc8de822ca8403f405` |
| 2 | `theme_d5_w1_data_engineering_greenfield_implementation` | 13 | 30 | horizon then control | `sha256:4f96b633ee707bf4ead68c48b58d4f8131bbb19780c9980b0a4d6e1ece610fec` | `e68962d25467e96427cae39c827052bcd944848429299c5c4df1e34e157464ae` |
| 3 | `theme_d8_w5_cloud_devops_integration_e2e_wiring` | 11 | 30 | horizon then control | `sha256:4c8076ef0364736e9c2b9c0b30ec261aa4eb942d47997a0922e069cba8102f75` | `c5356798b58a0fb573dd89e1c84e4d1df897bd480f375c2863775f2046bf6155` |
| 4 | `theme_d9_w11_security_automation_scripting` | 15 | 30 | control then horizon | `sha256:aee00ab72d8a399eac4f47cda46c5717cf48f09879238fe9da29ed8a53a716d9` | `440d67993510961de1ab3a35e7538b5ddc237aeb1d5e5abb78b1307faae0aaea` |
| 5 | `theme_d10_w4_ml_ai_mlops_migration_upgrade__not_1234` | 13 | 30 | horizon then control | `sha256:c5a582043d08070899857225642fef1b348e0ab5fd4382f5c7e402087a2c613e` | `366c81f06490bb66d11957df1503525db4f3f7e7f731dfe1900756210da48852` |
| 6 | `theme_d11_w9_scientific_numerical_reproducibility_verification` | 8 | 60 | control then horizon | `sha256:e630e301b9ad2102184c06c9e8d4591aa72e5be9ac302568387453231a91a098` | `5265d6e6749918386c089c84af86d55d24312c24cce4190d4b3e15165f0dd119` |
| 7 | `theme_d12_w1_automation_productivity_greenfield_implementation` | 7 | 30 | control then horizon | `sha256:3fba493d99f501daa1ccded74fb451309c60dd8f2a12691598cd3ad345fe2804` | `12021b3320cbce760c9569557546d50131f380b7abc5e23ac146fd4d6eb895e5` |
| 8 | `theme_d1_w11_code_build_automation_scripting` | 8 | 30 | horizon then control | `sha256:4235fa70739d825ca87879ff0499010b55c612adfb8c20a117fdefc97993f2c5` | `ca9e29475084fbfe6cf1fe6eb680370edf762e14b338ec7ae0bbf1301670c097` |
| 10 | `theme_d10_w9_ml_ai_mlops_reproducibility_verification` | 8 | 30 | horizon then control | `sha256:7182aa7ad8e4dd01f2baf58acca1a686528f7dd90f1c1b7a7d24c8551eb66a31` | `5278ad82f334a85a1cf7f200b5172b6c17e57120119218dbae8c08246d205727` |
| 11 | `theme_d1_w2_code_build_brownfield_modification` | 8 | 30 | control then horizon | `sha256:c72474176349a8970c56a9527ca97381ca83b492ce58348a596515c9ec9eb0dc` | `2c33ec9c396a1662f53d3bf6b4f55332a63cc302a60b9ff85ef34cf13034722c` |

Passed over because they failed validation:

- `theme_d5_w9_data_engineering_reproducibility_verification`: oracle rewards [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], expected 1.0 on all 15 rounds; planted rewards [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], expected 1.0 on all 15 rounds

### Reserve

Pre-registered replacements, used as the Running section says: the tasks after the Nth measured task in the order whose validation passes the same checks.

No reserve: validation stopped at the Nth passing task, or no later task passed it.

## Decisions made before the freeze

- Task copies add python3 to the image for both arms when the image lacks it, so the Horizon CLI can run (user decision, 2026-10-09; tasks theme_d10_w4 and theme_d1_w11 had no python3).
- The ARM patcher leaves the x86_64/amd64 arms of an architecture case statement in a RUN instruction unchanged when the same statement also has an aarch64/arm64 arm, and patches the rest of the statement as usual (user decision, 2026-10-09; task theme_d12_w1).
- theme_d5_w9 was swapped out at validation: its oracle passes only round 1, and the same happens without the round hooks, so the failure is the task's, not the runner's (diagnosed 2026-10-09).
- The runner keeps TB4's usage pacing rates (0.098 five-hour and 0.0127 seven-day utilization per agent-hour), although the timing dry run measured about 0.15 to 0.19 five-hour utilization per agent-hour while other work shared the account; a job that hits a usage limit is invalid and is rerun, never scored (user decision, 2026-10-10).

## N rule

The timing dry run on `theme_d11_w2_scientific_numerical_brownfield_modification__not_1234` gave m_control = 1.57 and m_horizon = 4.95 agent minutes per round. N is the largest of [10, 8, 6] with N x 10 x (m_control + m_horizon) / 60 <= 60.0 agent-hours: N = 10.

## Arms and prompts

Both arms: anthropic/claude-sonnet-5-5 at effort high, Claude Code 2.1.293, Harbor 0.24.0, a fresh session every round, the same patched images and task copies. Control appends the shared paragraph to every round; Horizon also installs the Horizon v2 bundle and appends the Horizon sentence. M is 30, or 60 for 3,600-s tasks.

**control@30** (text sha256 `7ef4d007d8997e94d1f0d0620d9befd6ef7fda8f0f8f12ecee3ccb7a7451cbdd`, file sha256 `edf1437d7c900a0f11c41ac41f62223ed2510ad04e6df7e02a37c397f3f32c52`)

> You have 30 minutes for this request. Keep working until it is fully complete; do not stop early. Before finishing, verify your work against the request with your own tests or checks. If you cannot finish within 30 minutes, stop and state exactly what is complete and what is incomplete.

**control@60** (text sha256 `2d0ea9045233ed1b38b09cdba9cd41dc6db6fdc1d2984b2e0d23ebb221caf345`, file sha256 `4ffa449db1264c3376f56ff6b5d56a967de1b7f9eb251817e834018b9ba0f435`)

> You have 60 minutes for this request. Keep working until it is fully complete; do not stop early. Before finishing, verify your work against the request with your own tests or checks. If you cannot finish within 60 minutes, stop and state exactly what is complete and what is incomplete.

**horizon@30** (text sha256 `e366279510d844a77bddd200871d51522ca05a6fde67507730ee986437aa4c7a`, file sha256 `b84cb761eeb788267570921dd0fce3c4bbe43f526164c6c52c97231d58c4e6ce`)

> You have 30 minutes for this request. Keep working until it is fully complete; do not stop early. Before finishing, verify your work against the request with your own tests or checks. If you cannot finish within 30 minutes, stop and state exactly what is complete and what is incomplete.
>
> Use the horizon skill for this request with `--max-turns 200`, and give the goal the minutes that remain of your 30 when you create it.

**horizon@60** (text sha256 `eec5abd1e63704e7723e0c11dada310f14a1f4c818e6ebcabf09bc392ef90647`, file sha256 `90c52c0046ed12804b1b70fc8b31e019b00c414ce57ee93cc426298adad47e2a`)

> You have 60 minutes for this request. Keep working until it is fully complete; do not stop early. Before finishing, verify your work against the request with your own tests or checks. If you cannot finish within 60 minutes, stop and state exactly what is complete and what is incomplete.
>
> Use the horizon skill for this request with `--max-turns 200`, and give the goal the minutes that remain of your 60 when you create it.

## Analysis

Per-task fraction of rounds passed: a round passes when its verifier reward is at least 1.0, and a missing, aborted or timed-out round counts as failed. Each task's difference is d = horizon - control. Reported: the mean d with a 95% interval from inverting the exact sign-flip test over shifts in steps of 0.01 within [-1, 1], the two-sided permutation p over all 2^N sign assignments, and the tasks won, lost and tied.

Test: exact sign-flip permutation, two-sided, alpha 0.05.

## Running

One attempt per arm per task; a task's two arms run back to back in its seeded arm order. An invalid run (usage limit, API error, infrastructure failure, host sleep or interruption) is rerun once; a second invalid run drops the task, logged in deviations.md. After the freeze a task is replaced only for an infrastructure failure, never because of its results: a main task dropped for an infrastructure failure is replaced by the next unused reserve in order; with no reserve left a drop stays a drop.

## Secondary outcomes

- Case score: the mean per-round share of hidden test cases passed, from the pass/total counts on the verifier's CASE_SUMMARY line; rounds without counts are excluded and counted.
- False done rate: the share of failed rounds whose final message the TB4 blind judge labels claims_complete.
- Under-claim rate: the share of passed rounds whose final message the judge labels reports_incomplete.
- Cost: median and mean agent minutes per round; tokens and the cost Claude Code reports, which exist only for rounds with a final result, so they cover those rounds and their count is shown beside them; and subscription usage consumed. Rounds that timed out, and rounds ended by another Harbor exception, are reported per arm.
- Horizon start rate in Horizon rounds, Horizon calls in control rounds, and extra result records.

## Validity checks

- Horizon was started in at least 90% of Horizon rounds.
- Control never invoked Horizon.
- Each round has exactly one result record; any extra record is flagged.
- No agent read /tests or /logs/verifier.
- The leftover-file audit shows what survives a round.

## Settings and versions

| Setting | Value |
| --- | --- |
| agent_setup_timeout_multiplier | `2.0` |
| agent_timeout_multiplier | `1.0` |
| claude_code | `2.1.293` |
| disable_web_search | `True` |
| effort | `high` |
| five_hour_ceiling | `0.9` |
| harbor | `0.24.0` |
| judge_model | `claude-opus-5-5` |
| max_output_tokens | `128000` |
| model | `anthropic/claude-sonnet-5-5` |
| probe_model | `claude-sonnet-5-5` |
| resume_trajectory | `False` |
| weekly_ceiling | `0.9` |

| Observed on the host | Value |
| --- | --- |
| claude (host) | `2.1.293 (Claude Code)` |
| docker arch | `aarch64` |
| docker server | `29.1.3` |
| harbor | `0.24.0` |
| python (host) | `3.14.4` |

## Horizon bundle

Commit `f73975ad6db67b8d9ac0d822ed569a807e9eae59`, modules filelock, gate, goal, paths, refine_log, steps, task_state, tree_hash, reviewing.

| File | SHA-256 |
| --- | --- |
| `horizon/SKILL.md` | `c94b6ad34216d43da0e1fcec3776d6a017b3c44a9b9a132d0e1811238d69d2da` |
| `horizon/references/commands.md` | `93fd1e9bb4e968c87ad676b8f966e9f2e744181f04164c532dd07b3b0b11eed0` |
| `horizon/scripts/filelock.py` | `7b134fd00d93c81c3d6e4093a42095f86786189f5ce29d3e9c30a377f1b208e6` |
| `horizon/scripts/gate.py` | `9ac4961c2ddb733dc2e192c527608084a400bcd35187fad34fc10a41476b6ffc` |
| `horizon/scripts/goal.py` | `e540b6082e7ff8da3ab19678f321862468c54682bbf0ecc64ac2f38b027ed6e3` |
| `horizon/scripts/harness.py` | `e74f3f73a5bb32523185ccbe9ab49530557668ae06a8c7d3e611b4c1881b26a6` |
| `horizon/scripts/paths.py` | `5020e8820e977a811dfaa7d79e3cbca0aa7a0136262b9ff8aa7f050b2dd2d79a` |
| `horizon/scripts/refine_log.py` | `09ac9fad92f517c28690c2f6692ddecdf2952715edb9871951083d8e1984f1aa` |
| `horizon/scripts/reviewing.py` | `c01ffafe5171907897734b42b2ced81e77146f8d9aacc6c69d0274f5b2538e90` |
| `horizon/scripts/steps.py` | `e1bf7b5e517efe0d6aba722789c9c39b875a3243646ec0691be5bb1fdb2df761` |
| `horizon/scripts/task_state.py` | `1ade30d217978a8ac1abe1677ffc7d83ca73d42000d65c3cf61f303dcadac9ad` |
| `horizon/scripts/tree_hash.py` | `8c2c92b585ca15f51b670ce639a3f265c6a3834eceab5442496baa16fda0198d` |

## Dataset

`UnipatAI/EvoCodeBench` at revision `9fcae3e5539d1c0e85e2481fe06bd6af42cc4bc6`, archive `archives/evocodebench_wotraj.tar.zst`, sha256 `a13d0cb47574282372c59366217ac68d895ff49d1387c81098b058f739906184` (equal to its LFS oid). EvoCode code reference: https://github.com/UniPat-AI/EvoCodeBench at `f8fcfaa1c9ad1c5b0bbc433323b587e4ddea2f32`.

## Judge

`claude-opus-5-5` with the TB4 rubric `docs/evaluations/tb4-horizon-pilot/prompts/judge.md` (sha256 `f11fde652e21dc09c827c1561cad6e0b9a0be7cf421eecbba00a49543b319f07`), blind to task and arm.

## Pilot checks

The latest attempt of each Harbor behaviour check (Task 7), with the digest of its findings.json.

| Job | Result | Failures | findings.json sha256 |
| --- | --- | --- | --- |
| `canary__dummy__horizon__a1` | passed | 0 | `8b2dfae2929a8f73494f3222b20ad826bf5335d0a305e93fe363f61b8f3d2502` |
| `check__dummy-probe__control__a1` | recorded only | 0 | `df98aacc4bf2b49ce0e6f3f50356fad986a3e9a89eb2b07af8f7623eeebadaed` |
| `check__dummy-vtimeout__oracle__a1` | passed | 0 | `3cd823ab1c6c52b0d4525a7de92b6ce47ec41d8f818d694a55f6af51f02bd6c3` |
| `check__dummy__control__a1` | passed | 0 | `12f2d6cfc60b48c886ae98a8b6fc0554d482ae7318ad6cd04ee753b81d6cfd3a` |
| `check__dummy__oracle__a1` | passed | 0 | `b1df76f7004a6aac7cce847150fe319e58474a22313fb5481a4181876387ec42` |

Recorded by `check__dummy-probe__control__a1`:

```json
{
  "claude_like_in_round_2": [
    "claude --verbose --output-format=stream-json --effort high --disallowedTools WebSearch,WebFetch --permission-mode=bypassPermissions --print"
  ],
  "round_1_exception": {
    "message": "Agent execution timed out after 60.0 seconds",
    "type": "AgentTimeoutError"
  },
  "round_1_ledger_collected": true,
  "round_1_reward": 0.0,
  "round_1_verifier_ran": true,
  "round_2_reward": 1.0,
  "round_2_started": true,
  "running_before_collect": [
    "claude --verbose --output-format=stream-json --effort high --disallowedTools WebSearch,WebFetch --permission-mode=bypassPermissions --print",
    "claude 86399",
    "/bin/bash -c source /logs/agent/sessions/shell-snapshots/snapshot-bash-1791589519898-audos1.sh 2>/dev/null || true && shopt -u extglob 2>/dev/null || true && { \\builtin unalias -- 'unsetenv'; \\builtin unset -f -- 'unsetenv'; } >/dev/null 2>&1 || true && eval 'sleep 600' < /dev/null && pwd -P >| /tmp/claude-dd60-cwd",
    "sleep 600"
  ],
  "still_running_in_round_2": []
}
```

## Code

41 tracked files under `bench/evo` and `bench/tb4`; their sha256 digests are in prereg.json. `python3 -m bench.evo.prereg check` refuses main-phase runs once they change.
