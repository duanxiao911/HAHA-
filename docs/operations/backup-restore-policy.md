# PostgreSQL Backup and Restore Policy

- Run one full custom-format PostgreSQL backup every 24 hours.
- Keep seven daily and four weekly recovery points.
- Store production backups outside the application host with encryption at rest and in transit.
- Restrict backup read and restore permissions to the operations role.
- Perform a restore drill into an isolated database at least monthly and after material schema changes.
- Verify Alembic version, identity tables, projects, brief versions, runs, scripts, and evidence after every drill.
- Record duration, backup size, object identifier, operator, and verification result.
- Treat a failed backup or restore verification as a release blocker until investigated.

Current targets are RPO 24 hours and RTO 4 hours. Point-in-time recovery is not yet implemented.

For the repository-controlled current-schema drill, run:

```powershell
python scripts/postgres_restore_drill.py
```

The script only restores into a generated `haha_restore_*` database, verifies the current Alembic
revision and selected cross-module table counts, then removes the isolated database by default. Its
local evidence does not replace encrypted off-host backups, PITR, or an external RTO exercise.
