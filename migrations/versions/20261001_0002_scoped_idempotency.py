"""Scope idempotency keys to workspace and project."""

import sqlalchemy as sa
from alembic import op

revision = "20261001_0002"
down_revision = "20260929_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("workspace_id", sa.String(100), nullable=True))
    op.add_column("runs", sa.Column("request_fingerprint", sa.String(64), nullable=True))
    op.execute(
        "UPDATE runs SET workspace_id = projects.workspace_id "
        "FROM projects WHERE runs.project_id = projects.id"
    )
    op.execute("UPDATE runs SET request_fingerprint = repeat('0', 64)")
    op.alter_column("runs", "workspace_id", nullable=False)
    op.alter_column("runs", "request_fingerprint", nullable=False)
    op.drop_constraint("runs_idempotency_key_key", "runs", type_="unique")
    op.create_unique_constraint(
        "uq_run_idempotency_scope",
        "runs",
        ["workspace_id", "project_id", "idempotency_key"],
    )
    op.create_index("ix_runs_workspace_id", "runs", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_runs_workspace_id", table_name="runs")
    op.drop_constraint("uq_run_idempotency_scope", "runs", type_="unique")
    op.create_unique_constraint("runs_idempotency_key_key", "runs", ["idempotency_key"])
    op.drop_column("runs", "request_fingerprint")
    op.drop_column("runs", "workspace_id")
