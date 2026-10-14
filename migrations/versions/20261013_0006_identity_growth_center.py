"""Add durable multi-role identity and growth-center state."""

import sqlalchemy as sa
from alembic import op

revision = "20261013_0006"
down_revision = "20261001_0005"
branch_labels = None
depends_on = None

BUSINESS_ROLES = "'viewer','buyer','learner','creator','contributor','seller','reviewer','admin'"


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("active_role", sa.String(32), nullable=False),
        sa.Column("personalization_enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.CheckConstraint(f"active_role IN ({BUSINESS_ROLES})", name="ck_user_profiles_active_role"),
    )
    op.create_table(
        "role_grants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("granted_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("revoked_at", sa.String(40), nullable=False, server_default=""),
        sa.CheckConstraint(f"role IN ({BUSINESS_ROLES})", name="ck_role_grants_role"),
        sa.CheckConstraint("status IN ('active','revoked')", name="ck_role_grants_status"),
        sa.UniqueConstraint("user_id", "workspace_id", "role", name="uq_role_grant_owner_role"),
    )
    op.create_index("ix_role_grants_owner", "role_grants", ["user_id", "workspace_id"])
    op.create_table(
        "role_applications",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("decision_note", sa.String(1000), nullable=False, server_default=""),
        sa.Column("reviewed_by", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.CheckConstraint(f"role IN ({BUSINESS_ROLES})", name="ck_role_applications_role"),
        sa.CheckConstraint("status IN ('pending','approved','rejected','cancelled')", name="ck_role_applications_status"),
    )
    op.create_index("ix_role_applications_owner_status", "role_applications", ["user_id", "workspace_id", "status"])
    op.create_table(
        "identity_tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("target_href", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("completed_at", sa.String(40), nullable=False, server_default=""),
        sa.CheckConstraint(f"role IN ({BUSINESS_ROLES})", name="ck_identity_tasks_role"),
        sa.CheckConstraint("status IN ('open','completed','cancelled')", name="ck_identity_tasks_status"),
    )
    op.create_index("ix_identity_tasks_owner_status", "identity_tasks", ["user_id", "workspace_id", "status"])
    op.create_table(
        "identity_audit_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("actor_user_id", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("target_role", sa.String(32), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_identity_audit_owner_created", "identity_audit_events", ["user_id", "workspace_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_identity_audit_owner_created", table_name="identity_audit_events")
    op.drop_table("identity_audit_events")
    op.drop_index("ix_identity_tasks_owner_status", table_name="identity_tasks")
    op.drop_table("identity_tasks")
    op.drop_index("ix_role_applications_owner_status", table_name="role_applications")
    op.drop_table("role_applications")
    op.drop_index("ix_role_grants_owner", table_name="role_grants")
    op.drop_table("role_grants")
    op.drop_table("user_profiles")
