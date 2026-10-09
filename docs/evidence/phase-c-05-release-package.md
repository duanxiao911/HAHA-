# Phase C5 — External staging release package evidence

Date: 2026-10-09

## Delivered package

- `compose.release.yaml` deploys PostgreSQL, Redis, one-shot Alembic migration, JWT-only API,
  Dramatiq Worker and Web from content-addressed images. PostgreSQL/Redis remain on an internal Docker
  network; API and Web require explicit loopback binds for an HTTPS ingress.
- `scripts/release_preflight.py` fails closed on missing values, mutable images, short secrets,
  non-HTTPS public origins, wildcard/invalid CORS, public binds and placeholder ownership.
- `scripts/release_smoke.py` verifies the release ID, API health/readiness, Web availability,
  anonymous rejection, authorized project creation, request correlation and SSE reconnect CORS.
- The API `/health` response exposes `HAHA_RELEASE_ID` so the deployment gate can identify the running
  release rather than trusting a filename or mutable tag.
- Release, rollback and ownership runbooks define required inputs, sequence, decision owners, evidence
  and the schema-incompatible restore path.
- GitHub CI validates both the preflight and fully rendered release Compose configuration on every
  change.

Static and regression verification before commit:

```text
Ruff: PASS
Release preflight unit/negative tests: PASS
Full backend suite: 68 passed, 6 skipped, 1 deprecation warning
Strict production-mode preflight: PASS
Rendered compose.release.yaml validation: PASS
```

## Isolated release rehearsal

The rehearsal used a clean `haha-c5-rehearsal` Compose project and locally content-addressed image IDs.
The production preflight still requires registry `name@sha256:digest` references; the relaxed local
image-ID and HTTP modes require explicit flags and are documented as rehearsal-only.

Candidate release smoke result:

```text
health/release identity: PASS
PostgreSQL + Redis readiness: PASS
Web response: PASS
anonymous authentication rejection: PASS
authorized project creation: PASS
request ID propagation: PASS
exact CORS origin: PASS
Authorization + Last-Event-ID preflight: PASS
```

A custom-format pre-rollback backup was created (18,447 bytes) and its catalog was successfully read
with `pg_restore -l` before any image switch.

## Rollback rehearsal

Worker consumption was stopped first. API, Worker and Web were then recreated from the previously
validated C4 content identities without changing the database volume. Verification showed:

```text
API previous image identity restored: PASS
Web previous image identity restored: PASS
API health and dependency readiness: PASS
existing project data preserved: PASS
real browser generation after rollback: PASS
authenticated SSE observed, terminal GET count: 1
browser exceptions: 0
```

The isolated containers, networks and PostgreSQL/Redis volumes were removed after the rehearsal.

## Boundary

C5 proves the deployable package and rollback procedure on an isolated real container topology. It
does not claim that a third-party external staging host has been provisioned, because no deployment
account or DNS/TLS destination was supplied. Before such a deployment, operators must provide real
registry digests, HTTPS origins, managed secrets and named ownership acknowledgements.

The four deferred authentication-default, prompt-boundary, XML entity expansion and ZIP amplification
findings remain release blockers. Phase C completion is not a Production Candidate declaration.
