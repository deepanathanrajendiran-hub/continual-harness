# Coordinator-written tool accounts

These are coordinator-authored observations, separate from raw exported lifecycle JSON and native terminal payloads.

- Before dispatch, `git rev-parse --show-toplevel` exited 128 with the expected outside-Git error.
- Initial source and protected-artifact hashes matched `seed-hashes.csv`; trial home was empty.
- Worker `/root/pilot_api_refactor_sol_state_3/state_editor_001` was freshly dispatched at gpt-5.6-sol/high, immediately bound to attempt `request-001`, then observed completed by native collaboration wait/status before step-finish.
- After the worker stopped, coordinator AST symbol inspection and read-only file inspection confirmed the three requested source changes. The protected acceptance test retained both required hash and original nanosecond mtime.
- The worker returned a schema-version-1 update without formatting repair.
- Reviewer `/root/pilot_api_refactor_sol_state_3/independent_reviewer` was freshly dispatched at gpt-5.6-sol/high and observed completed with `verdict: pass` before lifecycle review/complete.
- The reviewer caught a coordinator export-only trailing-LF mismatch in `packet-request-001.raw.json`. The immutable project packet was always correct. The evidence copy was mechanically truncated from 1,891 to 1,890 bytes and reverified at the recorded `08a240…` SHA-256; watched project bytes did not change.

Raw exports are stored separately in `lifecycle-*.json`, `goal-*.raw.json`, `packet-*.raw.json`, `worker-request-001-update.raw.json`, and later reviewer terminal files.
