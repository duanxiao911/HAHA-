# Phase A Evidence 04 — PostgreSQL Backup and Restore Drill

Date: 2026-10-01
Status: PASS (local production-shaped drill)

## Procedure

1. Stopped the test Worker so the snapshot had no active generation writes.
2. Ran `pg_dump -Fc` against the PostgreSQL 17 `haha` database.
3. Copied the dump to `artifacts/backups/haha-phase-a.dump`.
4. Created an independent `haha_restore` database.
5. Restored the custom-format dump with `pg_restore`.
6. Verified table counts and Alembic version.
7. Started the FastAPI application against `haha_restore`.
8. Called `/ready` and read a restored Run and ScriptVersion through the API.

## Recovery Evidence

```text
dump size: 21,435 bytes
backup + restore elapsed: 2,264 ms
alembic version: 20261001_0004
workspaces: 3
projects: 3
brief_versions: 3
runs: 3
script_versions: 2
script versions with evidence: 2
```

Restored API evidence:

```text
/ready: ready
run status: PASSED
script present: yes
evidence mode: local
verification passed: true
platform: B站
spec: 90秒 · 16:9
```

## Current Recovery Targets

- RPO target: 24 hours, based on one encrypted full backup per day.
- RTO target: 4 hours for this deployment stage.
- Retention target: 7 daily backups and 4 weekly backups.
- Production storage target: encrypted object storage outside the application host, with restricted restore credentials.

These are initial operational targets, not an SLA. The measured local restore time is not presented as a production RTO guarantee.

## Encryption Boundary

The local drill artifact is not a production backup and is stored only in the workspace test artifacts. A production deployment must use encrypted remote storage and must test retrieval from that storage before Production Ready can be considered.
