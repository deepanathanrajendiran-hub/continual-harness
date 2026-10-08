# Findings and stops

## 2026-10-08 01:33 — setup trials blocked by an invalid Keychain token (Task 16, Step 2)

- The setup runner started at 01:32 and called the usage probe before the first trial. The probe exited 1: Claude Code returned `401 Invalid bearer token` (an `api_retry` with `authentication_failed`, then an error result).
- The value stored under Keychain service `tb4-horizon-claude-token` is 74 characters, contains whitespace, and does not start with `sk-ant-`. It is not a `claude setup-token` token. Its content was not printed or recorded.
- The runner was stopped with SIGTERM while sleeping between probe retries: no Harbor job, record, container, or trial existed, and no subscription usage was spent.
- The runner reads the token once at start, so it must be relaunched after the token is replaced (plan step A2), and Task 16 Step 2 repeated.
- Validation (Task 14) and the draw (Task 15) do not use the token and are unaffected.

## 2026-10-08 11:36 — setup Horizon trial ended on a Sonnet 5.5 safety refusal (Task 16, Step 3)

- `setup__interleaved-vigenere__control__a1` (11:12–11:34) passed every Step 3 check: valid, reward 1.0, Claude Code 2.1.293, `claude-sonnet-5-5`, no skill, no Horizon calls, image IDs match.
- `setup__interleaved-vigenere__horizon__a1` (11:34–11:36) ended after 80 s of agent time with Harbor `AgentSafetyRefusalError`. The stream shows Sonnet 5.5's API safeguards stopping a response once (Claude Code continued once, as designed), then `system/model_refusal_no_fallback` with `api_refusal_category: "bio"` and a final `stop_reason: refusal`. No fallback model ran.
- The flagged context is benign cryptanalysis: letter-shift statistics on a sample text about cryptography, music, soil chemistry and computing history. This is a false positive of the API classifier, not a defect in the bench code.
- The Horizon mechanics worked up to the refusal: skill loaded, a goal started with budget 200 turns / 100 minutes, and the ledger was collected with `docker cp`.
- The scorer marks the trial invalid (`exception AgentSafetyRefusalError`, `result is_error`, `run ended on an API error`), as the protocol requires. 0 leftover containers; 0 files under `jobs/`, `records/`, `ledgers/` or `logs/` contain the token.
- Implication for the measured phase: refusals count as invalid, so a pair that refuses twice is excluded, which counts against condition 1 (at least 9 valid pairs). The drawn set includes Security and Science tasks, where such false positives are more likely.
