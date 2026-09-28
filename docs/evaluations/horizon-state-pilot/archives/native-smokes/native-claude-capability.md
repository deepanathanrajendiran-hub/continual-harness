# Native Claude capability preflight
Observed 2026-09-20: claude installed at /Users/deeps/.local/bin/claude, version 2.1.276.
Local help exposes non-interactive print mode, tools/allowedTools, Agent definitions, native session handles, and background agent status commands.
This confirms CLI presence only. Authentication, actual Agent freshness/lifecycle, and new Horizon state-mode behavior remain untested until Task 8.
Do not use --dangerously-skip-permissions or alter global settings to run the smoke test.

Read-only `claude auth status --json`: exit 1, loggedIn=false, authMethod=none, apiProvider=firstParty. No account-identifying fields retained. Native smoke currently unavailable; recheck once at Task 8.

Task 8 recheck, 2026-09-23: `/Users/deeps/.local/bin/claude auth status --json` again returned exit 1 with `loggedIn: false`, `authMethod: none`, `apiProvider: firstParty`. Native Claude smoke remains unavailable and unverified/experimental. No login flow, credential change, permission bypass, or global setting change was attempted. Shared Python CLI coverage is not counted as native Claude verification.
