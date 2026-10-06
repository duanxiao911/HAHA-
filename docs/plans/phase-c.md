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
| C3 | Failed-job operations API | Pending | workspace isolation and bounded retry tests |
| C4 | Next.js operational UI | Pending | browser E2E without polling-only progress |
| C5 | External staging/release package | Pending | deployment, rollback and ownership evidence |

## Real-environment gate

The clean containerized staging validation for completed slices C1 and C2 passed on 2026-10-06. It
covered JWT rejection, PostgreSQL/Redis readiness, Dramatiq delivery, browser generation, bounded SSE,
cancellation during worker downtime and state persistence across service restarts. The validation also
found and closed an inherited API health-check defect on the worker container. See
`docs/evidence/phase-c-real-environment-validation.md`.

C3 remains Pending until the validation commit passes GitHub Actions.

## Deferred security work

The separately reported authentication defaults, prompt-boundary injection, XML expansion and ZIP
amplification findings remain release blockers. They are intentionally not folded into C1 while the
security upgrade is paused, and must be resolved before any Production Candidate decision.

## C1 contract

`GET /api/runs/{run_id}/events` returns `text/event-stream`, reuses the existing membership and
workspace authorization boundary, emits a current `run.status` event, and closes with a
`run.terminal` event for `PASSED`, `FAILED` or `CANCELLED`. A stream is bounded to 30 seconds so
clients reconnect instead of holding an unbounded API worker.
