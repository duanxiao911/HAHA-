# Phase B-02 — Continuous integration

Date: 2026-10-01

## Required gates

The workflow `.github/workflows/ci.yml` defines three fail-closed jobs:

1. Backend static checks, Alembic migrations, full PostgreSQL test suite, and a real Redis/Dramatiq worker integration run.
2. Frontend frozen dependency install, ESLint, and production Next.js build.
3. API and web container builds, only after both test jobs pass.

The workflow has read-only repository permissions, explicit timeouts, service health checks,
dependency caching, and per-ref concurrency cancellation.

## Local verification

```text
python -m ruff check src/haha_api src/haha_worker tests/test_observability.py
PASS

python -m pytest -q
52 passed, 4 PostgreSQL-only tests skipped without HAHA_TEST_POSTGRES_URL
```

GitHub-hosted execution remains `UNKNOWN` until the workflow is pushed to GitHub and a run URL exists.
No hosted CI success is claimed by this evidence file.
