# Phase A Evidence 05 — Failed Job Store and Stuck Run Reconciler

Date: 2026-10-01
Status: PASS

## Implemented

- Added durable `failed_jobs` storage with one record per exhausted Run.
- Added Alembic revision `20261001_0005`; applied successfully to PostgreSQL.
- Added bounded expired-lease reconciliation using PostgreSQL row locks with `SKIP LOCKED`.
- First eligible expiry moves a Run to RETRYING, clears the old lease, and increments attempt/lock version.
- Expiry at the configured attempt limit moves the Run to FAILED and persists `lease_exhausted`.
- Added an explicit `scripts/reconcile_stuck_runs.py` command.
- Requeued Runs are published only when a Redis broker is configured.
- Worker records terminal or exhausted failures in the Failed Job Store.

## Tests Executed

```text
PostgreSQL Alembic head: 20261001_0005
PostgreSQL integration tests: 4 passed
Full suite with PostgreSQL enabled: 53 passed
Ruff: all checks passed
```

Validated behavior:

- Local SQLite reconciler follows the same bounded semantics.
- PostgreSQL reconciler stores exhausted jobs transactionally.
- Concurrent PostgreSQL claim/idempotency and completion rollback remain green.
- Empty production-shaped reconciliation command completes safely:

```json
{"requeued": [], "enqueued": [], "failed": []}
```

## Safety Boundary

The reconciler is an explicit command, not an uncontrolled infinite loop. It processes a bounded limit and never retries a Run beyond the configured maximum.
