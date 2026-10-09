# Phase C4 — Next.js operational UI evidence

Date: 2026-10-09

## Implemented surface

- The creator workbench consumes `GET /api/runs/{id}/events` through an authenticated fetch stream,
  so JWT mode does not depend on the header-limited browser `EventSource` API.
- The client reconnects bounded SSE streams with `Last-Event-ID`, renders the current attempt and the
  `PENDING` through `PASSED` stages, and performs only one final Run read after a terminal event.
- Operators can cancel a non-terminal Run from the progress panel.
- The failed-job panel lists unresolved workspace jobs and exposes retry and idempotent resolution
  actions. GitHub Pages demo mode remains isolated from these live operations.
- CORS now explicitly permits `Last-Event-ID`; a backend contract test protects SSE reconnects from
  browser preflight regressions.
- The browser E2E enters `/creator` explicitly because `/` is the public community route.

## Static and regression verification

```text
Ruff: PASS
Frontend ESLint: PASS
Next.js production build: PASS (/, /community and /creator statically generated)
Backend suite: 65 passed, 6 skipped, 1 deprecation warning
```

The six skipped tests are the opt-in PostgreSQL tests already covered by the Phase C3 clean
PostgreSQL validation. C4 additionally rebuilt and exercised the complete staging topology below.

## Real staging browser verification

A new isolated `compose.staging.yaml` project rebuilt and started PostgreSQL 17, Redis 8, Alembic,
the JWT-only FastAPI service, Dramatiq Worker and production Next.js image. A one-hour staging token
was issued inside the private test stack and was not written to evidence.

Three headless Chrome scenarios passed against `http://127.0.0.1:13000/creator`:

1. Normal generation observed the authenticated SSE request, generated the requested B站 / 90秒 /
   16:9 / 纪录片 output, showed independent verification and evidence, and made exactly one terminal
   Run GET rather than interval polling.
2. With the Worker stopped, the UI exposed and submitted cancellation, rendered `运行已取消`, and
   emitted no browser exception. After the Worker restarted and received the queued message, the
   database still reported `CANCELLED`.
3. A controlled failed-job fixture appeared after UI refresh; the operator action called the resolve
   endpoint and removed the resolved item from the unresolved list.

The reports and screenshots are stored under `artifacts/e2e/phase-c4-*` in the local validation
workspace. The isolated containers, network and PostgreSQL/Redis volumes were removed afterward.

This evidence completes C4 only. C5 remains pending. The deferred authentication-default,
prompt-boundary, XML entity expansion and ZIP amplification findings remain release blockers, and no
Production Candidate status is claimed.
