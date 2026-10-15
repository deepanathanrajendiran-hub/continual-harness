# SWE-bench Pro refine study, plan B: stopped at the pilot

**Result: no practice, no test phase.** A minimal open-source agent
(mini-swe-agent 2.4.6) running DeepSeek V4 Flash, capped at 100 steps, solved
all 8 openlibrary pilot tasks. That is above the pre-registered ceiling
(Amendment 3: continue only if the pilot rate lies strictly between 4/30 and
26/30). Nothing here says whether refine helps or hurts.

## What ran

- **Pool.** The openlibrary tasks in SWE-bench Pro v2
  (`scaleapi/SWE-bench_Pro-os` at `66f92766`), minus the excluded tasks.
- **Pilot.** The same 8 fixed openlibrary pilot tasks used by the earlier
  pilots, one attempt each, no notes file.
- **Agent.** mini-swe-agent 2.4.6, model `deepseek/deepseek-v4-flash` via
  LiteLLM, default system prompt, `step_limit` 100, installed offline from a
  pinned bundle (`tools/manifest.json`). Network open only to
  `api.deepseek.com`; the probe confirmed GitHub, PyPI, Google and
  `api.anthropic.com` blocked.

## Pilot results

| Configuration | Pilot passes |
|---|---|
| Claude Code + Haiku 5.5 | 8 of 8 |
| Claude Code + DeepSeek V4 Flash | 8 of 8 |
| **mini-swe-agent + DeepSeek V4 Flash, 100 steps** | **8 of 8** |

mini-swe-agent per task:

| Task | Steps | Tokens in | Tokens out | Agent time |
|---|---|---|---|---|
| 09865f5f | 64 | 3.61M | 65k | 474 s |
| 308a35d6 | 58 | 3.51M | 47k | 378 s |
| 431442c9 | 22 | 0.48M | 22k | 166 s |
| 630221ab | 78 | 6.45M | 102k | 790 s |
| 9cd47f4d | 71 | 2.99M | 38k | 385 s |
| bdba0af0 | 42 | 1.19M | 25k | 211 s |
| c8996ecc | 37 | 1.07M | 26k | 233 s |
| e8084193 | 37 | 1.02M | 19k | 190 s |

Every run ended with "Submitted", none at the step cap. DeepSeek spend for
the 8 tasks was about $0.61 (balance $7.59 → $6.98).

## What it means

- Four agent and model combinations, on two repositories, all sit at the
  ceiling: Sonnet/ansible 29/30, Haiku/ansible 30/30, and the three
  openlibrary pilots above.
- Removing Claude Code's scaffolding did not make these tasks hard. Even a
  bash-only loop with a cheap model reaches a passing patch in well under
  100 steps.
- The pipeline was checked separately: an empty patch scores 0, the
  reference patch scores 1, the images hold no fix or tests, and passing
  patches still pass with every test-file edit stripped.
- A fair refine test needs a pool where the agent fails about half the time.
  Options, none pre-registered:
  - a tighter step cap (for example 30), which the per-task step counts
    above suggest would cause failures;
  - a smaller or older model;
  - a harder repository or the full multi-repository pool, chosen by pilot.

## Deviations

See `deviations.md`. The run was operated under the user's delegation, and
the stopping rule was applied as pre-registered.

## Credit

SWE-bench Pro by Scale AI, MIT License,
<https://github.com/scaleapi/SWE-bench_Pro-os>, commit
`66f92766bba642462d4bbe5479e83f91f9211862`. mini-swe-agent by the SWE-agent
team, MIT License.
