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
