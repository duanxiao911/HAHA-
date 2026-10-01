"""Add an explicit failed job store for exhausted runs."""

import sqlalchemy as sa
from alembic import op

revision = "20261001_0005"
down_revision = "20261001_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "failed_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), nullable=False, unique=True),
        sa.Column("reason", sa.String(4000), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("resolved_at", sa.String(40), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("failed_jobs")
