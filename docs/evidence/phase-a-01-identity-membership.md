# Phase A Evidence 01 — Persistent Identity and Membership

Date: 2026-10-01
Status: PASS (code and local adapters)

## Implemented

- Added persistent `users`, `workspaces`, and `memberships` tables.
- Added a composite membership key `(user_id, workspace_id)` and constrained roles.
- JWT authentication now verifies identity only; token role claims are not trusted for authorization.
- API authorization resolves the effective role from the repository membership record.
- Development identity bootstrap is limited to explicit development auth mode.
- Added Alembic revision `20261001_0004` for identity and membership persistence.
- Repaired the fresh-database migration chain so `projects.workspace_id` exists before indexing and `runs.workspace_id` is introduced once.

## Security Evidence

- Missing and invalid JWTs are rejected.
- `X-Workspace-ID` cannot override a verified JWT workspace.
- A verified user without membership receives HTTP 403.
- A token claiming `owner` remains read-only when persisted membership is `viewer`.

## Tests Executed

```text
python -m ruff check src tests migrations
python -m pytest -q --tb=short --basetemp=.pytest-runtime
```

Result:

```text
48 passed
Ruff: all checks passed
```

## Scope Boundary

This evidence validates the domain, SQLite adapter, SQLAlchemy metadata, API authorization behavior, and migration source. Fresh PostgreSQL migration execution is intentionally recorded in the next Phase A evidence item.
