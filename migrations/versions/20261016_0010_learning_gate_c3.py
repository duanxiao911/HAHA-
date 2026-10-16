"""Add Gate C3 server-authoritative learning and growth state."""

import sqlalchemy as sa
from alembic import op

revision = "20261016_0010"
down_revision = "20261015_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_profiles",
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Shanghai"),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_learning_date", sa.String(10), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
    )
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("workspace_id", sa.String(100), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("publisher", sa.String(300), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("verification_status", sa.String(20), nullable=False),
        sa.Column("provenance", sa.String(40), nullable=False),
        sa.Column("checked_at", sa.String(40), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.CheckConstraint(
            "verification_status IN ('verified','pending','demo_only','disputed')",
            name="ck_knowledge_source_verification",
        ),
    )
    op.create_table(
        "learning_paths",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("workspace_id", sa.String(100), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("provenance", sa.String(40), nullable=False),
        sa.Column("verification_status", sa.String(20), nullable=False),
        sa.Column("source_note", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.CheckConstraint("status IN ('draft','published','archived')", name="ck_learning_path_status"),
    )
    op.create_table(
        "learning_units",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("path_id", sa.String(100), nullable=False),
        sa.Column("workspace_id", sa.String(100), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.String(2000), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("required", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["path_id", "workspace_id"], ["learning_paths.id", "learning_paths.workspace_id"]),
        sa.ForeignKeyConstraint(["source_id", "workspace_id"], ["knowledge_sources.id", "knowledge_sources.workspace_id"]),
        sa.UniqueConstraint("path_id", "workspace_id", "position", name="uq_learning_unit_position"),
        sa.CheckConstraint("kind IN ('lesson','quiz')", name="ck_learning_unit_kind"),
    )
    op.create_table(
        "learning_path_enrollments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("path_id", sa.String(100), nullable=False),
        sa.Column("source_content_id", sa.String(200), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enrolled_at", sa.String(40), nullable=False),
        sa.Column("completed_at", sa.String(40), nullable=False, server_default=""),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["path_id", "workspace_id"], ["learning_paths.id", "learning_paths.workspace_id"]),
        sa.UniqueConstraint("user_id", "workspace_id", "path_id", name="uq_learning_enrollment_owner_path"),
        sa.CheckConstraint("status IN ('active','completed')", name="ck_learning_enrollment_status"),
    )
    op.create_index("ix_learning_enrollment_owner", "learning_path_enrollments", ["user_id", "workspace_id", "updated_at"])
    op.create_table(
        "learning_progress",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("path_id", sa.String(100), nullable=False),
        sa.Column("unit_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.String(40), nullable=False),
        sa.Column("completed_at", sa.String(40), nullable=False, server_default=""),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["unit_id", "workspace_id"], ["learning_units.id", "learning_units.workspace_id"]),
        sa.UniqueConstraint("user_id", "workspace_id", "unit_id", name="uq_learning_progress_owner_unit"),
        sa.CheckConstraint("status IN ('not_started','in_progress','completed')", name="ck_learning_progress_status"),
        sa.CheckConstraint("progress_percent BETWEEN 0 AND 100", name="ck_learning_progress_percent"),
    )
    op.create_index("ix_learning_progress_owner_updated", "learning_progress", ["user_id", "workspace_id", "updated_at"])
    op.create_table(
        "knowledge_cards",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("path_id", sa.String(100), nullable=False),
        sa.Column("unit_id", sa.String(100), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("body", sa.String(4000), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("trust_status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["unit_id", "workspace_id"], ["learning_units.id", "learning_units.workspace_id"]),
        sa.ForeignKeyConstraint(["source_id", "workspace_id"], ["knowledge_sources.id", "knowledge_sources.workspace_id"]),
        sa.UniqueConstraint("user_id", "workspace_id", "unit_id", name="uq_knowledge_card_owner_unit"),
    )
    op.create_index("ix_knowledge_card_owner_updated", "knowledge_cards", ["user_id", "workspace_id", "updated_at"])
    op.create_table(
        "quizzes",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("workspace_id", sa.String(100), primary_key=True),
        sa.Column("path_id", sa.String(100), nullable=False),
        sa.Column("unit_id", sa.String(100), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("pass_score", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["unit_id", "workspace_id"], ["learning_units.id", "learning_units.workspace_id"]),
        sa.UniqueConstraint("unit_id", "workspace_id", name="uq_quiz_unit"),
        sa.CheckConstraint("pass_score BETWEEN 0 AND 100", name="ck_quiz_pass_score"),
    )
    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("quiz_id", sa.String(100), nullable=False),
        sa.Column("workspace_id", sa.String(100), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.String(1000), nullable=False),
        sa.Column("choices_json", sa.JSON(), nullable=False),
        sa.Column("correct_choice", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.String(1000), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["quiz_id", "workspace_id"], ["quizzes.id", "quizzes.workspace_id"]),
        sa.ForeignKeyConstraint(["source_id", "workspace_id"], ["knowledge_sources.id", "knowledge_sources.workspace_id"]),
        sa.UniqueConstraint("quiz_id", "workspace_id", "position", name="uq_quiz_question_position"),
    )
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("quiz_id", sa.String(100), nullable=False),
        sa.Column("quiz_version", sa.Integer(), nullable=False),
        sa.Column("answers_json", sa.JSON(), nullable=False),
        sa.Column("question_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["quiz_id", "workspace_id"], ["quizzes.id", "quizzes.workspace_id"]),
    )
    op.create_index("ix_quiz_attempt_owner_created", "quiz_attempts", ["user_id", "workspace_id", "created_at"])
    op.create_table(
        "learning_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("entity_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("activity_date", sa.String(10), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("user_id", "workspace_id", "idempotency_key", name="uq_learning_event_idempotency"),
    )
    op.create_index("ix_learning_events_owner_date", "learning_events", ["user_id", "workspace_id", "activity_date", "event_type"])
    op.create_table(
        "daily_tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("task_date", sa.String(10), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("current_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("user_id", "workspace_id", "task_date", "kind", name="uq_daily_task_owner_date_kind"),
    )
    op.create_index("ix_daily_task_owner_date", "daily_tasks", ["user_id", "workspace_id", "task_date"])
    op.create_table(
        "achievement_definitions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("workspace_id", sa.String(100), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("workspace_id", "code", "version", name="uq_achievement_definition_version"),
    )
    op.create_table(
        "achievement_grants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("definition_id", sa.String(100), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("triggering_event_id", sa.String(64), sa.ForeignKey("learning_events.id"), nullable=False),
        sa.Column("granted_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["definition_id", "workspace_id"], ["achievement_definitions.id", "achievement_definitions.workspace_id"]),
        sa.UniqueConstraint("user_id", "workspace_id", "definition_id", name="uq_achievement_grant_owner_definition"),
    )
    op.create_index("ix_achievement_grant_owner", "achievement_grants", ["user_id", "workspace_id", "granted_at"])


def downgrade() -> None:
    op.drop_index("ix_achievement_grant_owner", table_name="achievement_grants")
    op.drop_table("achievement_grants")
    op.drop_table("achievement_definitions")
    op.drop_index("ix_daily_task_owner_date", table_name="daily_tasks")
    op.drop_table("daily_tasks")
    op.drop_index("ix_learning_events_owner_date", table_name="learning_events")
    op.drop_table("learning_events")
    op.drop_index("ix_quiz_attempt_owner_created", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
    op.drop_table("quiz_questions")
    op.drop_table("quizzes")
    op.drop_index("ix_knowledge_card_owner_updated", table_name="knowledge_cards")
    op.drop_table("knowledge_cards")
    op.drop_index("ix_learning_progress_owner_updated", table_name="learning_progress")
    op.drop_table("learning_progress")
    op.drop_index("ix_learning_enrollment_owner", table_name="learning_path_enrollments")
    op.drop_table("learning_path_enrollments")
    op.drop_table("learning_units")
    op.drop_table("learning_paths")
    op.drop_table("knowledge_sources")
    op.drop_table("learning_profiles")
