# Phase B-03 — Staging security and dependency integration

Date: 2026-10-01

## Implemented

- Standalone `compose.staging.yaml` with PostgreSQL 17, Redis 8, Alembic migration,
  JWT-only FastAPI, Dramatiq worker and JWT-aware Next.js frontend.
- Required secret interpolation prevents staging from booting with empty database or JWT secrets.
- API and web ports bind to loopback for the local staging drill.
- Short-lived bootstrap token utility and an operator runbook.
- Frontend stores a supplied short-lived staging token in browser session storage, never in source or build args.

## Full Compose staging result

The complete containerized stack was built and started with real PostgreSQL and Redis dependencies.
The API and frontend images run as numeric non-root user `65532:65532`.

```json
{
  "health": {"status": "ok", "service": "haha-creator-api", "version": "0.2.0"},
  "readiness": {"status": "ready", "checks": {"database": "ok", "redis": "ok"}},
  "web_status": 200,
  "browser_e2e": "passed"
}
```

Alembic upgraded a fresh database through revision `20261001_0005` before the API and worker started.
A short-lived JWT identity created the project, brief and run. The same correlation ID
`f1f2fc91b86448d5a233c555941efd49` appeared on the API enqueue log and the worker start/completion logs;
the worker completed run `run_89a2cd785ed74bd18ffa82f549ace70a` as `PASSED` on attempt 1.

## Docker Hub EOF resolution

Docker Hub metadata requests for the original Python and Node base images failed with TLS `EOF` on this
machine. The production Dockerfiles now use digest-pinned Microsoft Artifact Registry Azure Linux base
images, while Python and Node package registries are configurable build arguments. The local staging drill
used the Tsinghua PyPI mirror and npmmirror; the already cached PostgreSQL and Redis images remained pinned
by service tag. Both API and web production images built successfully, and `docker compose up -d --build`
completed with healthy API, PostgreSQL and Redis services plus a running worker and frontend.

This is a build-network portability fix; secrets remain runtime-only and are not copied into either image.
