# Phase C1 — Run event stream evidence

Date: 2026-10-04

## Implemented contract

- Authenticated `GET /api/runs/{run_id}/events` endpoint.
- Existing project/workspace access check is applied before streaming starts.
- SSE messages carry event ID, Run status, attempt, update time and safe error fields.
- Terminal Run states emit `run.terminal` and close the stream.
- Non-terminal streams expire after a caller-selected 1–30 second window.
- Responses disable proxy buffering and caching.

## Verification

The API regression suite covers a completed Run stream and cross-workspace denial.

```text
Ruff: PASS
Pytest: 55 passed, 4 skipped
ESLint: PASS
Next.js production build: PASS
```

The skipped tests require the opt-in PostgreSQL integration environment. Full Phase C evidence will
be recorded after the remaining operational slices are implemented; this document does not claim
Phase C completion or Production Candidate status.
