"""Persist users, workspaces and role-bearing memberships."""

import sqlalchemy as sa
from alembic import op

revision = "20261001_0004"
down_revision = "20261001_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(200), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_table(
        "memberships",
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), primary_key=True
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.CheckConstraint(
            "role IN ('owner', 'editor', 'viewer')", name="ck_memberships_role"
        ),
    )


def downgrade() -> None:
    op.drop_table("memberships")
    op.drop_table("workspaces")
    op.drop_table("users")
