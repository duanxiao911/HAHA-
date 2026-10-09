# Phase C — Run operations and release preparation

Date: 2026-10-04

## Objective

Phase C turns the completed creation pipeline into an operable product surface. It adds observable
run progress, cancellation and failure-management workflows, then prepares external staging and the
separate Production Candidate gate.

Phase C does not declare the product Production Candidate or Production Ready.

## Scope

1. Run event stream: authenticated SSE status and terminal events.
2. Run control: bounded cancellation with worker-safe state handling.
3. Failure operations: workspace-scoped failed-job visibility and retry/resolution actions.
4. Web integration: progress, cancellation and failure-management views.
5. External staging preparation: deployment inputs, release checklist and rollback evidence.

## Delivery order

| Slice | Deliverable | Status | Exit evidence |
|---|---|---|---|
| C1 | Workspace-protected Run SSE endpoint | Complete | API contract and authorization tests |
| C2 | Cancellation API and worker cooperation | Complete | concurrency and terminal-state tests |
| C3 | Failed-job operations API | Complete | workspace isolation and bounded retry tests |
| C4 | Next.js operational UI | Complete | authenticated SSE, cancellation and failed-job browser E2E |
| C5 | External staging/release package | Complete | immutable deployment, rollback and ownership rehearsal |

## Real-environment gate

The clean containerized staging validation for completed slices C1 and C2 passed on 2026-10-06. It
covered JWT rejection, PostgreSQL/Redis readiness, Dramatiq delivery, browser generation, bounded SSE,
cancellation during worker downtime and state persistence across service restarts. The validation also
found and closed an inherited API health-check defect on the worker container. See
`docs/evidence/phase-c-real-environment-validation.md`.

C3 remained Pending until the validation commit passed GitHub Actions on 2026-10-06. C3 then
completed with workspace-scoped failed-job listing, idempotent resolution, atomic bounded retry and
PostgreSQL integration evidence.
See `docs/evidence/phase-c-03-failed-job-operations.md`.

C4 completed on 2026-10-09 with an authenticated fetch-stream SSE client, visible run stages,
cancellation controls and workspace-scoped failed-job actions. A clean staging stack exercised normal
generation, cancellation across Worker restart and failed-job resolution in a real browser. The UI
made one terminal Run GET and did not return to interval polling.
See `docs/evidence/phase-c-04-operational-ui.md`.

C5 completed on 2026-10-09 as a release package and isolated deployment/rollback rehearsal. External
staging now has an immutable-image Compose definition, fail-closed environment preflight, public smoke
gate, named ownership contract and separate release/rollback runbooks. The rehearsal deployed the
candidate, verified backup readability, rolled API/Web/Worker back to the previous image identities,
preserved data and passed the real browser pipeline after rollback.
See `docs/evidence/phase-c-05-release-package.md`.

## Deferred security work

The separately reported authentication defaults, prompt-boundary injection, XML expansion and ZIP
amplification findings remain release blockers. They are intentionally not folded into C1 while the
security upgrade is paused, and must be resolved before any Production Candidate decision.

## C1 contract

`GET /api/runs/{run_id}/events` returns `text/event-stream`, reuses the existing membership and
workspace authorization boundary, emits a current `run.status` event, and closes with a
`run.terminal` event for `PASSED`, `FAILED` or `CANCELLED`. A stream is bounded to 30 seconds so
clients reconnect instead of holding an unbounded API worker.

## C3 contract

`GET /api/failed-jobs` is workspace-scoped and read-only for viewers. Retry and resolution endpoints
require owner/editor write access. Retry atomically consumes one attempt, resolves the current failure
record and enqueues the Run; later failure reopens the record. A Run never exceeds three attempts.

## C5 contract

External deployment accepts only digest-pinned images, HTTPS public origins, exact non-wildcard CORS,
loopback container binds, sufficiently long runtime secrets and explicit accountable owners. Local
image IDs and HTTP loopback URLs are accepted only behind explicit rehearsal flags. A successful C5
package does not override the deferred security release blockers or constitute a Production Candidate.
