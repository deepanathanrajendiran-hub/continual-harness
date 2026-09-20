# Web-app release runbook

Owner: [primary release owner]
Backup: [backup release owner]

## Prerequisites

- Approved release version and immutable artifact digest: [version/digest].
- Green CI, staging access, production deploy access, and monitoring access.
- Database changes are backward compatible; current production version is recorded as [rollback version].
- Release window and incident channel are confirmed: [window] / [channel].

## Deployment

1. Announce the start in [channel], record current production health, and confirm [rollback version] is deployable.
2. Deploy [version/digest] to staging. Run the health check plus login and one critical user flow. If any check fails, stop; do not deploy production.
3. Deploy [version/digest] to a production canary or the smallest available batch. Watch health, error rate, and latency for 10 minutes.
4. If the canary is healthy, deploy the remaining production instances. If it is unhealthy, halt and follow the rollback actions.
5. Record the deployed version, timestamps, and release link in [channel/change record].

## Production verification and failure handling

For 15 minutes, verify the production health endpoint, error rate, p95 latency, logs, login, and one critical user flow against the pre-release baseline. If any check fails, halt further changes, capture links and timestamps, notify the owner and backup, and apply the rollback triggers below. Do not mark the release complete until every check passes.

## Rollback triggers

- Two consecutive health-check failures, or error rate/p95 latency breaching [service threshold] for 5 minutes.
- Login or the critical user flow fails in production.
- Any suspected data corruption, security exposure, or unavailable dependency caused by the release.

## Rollback actions

1. Stop the rollout and route traffic away from failed instances where supported.
2. Redeploy [rollback version]. Revert database changes only with the approved [database rollback procedure].
3. Repeat the production verification checks for 15 minutes. Escalate to [incident commander] if recovery checks fail.
4. Announce rollback status in [channel], preserve logs and metrics, and open [incident/follow-up ticket].
