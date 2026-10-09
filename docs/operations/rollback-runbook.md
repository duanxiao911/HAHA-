# External staging rollback runbook

## Triggers

Rollback when readiness fails after the deployment window, authentication or workspace isolation
regresses, migrations fail, error rate materially increases, queue processing stops, or the release
smoke/browser gate fails. Security findings with active exposure require disabling ingress first.

## Image rollback (preferred)

1. The rollback owner declares the rollback and records the trigger and time.
2. Disable new Web traffic at the ingress and stop Worker consumption.
3. Preserve logs, metrics, the failed-job list and the current database backup identifier.
4. Replace `HAHA_API_IMAGE` and `HAHA_WEB_IMAGE` in the protected environment with the previously
   verified digests. Never use a floating tag.
5. If the previous application is compatible with the current schema, redeploy API, Worker and Web
   without downgrading the database.
6. Run readiness, release smoke and one browser generation before reopening ingress.

## Database rollback (exception path)

Do not run an Alembic downgrade against the only staging database during incident pressure. If the
previous application is not schema-compatible:

1. Keep ingress and Worker disabled.
2. Restore the pre-release custom-format backup into a new isolated PostgreSQL database/volume.
3. Verify Alembic revision, memberships, projects, brief versions, runs, scripts and evidence.
4. Point the previous API and Worker digests to the restored database.
5. Run the complete release smoke and browser gate, then switch ingress.
6. Retain the failed release database read-only until the incident owner approves disposal.

## Closure evidence

Record the trigger, decision owner, old/new image digests, database path chosen, backup identifier,
data-loss window, smoke output, recovery time and follow-up issue. The current targets remain RPO 24
hours and RTO 4 hours; missing or failed restore evidence blocks release sign-off.
