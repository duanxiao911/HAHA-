# Phase B-01 — Observability baseline

Date: 2026-10-01

## Scope

- Structured JSON application and worker events.
- Correlation through caller-supplied or generated `X-Request-ID`.
- HTTP request count and duration metrics in Prometheus text format.
- Separate liveness (`/health`) and dependency readiness (`/ready`) contracts.
- Worker lifecycle events include run ID, worker ID, attempt, terminal status and safe error code.
- No authorization header, bearer token, API key or request body is written to logs.

## Verification

```text
python -m ruff check src/haha_api/observability.py src/haha_api/main.py tests/test_observability.py
PASS

python -m pytest tests/test_observability.py tests/test_api.py -q
10 passed
```

The observability baseline is intentionally dependency-free. It does not claim a hosted metrics backend,
log aggregation service, alert delivery, or distributed trace exporter; those require deployment-specific
credentials and infrastructure.
