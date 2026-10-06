# Phase C — Real-environment validation gate

Date: 2026-10-06

## Scope

This gate validates the completed C1 and C2 slices against a clean, fully containerized staging
environment before C3 begins. It does not complete Phase C and does not declare Production Candidate
status.

The isolated stack used fresh PostgreSQL and Redis volumes and the production images/configuration
from `compose.staging.yaml`:

`Chrome -> Next.js -> FastAPI JWT -> PostgreSQL -> Redis/Dramatiq -> PostgreSQL -> SSE/API -> Next.js`

## Results

- PostgreSQL 17, Redis 8, migrations, FastAPI, Dramatiq and Next.js started successfully.
- `/ready` reported both database and Redis as `ok`; the web route returned HTTP 200.
- Anonymous project creation was rejected with HTTP 401 in staging JWT mode.
- The current creator workspace completed a real browser generation and displayed matching platform,
  duration, aspect ratio, tone, verification and evidence output without browser exceptions.
- The browser-generated Run finished `PASSED` with one persisted script version.
- The Run SSE endpoint emitted the initial `PENDING` state, a bounded timeout event and the terminal
  `CANCELLED` event.
- A Run cancelled while the worker was stopped remained `CANCELLED` after worker delivery; the worker
  logged the job as skipped and no script version was created.
- After API, web and worker restarts, readiness recovered and both the completed and cancelled Run
  states remained intact.

Browser result:

```json
{
  "status": "passed",
  "checks": {
    "platform": true,
    "spec": true,
    "tone": true,
    "verification": true,
    "evidence": true
  },
  "browser_exceptions": []
}
```

Operational result:

```json
{
  "status": "passed",
  "checks": {
    "anonymous_rejected": true,
    "database_ready": true,
    "redis_ready": true,
    "queued_to_worker": true,
    "pending_sse": true,
    "bounded_sse": true,
    "cancelled": true,
    "terminal_sse": true,
    "cancel_survived_worker_delivery": true,
    "cancelled_run_has_no_script": true
  }
}
```

## Defect found and closed

The worker reused the API image and inherited its HTTP `/health` check even though Dramatiq does not
listen on port 8000. Docker therefore marked a functioning worker unhealthy. Both Compose files now
override that image-level check with a worker-process health check. The isolated staging worker was
recreated and reached `healthy` before the final restart and persistence verification.

## Reproducible checks

- `scripts/e2e_next_pipeline.py` accepts `HAHA_E2E_ARTIFACT_PREFIX` and tracks the current creator
  workspace labels and result copy.
- `scripts/staging_phase_c_operations.py` verifies staging authentication, readiness, SSE bounds and
  cancellation/worker race behavior without persisting an access token.
- Local artifacts remain under `artifacts/e2e/` and are not committed.

This gate authorizes planning and implementation of C3 only after the associated commit passes GitHub
Actions. The separately deferred security findings remain release blockers.
