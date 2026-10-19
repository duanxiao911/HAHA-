# PostgreSQL Backup and Restore Policy

- Run one full custom-format PostgreSQL backup every 24 hours.
- Keep seven daily and four weekly recovery points.
- Store production backups outside the application host with encryption at rest and in transit.
- Restrict backup read and restore permissions to the operations role.
- Perform a restore drill into an isolated database at least monthly and after material schema changes.
- Verify Alembic version, identity tables, projects, brief versions, runs, scripts, and evidence after every drill.
- Record duration, backup size, object identifier, operator, and verification result.
- Treat a failed backup or restore verification as a release blocker until investigated.
- Back up the durable community-media store at the same recovery point as PostgreSQL.
- Reconcile every media object with `community_media_assets` by storage key, byte size and SHA-256;
  missing database objects and orphan files both fail the recovery gate.

Current targets are RPO 24 hours and RTO 4 hours. Point-in-time recovery is not yet implemented.

For the repository-controlled current-schema drill, run:

```powershell
python scripts/postgres_restore_drill.py
```

The script only restores into a generated `haha_restore_*` database, verifies the current Alembic
revision and selected cross-module table counts, then removes the isolated database by default.

For the media volume drill, run:

```powershell
python scripts/media_restore_drill.py --require-files
```

The media drill creates a generated ZIP, checks the live volume against PostgreSQL, restores into a
temporary local directory and compares the restored manifest. On 2026-10-19 the isolated release
stack passed with one database record and one file. The long-lived development volume has five
historical files with no database records; they are retained pending explicit cleanup approval.

Local evidence does not replace encrypted off-host backups, PITR, synchronized database/object-store
snapshots, malware scanning, or an external RTO exercise.
