# Phase C2 — Run cancellation evidence

Date: 2026-10-04

## Implemented contract

- `POST /api/runs/{run_id}/cancel` reuses membership, workspace and write-role checks.
- Cancellation is an atomic repository update in both SQLite and PostgreSQL adapters.
- Repeated cancellation is idempotent and returns the existing `CANCELLED` Run.
- `PASSED` and `FAILED` Runs reject cancellation with HTTP 409.
- Cancelling clears worker claim, heartbeat and lease state.
- Stale worker `save_run` calls cannot overwrite `CANCELLED`.
- Script completion checks the persisted Run and rolls back if cancellation won the race.
- Worker execution reloads cancellation after generation and before failure handling.

## Verification

```text
Ruff: PASS
Pytest: 59 passed, 5 skipped
ESLint: PASS
Next.js production build: PASS
```

The five skipped tests require the opt-in PostgreSQL integration environment. CI executes those tests
with its PostgreSQL service, including the new atomic cancellation and stale-worker protection case.
This evidence completes C2 only; it does not claim full Phase C completion or Production Candidate
status.
