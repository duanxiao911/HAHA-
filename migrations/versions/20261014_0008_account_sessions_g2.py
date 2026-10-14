"""Add internal credentials, rotating refresh sessions and auth audit."""

import sqlalchemy as sa
from alembic import op

revision = "20261014_0008"
down_revision = "20261014_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_credentials",
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_salt", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(100), nullable=False),
        sa.Column("password_iterations", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.String(40), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_auth_credentials_status"),
        sa.UniqueConstraint("email", "workspace_id", name="uq_auth_credential_email_workspace"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.String(40), nullable=False),
        sa.Column("revoked_at", sa.String(40), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("last_used_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_auth_sessions_owner", "auth_sessions", ["user_id", "workspace_id", "expires_at"])
    op.create_table(
        "auth_audit_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_auth_audit_owner_created", "auth_audit_events", ["user_id", "workspace_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_audit_owner_created", table_name="auth_audit_events")
    op.drop_table("auth_audit_events")
    op.drop_index("ix_auth_sessions_owner", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("auth_credentials")
