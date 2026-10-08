# Findings and stops

## 2026-10-08 01:33 — setup trials blocked by an invalid Keychain token (Task 16, Step 2)

- The setup runner started at 01:32 and called the usage probe before the first trial. The probe exited 1: Claude Code returned `401 Invalid bearer token` (an `api_retry` with `authentication_failed`, then an error result).
- The value stored under Keychain service `tb4-horizon-claude-token` is 74 characters, contains whitespace, and does not start with `sk-ant-`. It is not a `claude setup-token` token. Its content was not printed or recorded.
- The runner was stopped with SIGTERM while sleeping between probe retries: no Harbor job, record, container, or trial existed, and no subscription usage was spent.
- The runner reads the token once at start, so it must be relaunched after the token is replaced (plan step A2), and Task 16 Step 2 repeated.
- Validation (Task 14) and the draw (Task 15) do not use the token and are unaffected.
