"""Add durable worker claim and lease state."""

import sqlalchemy as sa
from alembic import op

revision = "20261001_0003"
down_revision = "20261001_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("claimed_by", sa.String(200), nullable=False, server_default=""))
    op.add_column("runs", sa.Column("claimed_at", sa.String(40), nullable=False, server_default=""))
    op.add_column("runs", sa.Column("lease_until", sa.String(40), nullable=False, server_default=""))
    op.add_column("runs", sa.Column("heartbeat_at", sa.String(40), nullable=False, server_default=""))
    op.add_column("runs", sa.Column("lock_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("runs", "lock_version")
    op.drop_column("runs", "heartbeat_at")
    op.drop_column("runs", "lease_until")
    op.drop_column("runs", "claimed_at")
    op.drop_column("runs", "claimed_by")
