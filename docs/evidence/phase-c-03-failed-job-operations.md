# Phase C3 — Failed-job operations evidence

Date: 2026-10-06

## Implemented contract

- `GET /api/failed-jobs` lists only jobs whose Run belongs to the authenticated workspace.
- The list defaults to unresolved jobs, supports `include_resolved=true`, and caps each response at
  100 records.
- Viewers may inspect failed jobs; retry and resolve actions require owner or editor write access.
- `POST /api/failed-jobs/{id}/retry` atomically changes one unresolved `FAILED` Run to `RETRYING`,
  increments its attempt and resolves the failed-job record before queue delivery.
- Concurrent retries can consume only one attempt. Repeated, resolved, non-failed or exhausted retries
  return a bounded conflict instead of re-enqueueing work.
- Runs may consume at most three attempts. A failure after manual retry reopens the same failed-job
  record with the latest reason so it remains visible to operators.
- `POST /api/failed-jobs/{id}/resolve` is workspace-scoped and idempotent.
- Redis/Dramatiq remains the primary retry path; local fallback execution now records failures in the
  same durable store.

No schema migration was needed because Phase A already created the required durable failed-job table.

## Verification

```text
Ruff: PASS
Targeted API/repository tests: 32 passed
Concurrent retry race test: PASS (one success, one controlled conflict)
Full local suite: 64 passed, 6 skipped
PostgreSQL 17 migrations: PASS through 20261001_0005
PostgreSQL integration suite: 6 passed
```

The local suite skips the six opt-in PostgreSQL tests; those same six tests were run separately against
a clean PostgreSQL 17 container and passed. The container and its disposable data were removed after
verification.

This evidence completes C3 only. C4 and C5 remain pending, the deferred security findings remain
release blockers, and no Production Candidate status is claimed.
