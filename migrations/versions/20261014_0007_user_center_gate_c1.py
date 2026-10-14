"""Add durable user-center assets, preferences, history and notifications."""

import sqlalchemy as sa
from alembic import op

revision = "20261014_0007"
down_revision = "20261013_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_center_settings",
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("bio", sa.String(300), nullable=False, server_default=""),
        sa.Column("region", sa.String(100), nullable=False, server_default=""),
        sa.Column("profile_visibility", sa.String(20), nullable=False, server_default="private"),
        sa.Column("history_enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("recommendation_enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notification_enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.CheckConstraint("profile_visibility IN ('private','members','public')", name="ck_user_center_visibility"),
    )
    op.create_table(
        "user_library_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("target_href", sa.String(500), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.CheckConstraint("kind IN ('bookmark','want_to_learn','watch_later')", name="ck_user_library_kind"),
        sa.UniqueConstraint("user_id", "workspace_id", "kind", "target_id", name="uq_user_library_target"),
    )
    op.create_index("ix_user_library_owner_updated", "user_library_items", ["user_id", "workspace_id", "updated_at"])
    op.create_table(
        "user_follows",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("target_id", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("target_href", sa.String(500), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("user_id", "workspace_id", "target_id", name="uq_user_follow_target"),
    )
    op.create_index("ix_user_follows_owner_updated", "user_follows", ["user_id", "workspace_id", "updated_at"])
    op.create_table(
        "user_watch_history",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("content_id", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("target_href", sa.String(500), nullable=False),
        sa.Column("progress_seconds", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("viewed_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("user_id", "workspace_id", "content_id", name="uq_user_history_content"),
    )
    op.create_index("ix_user_history_owner_viewed", "user_watch_history", ["user_id", "workspace_id", "viewed_at"])
    op.create_table(
        "user_notifications",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("target_href", sa.String(500), nullable=False),
        sa.Column("read_at", sa.String(40), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_user_notifications_owner_created", "user_notifications", ["user_id", "workspace_id", "created_at"])
    op.create_table(
        "user_center_audit_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_user_center_audit_owner_created", "user_center_audit_events", ["user_id", "workspace_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_user_center_audit_owner_created", table_name="user_center_audit_events")
    op.drop_table("user_center_audit_events")
    op.drop_index("ix_user_notifications_owner_created", table_name="user_notifications")
    op.drop_table("user_notifications")
    op.drop_index("ix_user_history_owner_viewed", table_name="user_watch_history")
    op.drop_table("user_watch_history")
    op.drop_index("ix_user_follows_owner_updated", table_name="user_follows")
    op.drop_table("user_follows")
    op.drop_index("ix_user_library_owner_updated", table_name="user_library_items")
    op.drop_table("user_library_items")
    op.drop_table("user_center_settings")
