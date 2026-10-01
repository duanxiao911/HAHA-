# Phase A Evidence 02 — PostgreSQL Integration

Date: 2026-10-01
Status: PASS

## Runtime

- PostgreSQL: 17 Alpine in Docker Desktop
- Host test endpoint: `127.0.0.1:55432`
- Alembic: fresh database upgraded from base to `20261001_0004 (head)`

## Schema Evidence

- Tables: users, workspaces, memberships, projects, brief_versions, runs, script_versions.
- Membership primary key: `(user_id, workspace_id)` with user/workspace foreign keys.
- Membership role check permits only owner/editor/viewer.
- Run idempotency unique constraint: `(workspace_id, project_id, idempotency_key)`.
- Run claim fields and `lock_version` exist with non-null defaults.

## Integration Tests

```text
pytest tests/test_postgres_integration.py -q
3 passed
```

Validated behavior:

- Four concurrent requests with the same scoped idempotency key create one Run.
- Two concurrent workers cannot claim the same Run.
- An expired lease can be reclaimed and advances `lock_version`.
- A forced failure after ScriptVersion insertion rolls back both the script insert and Run update.

## External Build Note

The API image build hit a Docker Hub timeout for `python:3.12-slim`. PostgreSQL validation remained real: local Alembic and tests connected to the PostgreSQL container.
