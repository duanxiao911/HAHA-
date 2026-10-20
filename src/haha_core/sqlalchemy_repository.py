"""SQLAlchemy repository used by PostgreSQL production deployments."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    func,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from haha_auth.domain import AuthAuditEvent, AuthCredential, AuthSession
from haha_core.domain import BriefVersion, FailedJob, Project, Run, RunStatus, ScriptVersion
from haha_core.repository import RepositoryConflictError
from haha_identity.domain import (
    IdentityAuditEvent,
    IdentityTask,
    RoleApplication,
    RoleGrant,
    UserProfile,
)
from haha_learning.domain import (
    AchievementDefinition,
    AchievementGrant,
    DailyTask,
    KnowledgeCard,
    KnowledgeSource,
    LearningActivityCommit,
    LearningConflictError,
    LearningEvent,
    LearningPath,
    LearningProfile,
    LearningProgress,
    LearningUnit,
    PathEnrollment,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    TutorInteraction,
)
from haha_learning.seed import catalog_records
from haha_user_center.domain import (
    LibraryItem,
    UserCenterAuditEvent,
    UserCenterSettings,
    UserFollow,
    UserNotification,
    WatchHistoryItem,
)

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", String(200), primary_key=True),
    Column("email", String(320), nullable=False),
    Column("created_at", String(40), nullable=False),
)

workspaces = Table(
    "workspaces",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("created_at", String(40), nullable=False),
)

memberships = Table(
    "memberships",
    metadata,
    Column("user_id", String(200), ForeignKey("users.id"), primary_key=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), primary_key=True),
    Column("role", String(20), nullable=False),
    Column("created_at", String(40), nullable=False),
)

auth_credentials = Table(
    "auth_credentials",
    metadata,
    Column("user_id", String(200), ForeignKey("users.id"), primary_key=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), primary_key=True),
    Column("email", String(320), nullable=False),
    Column("password_salt", String(100), nullable=False),
    Column("password_hash", String(100), nullable=False),
    Column("password_iterations", Integer, nullable=False),
    Column("status", String(20), nullable=False),
    Column("failed_attempts", Integer, nullable=False, server_default="0"),
    Column("locked_until", String(40), nullable=False, server_default=""),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("email", "workspace_id", name="uq_auth_credential_email_workspace"),
)
Index(
    "uq_auth_credential_email_lower",
    func.lower(auth_credentials.c.email),
    unique=True,
)

auth_sessions = Table(
    "auth_sessions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("refresh_token_hash", String(64), nullable=False),
    Column("expires_at", String(40), nullable=False),
    Column("revoked_at", String(40), nullable=False, server_default=""),
    Column("created_at", String(40), nullable=False),
    Column("last_used_at", String(40), nullable=False),
)

auth_audit_events = Table(
    "auth_audit_events",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), nullable=False, index=True),
    Column("workspace_id", String(100), nullable=False, index=True),
    Column("event_type", String(100), nullable=False),
    Column("detail_json", JSON, nullable=False),
    Column("created_at", String(40), nullable=False),
)

user_profiles = Table(
    "user_profiles",
    metadata,
    Column("user_id", String(200), ForeignKey("users.id"), primary_key=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), primary_key=True),
    Column("display_name", String(200), nullable=False),
    Column("active_role", String(32), nullable=False),
    Column("personalization_enabled", Integer, nullable=False, server_default="0"),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)

role_grants = Table(
    "role_grants",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("role", String(32), nullable=False),
    Column("status", String(20), nullable=False),
    Column("scope_json", JSON, nullable=False),
    Column("granted_by", String(200), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("revoked_at", String(40), nullable=False, server_default=""),
    UniqueConstraint("user_id", "workspace_id", "role", name="uq_role_grant_owner_role"),
)

role_applications = Table(
    "role_applications",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("role", String(32), nullable=False),
    Column("status", String(20), nullable=False, index=True),
    Column("reason", String(1000), nullable=False),
    Column("decision_note", String(1000), nullable=False, server_default=""),
    Column("reviewed_by", String(200), nullable=False, server_default=""),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)

identity_tasks = Table(
    "identity_tasks",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("role", String(32), nullable=False),
    Column("kind", String(64), nullable=False),
    Column("title", String(300), nullable=False),
    Column("description", String(2000), nullable=False),
    Column("target_href", String(500), nullable=False),
    Column("status", String(20), nullable=False, index=True),
    Column("created_at", String(40), nullable=False),
    Column("completed_at", String(40), nullable=False, server_default=""),
)

identity_audit_events = Table(
    "identity_audit_events",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), nullable=False, index=True),
    Column("workspace_id", String(100), nullable=False, index=True),
    Column("actor_user_id", String(200), nullable=False),
    Column("event_type", String(100), nullable=False),
    Column("target_role", String(32), nullable=False),
    Column("detail_json", JSON, nullable=False),
    Column("created_at", String(40), nullable=False),
)

user_center_settings = Table(
    "user_center_settings",
    metadata,
    Column("user_id", String(200), ForeignKey("users.id"), primary_key=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), primary_key=True),
    Column("bio", String(300), nullable=False, server_default=""),
    Column("region", String(100), nullable=False, server_default=""),
    Column("profile_visibility", String(20), nullable=False, server_default="private"),
    Column("history_enabled", Integer, nullable=False, server_default="1"),
    Column("recommendation_enabled", Integer, nullable=False, server_default="1"),
    Column("notification_enabled", Integer, nullable=False, server_default="1"),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)

user_library_items = Table(
    "user_library_items",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("kind", String(32), nullable=False),
    Column("target_id", String(200), nullable=False),
    Column("title", String(200), nullable=False),
    Column("target_href", String(500), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("user_id", "workspace_id", "kind", "target_id", name="uq_user_library_target"),
)

user_follows = Table(
    "user_follows",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("target_id", String(200), nullable=False),
    Column("display_name", String(200), nullable=False),
    Column("target_href", String(500), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("user_id", "workspace_id", "target_id", name="uq_user_follow_target"),
)

user_watch_history = Table(
    "user_watch_history",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("content_id", String(200), nullable=False),
    Column("title", String(200), nullable=False),
    Column("target_href", String(500), nullable=False),
    Column("progress_seconds", Integer, nullable=False),
    Column("duration_seconds", Integer, nullable=False),
    Column("completed", Integer, nullable=False, server_default="0"),
    Column("viewed_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("user_id", "workspace_id", "content_id", name="uq_user_history_content"),
)

user_notifications = Table(
    "user_notifications",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("kind", String(32), nullable=False),
    Column("title", String(200), nullable=False),
    Column("body", String(1000), nullable=False),
    Column("target_href", String(500), nullable=False),
    Column("read_at", String(40), nullable=False, server_default=""),
    Column("created_at", String(40), nullable=False),
)

user_center_audit_events = Table(
    "user_center_audit_events",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), nullable=False, index=True),
    Column("workspace_id", String(100), nullable=False, index=True),
    Column("event_type", String(100), nullable=False),
    Column("detail_json", JSON, nullable=False),
    Column("created_at", String(40), nullable=False),
)

learning_profiles = Table(
    "learning_profiles",
    metadata,
    Column("user_id", String(200), ForeignKey("users.id"), primary_key=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), primary_key=True),
    Column("timezone", String(64), nullable=False),
    Column("current_streak", Integer, nullable=False, server_default="0"),
    Column("longest_streak", Integer, nullable=False, server_default="0"),
    Column("last_learning_date", String(10), nullable=False, server_default=""),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)

knowledge_sources = Table(
    "knowledge_sources",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("workspace_id", String(100), primary_key=True),
    Column("title", String(300), nullable=False),
    Column("publisher", String(300), nullable=False),
    Column("source_type", String(40), nullable=False),
    Column("url", String(1000), nullable=False),
    Column("version", Integer, nullable=False),
    Column("verification_status", String(20), nullable=False),
    Column("provenance", String(40), nullable=False),
    Column("checked_at", String(40), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)

learning_paths = Table(
    "learning_paths",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("workspace_id", String(100), primary_key=True),
    Column("title", String(300), nullable=False),
    Column("summary", String(2000), nullable=False),
    Column("status", String(20), nullable=False),
    Column("version", Integer, nullable=False),
    Column("provenance", String(40), nullable=False),
    Column("verification_status", String(20), nullable=False),
    Column("source_note", String(1000), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)

learning_units = Table(
    "learning_units",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("path_id", String(100), nullable=False),
    Column("workspace_id", String(100), primary_key=True),
    Column("position", Integer, nullable=False),
    Column("kind", String(32), nullable=False),
    Column("title", String(300), nullable=False),
    Column("summary", String(2000), nullable=False),
    Column("source_id", String(100), nullable=False),
    Column("version", Integer, nullable=False),
    Column("required", Integer, nullable=False, server_default="1"),
    Column("estimated_minutes", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    ForeignKeyConstraint(["path_id", "workspace_id"], ["learning_paths.id", "learning_paths.workspace_id"]),
    ForeignKeyConstraint(["source_id", "workspace_id"], ["knowledge_sources.id", "knowledge_sources.workspace_id"]),
    UniqueConstraint("path_id", "workspace_id", "position", name="uq_learning_unit_position"),
)

learning_path_enrollments = Table(
    "learning_path_enrollments",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("path_id", String(100), nullable=False),
    Column("source_content_id", String(200), nullable=False),
    Column("status", String(20), nullable=False),
    Column("version", Integer, nullable=False),
    Column("enrolled_at", String(40), nullable=False),
    Column("completed_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    ForeignKeyConstraint(["path_id", "workspace_id"], ["learning_paths.id", "learning_paths.workspace_id"]),
    UniqueConstraint("user_id", "workspace_id", "path_id", name="uq_learning_enrollment_owner_path"),
)

learning_progress = Table(
    "learning_progress",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("path_id", String(100), nullable=False),
    Column("unit_id", String(100), nullable=False),
    Column("status", String(20), nullable=False),
    Column("progress_percent", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    Column("started_at", String(40), nullable=False),
    Column("completed_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    ForeignKeyConstraint(["unit_id", "workspace_id"], ["learning_units.id", "learning_units.workspace_id"]),
    UniqueConstraint("user_id", "workspace_id", "unit_id", name="uq_learning_progress_owner_unit"),
)

knowledge_cards = Table(
    "knowledge_cards",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("path_id", String(100), nullable=False),
    Column("unit_id", String(100), nullable=False),
    Column("topic", String(200), nullable=False),
    Column("body", String(4000), nullable=False),
    Column("source_id", String(100), nullable=False),
    Column("source_version", Integer, nullable=False),
    Column("trust_status", String(20), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    ForeignKeyConstraint(["unit_id", "workspace_id"], ["learning_units.id", "learning_units.workspace_id"]),
    ForeignKeyConstraint(["source_id", "workspace_id"], ["knowledge_sources.id", "knowledge_sources.workspace_id"]),
    UniqueConstraint("user_id", "workspace_id", "unit_id", name="uq_knowledge_card_owner_unit"),
)

quizzes = Table(
    "quizzes",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("workspace_id", String(100), primary_key=True),
    Column("path_id", String(100), nullable=False),
    Column("unit_id", String(100), nullable=False),
    Column("title", String(300), nullable=False),
    Column("version", Integer, nullable=False),
    Column("pass_score", Integer, nullable=False),
    Column("status", String(20), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    ForeignKeyConstraint(["unit_id", "workspace_id"], ["learning_units.id", "learning_units.workspace_id"]),
    UniqueConstraint("unit_id", "workspace_id", name="uq_quiz_unit"),
)

quiz_questions = Table(
    "quiz_questions",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("quiz_id", String(100), nullable=False),
    Column("workspace_id", String(100), primary_key=True),
    Column("position", Integer, nullable=False),
    Column("prompt", String(1000), nullable=False),
    Column("choices_json", JSON, nullable=False),
    Column("correct_choice", Integer, nullable=False),
    Column("explanation", String(1000), nullable=False),
    Column("source_id", String(100), nullable=False),
    Column("version", Integer, nullable=False),
    ForeignKeyConstraint(["quiz_id", "workspace_id"], ["quizzes.id", "quizzes.workspace_id"]),
    ForeignKeyConstraint(["source_id", "workspace_id"], ["knowledge_sources.id", "knowledge_sources.workspace_id"]),
    UniqueConstraint("quiz_id", "workspace_id", "position", name="uq_quiz_question_position"),
)

quiz_attempts = Table(
    "quiz_attempts",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("quiz_id", String(100), nullable=False),
    Column("quiz_version", Integer, nullable=False),
    Column("answers_json", JSON, nullable=False),
    Column("question_snapshot_json", JSON, nullable=False),
    Column("score", Integer, nullable=False),
    Column("passed", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    ForeignKeyConstraint(["quiz_id", "workspace_id"], ["quizzes.id", "quizzes.workspace_id"]),
)

learning_events = Table(
    "learning_events",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("event_type", String(64), nullable=False, index=True),
    Column("entity_type", String(64), nullable=False),
    Column("entity_id", String(100), nullable=False),
    Column("entity_version", Integer, nullable=False),
    Column("idempotency_key", String(200), nullable=False),
    Column("activity_date", String(10), nullable=False, index=True),
    Column("payload_json", JSON, nullable=False),
    Column("created_at", String(40), nullable=False),
    UniqueConstraint("user_id", "workspace_id", "idempotency_key", name="uq_learning_event_idempotency"),
)

tutor_interactions = Table(
    "tutor_interactions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("idempotency_key", String(200), nullable=False),
    Column("request_fingerprint", String(64), nullable=False),
    Column("question", String(1000), nullable=False),
    Column("status", String(20), nullable=False),
    Column("answer", String(4000), nullable=False, server_default=""),
    Column("citations_json", JSON, nullable=False),
    Column("model", String(100), nullable=False, server_default=""),
    Column("request_id", String(200), nullable=False, server_default=""),
    Column("input_tokens", Integer, nullable=False, server_default="0"),
    Column("output_tokens", Integer, nullable=False, server_default="0"),
    Column("latency_ms", Integer, nullable=False, server_default="0"),
    Column("error_code", String(64), nullable=False, server_default=""),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint(
        "user_id", "workspace_id", "idempotency_key", name="uq_tutor_interaction_idempotency"
    ),
)

daily_tasks = Table(
    "daily_tasks",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("task_date", String(10), nullable=False, index=True),
    Column("kind", String(40), nullable=False),
    Column("title", String(200), nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("target_count", Integer, nullable=False),
    Column("current_count", Integer, nullable=False),
    Column("status", String(20), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("user_id", "workspace_id", "task_date", "kind", name="uq_daily_task_owner_date_kind"),
)

achievement_definitions = Table(
    "achievement_definitions",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("workspace_id", String(100), primary_key=True),
    Column("code", String(64), nullable=False),
    Column("title", String(200), nullable=False),
    Column("description", String(1000), nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("threshold", Integer, nullable=False),
    Column("points", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    Column("status", String(20), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("workspace_id", "code", "version", name="uq_achievement_definition_version"),
)

achievement_grants = Table(
    "achievement_grants",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), ForeignKey("users.id"), nullable=False, index=True),
    Column("workspace_id", String(100), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("definition_id", String(100), nullable=False),
    Column("definition_version", Integer, nullable=False),
    Column("triggering_event_id", String(64), ForeignKey("learning_events.id"), nullable=False),
    Column("granted_at", String(40), nullable=False),
    ForeignKeyConstraint(["definition_id", "workspace_id"], ["achievement_definitions.id", "achievement_definitions.workspace_id"]),
    UniqueConstraint("user_id", "workspace_id", "definition_id", name="uq_achievement_grant_owner_definition"),
)

projects = Table(
    "projects",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("workspace_id", String(100), nullable=False, index=True),
    Column("title", String(200), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)

brief_versions = Table(
    "brief_versions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("project_id", String(64), nullable=False, index=True),
    Column("version", Integer, nullable=False),
    Column("payload_json", JSON, nullable=False),
    Column("created_at", String(40), nullable=False),
)

runs = Table(
    "runs",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("workspace_id", String(100), nullable=False, index=True),
    Column("project_id", String(64), nullable=False, index=True),
    Column("brief_version_id", String(64), nullable=False, index=True),
    Column("status", String(20), nullable=False, index=True),
    Column("model_preference", String(100), nullable=False),
    Column("idempotency_key", String(200), nullable=False),
    Column("request_fingerprint", String(64), nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("error_code", String(100), nullable=False),
    Column("error_message", String(4000), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    Column("claimed_by", String(200), nullable=False, server_default=""),
    Column("claimed_at", String(40), nullable=False, server_default=""),
    Column("lease_until", String(40), nullable=False, server_default=""),
    Column("heartbeat_at", String(40), nullable=False, server_default=""),
    Column("lock_version", Integer, nullable=False, server_default="0"),
    UniqueConstraint(
        "workspace_id", "project_id", "idempotency_key", name="uq_run_idempotency_scope"
    ),
)

script_versions = Table(
    "script_versions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("project_id", String(64), nullable=False, index=True),
    Column("run_id", String(64), nullable=False, unique=True),
    Column("brief_version_id", String(64), nullable=False),
    Column("version", Integer, nullable=False),
    Column("payload_json", JSON, nullable=False),
    Column("evidence_json", JSON, nullable=False),
    Column("created_at", String(40), nullable=False),
)

failed_jobs = Table(
    "failed_jobs",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("run_id", String(64), ForeignKey("runs.id"), nullable=False, unique=True),
    Column("reason", String(4000), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("resolved_at", String(40), nullable=False, server_default=""),
)


def create_database_engine(database_url: str) -> Engine:
    options: dict[str, Any] = {"pool_pre_ping": True}
    if database_url == "sqlite+pysqlite:///:memory:":
        options.update(
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(database_url, **options)


class SQLAlchemyCreatorRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine = create_database_engine(database_url)
        if create_schema:
            metadata.create_all(self.engine)

    @staticmethod
    def _insert_ignore(
        connection: Any,
        table: Table,
        values: dict[str, Any],
        conflict_columns: list[str],
    ) -> None:
        """Insert once without racing concurrent bootstrap requests."""
        index_elements = [getattr(table.c, column) for column in conflict_columns]
        if connection.dialect.name == "postgresql":
            connection.execute(
                postgresql_insert(table)
                .values(**values)
                .on_conflict_do_nothing(index_elements=index_elements)
            )
            return
        if connection.dialect.name == "sqlite":
            connection.execute(
                sqlite_insert(table)
                .values(**values)
                .on_conflict_do_nothing(index_elements=index_elements)
            )
            return
        criteria = [
            getattr(table.c, column) == values[column] for column in conflict_columns
        ]
        if connection.scalar(select(func.count()).select_from(table).where(*criteria)) == 0:
            connection.execute(table.insert().values(**values))

    @staticmethod
    def _insert_ignore_created(
        connection: Any,
        table: Table,
        values: dict[str, Any],
        conflict_columns: list[str],
    ) -> bool:
        """Return whether an insert won its uniqueness race."""
        index_elements = [getattr(table.c, column) for column in conflict_columns]
        if connection.dialect.name == "postgresql":
            result = connection.execute(
                postgresql_insert(table)
                .values(**values)
                .on_conflict_do_nothing(index_elements=index_elements)
                .returning(*table.primary_key.columns)
            )
            return result.first() is not None
        if connection.dialect.name == "sqlite":
            result = connection.execute(
                sqlite_insert(table)
                .values(**values)
                .on_conflict_do_nothing(index_elements=index_elements)
            )
            return result.rowcount == 1
        criteria = [
            getattr(table.c, column) == values[column] for column in conflict_columns
        ]
        if connection.scalar(select(func.count()).select_from(table).where(*criteria)):
            return False
        connection.execute(table.insert().values(**values))
        return True

    @staticmethod
    def _upsert(
        connection: Any,
        table: Table,
        values: dict[str, Any],
        conflict_columns: list[str],
        update_columns: list[str],
    ) -> None:
        """Atomically persist mutable user state on PostgreSQL and SQLite."""
        index_elements = [getattr(table.c, column) for column in conflict_columns]
        update_values = {column: values[column] for column in update_columns}
        if connection.dialect.name == "postgresql":
            connection.execute(
                postgresql_insert(table)
                .values(**values)
                .on_conflict_do_update(index_elements=index_elements, set_=update_values)
            )
            return
        if connection.dialect.name == "sqlite":
            connection.execute(
                sqlite_insert(table)
                .values(**values)
                .on_conflict_do_update(index_elements=index_elements, set_=update_values)
            )
            return
        criteria = [
            getattr(table.c, column) == values[column] for column in conflict_columns
        ]
        if connection.scalar(select(func.count()).select_from(table).where(*criteria)):
            connection.execute(table.update().where(*criteria).values(**update_values))
        else:
            connection.execute(table.insert().values(**values))

    def save_project(self, project: Project) -> None:
        with self.engine.begin() as connection:
            connection.execute(projects.insert().values(**asdict(project)))

    def ping(self) -> bool:
        with self.engine.connect() as connection:
            return connection.scalar(select(1)) == 1

    def ensure_identity(
        self,
        user_id: str,
        workspace_id: str,
        *,
        role: str,
        email: str = "",
        workspace_name: str = "",
    ) -> None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with self.engine.begin() as connection:
            self._insert_ignore(
                connection,
                users,
                {"id": user_id, "email": email, "created_at": now},
                ["id"],
            )
            self._insert_ignore(
                connection,
                workspaces,
                {
                    "id": workspace_id,
                    "name": workspace_name or workspace_id,
                    "created_at": now,
                },
                ["id"],
            )
            self._insert_ignore(
                connection,
                memberships,
                {
                    "user_id": user_id,
                    "workspace_id": workspace_id,
                    "role": role,
                    "created_at": now,
                },
                ["user_id", "workspace_id"],
            )

    def get_membership_role(self, user_id: str, workspace_id: str) -> str | None:
        with self.engine.connect() as connection:
            role = connection.scalar(
                select(memberships.c.role).where(
                    memberships.c.user_id == user_id,
                    memberships.c.workspace_id == workspace_id,
                )
            )
        return str(role) if role else None

    def get_auth_credential(self, email: str, workspace_id: str) -> AuthCredential | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(auth_credentials).where(
                        auth_credentials.c.email == email,
                        auth_credentials.c.workspace_id == workspace_id,
                    )
                )
                .mappings()
                .first()
            )
        return AuthCredential(**row) if row else None

    def get_auth_credential_by_email(self, email: str) -> AuthCredential | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(auth_credentials).where(
                        func.lower(auth_credentials.c.email) == email.lower()
                    )
                )
                .mappings()
                .first()
            )
        return AuthCredential(**row) if row else None

    def create_personal_account(
        self, credential: AuthCredential, *, workspace_name: str, display_name: str
    ) -> bool:
        now = credential.created_at
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    users.insert().values(
                        id=credential.user_id,
                        email=credential.email,
                        created_at=now,
                    )
                )
                connection.execute(
                    workspaces.insert().values(
                        id=credential.workspace_id,
                        name=workspace_name,
                        created_at=now,
                    )
                )
                connection.execute(
                    memberships.insert().values(
                        user_id=credential.user_id,
                        workspace_id=credential.workspace_id,
                        role="owner",
                        created_at=now,
                    )
                )
                connection.execute(
                    user_profiles.insert().values(
                        user_id=credential.user_id,
                        workspace_id=credential.workspace_id,
                        display_name=display_name,
                        active_role="viewer",
                        personalization_enabled=0,
                        created_at=now,
                        updated_at=now,
                    )
                )
                connection.execute(auth_credentials.insert().values(**asdict(credential)))
        except IntegrityError:
            return False
        return True

    def save_auth_credential(self, credential: AuthCredential) -> None:
        values = asdict(credential)
        with self.engine.begin() as connection:
            exists = connection.scalar(
                select(auth_credentials.c.user_id).where(
                    auth_credentials.c.user_id == credential.user_id,
                    auth_credentials.c.workspace_id == credential.workspace_id,
                )
            )
            query = (
                auth_credentials.update().where(
                    auth_credentials.c.user_id == credential.user_id,
                    auth_credentials.c.workspace_id == credential.workspace_id,
                )
                if exists
                else auth_credentials.insert()
            )
            connection.execute(query.values(**values))

    def get_auth_session(self, session_id: str) -> AuthSession | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(select(auth_sessions).where(auth_sessions.c.id == session_id))
                .mappings()
                .first()
            )
        return AuthSession(**row) if row else None

    def list_auth_sessions(self, user_id: str, workspace_id: str) -> list[AuthSession]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(auth_sessions)
                    .where(
                        auth_sessions.c.user_id == user_id,
                        auth_sessions.c.workspace_id == workspace_id,
                    )
                    .order_by(auth_sessions.c.created_at.desc())
                )
                .mappings()
                .all()
            )
        return [AuthSession(**row) for row in rows]

    def save_auth_session(self, session: AuthSession) -> None:
        values = asdict(session)
        with self.engine.begin() as connection:
            exists = connection.scalar(
                select(auth_sessions.c.id).where(auth_sessions.c.id == session.id)
            )
            query = (
                auth_sessions.update().where(auth_sessions.c.id == session.id)
                if exists
                else auth_sessions.insert()
            )
            connection.execute(query.values(**values))

    def rotate_auth_session(self, session: AuthSession, expected_hash: str) -> bool:
        """Atomically consume one refresh secret and install its replacement."""
        with self.engine.begin() as connection:
            result = connection.execute(
                auth_sessions.update()
                .where(
                    auth_sessions.c.id == session.id,
                    auth_sessions.c.refresh_token_hash == expected_hash,
                    auth_sessions.c.revoked_at == "",
                )
                .values(
                    refresh_token_hash=session.refresh_token_hash,
                    expires_at=session.expires_at,
                    revoked_at=session.revoked_at,
                    last_used_at=session.last_used_at,
                )
            )
        return result.rowcount == 1

    def revoke_auth_session(
        self, session_id: str, user_id: str, workspace_id: str, revoked_at: str
    ) -> bool:
        with self.engine.begin() as connection:
            result = connection.execute(
                auth_sessions.update()
                .where(
                    auth_sessions.c.id == session_id,
                    auth_sessions.c.user_id == user_id,
                    auth_sessions.c.workspace_id == workspace_id,
                    auth_sessions.c.revoked_at == "",
                )
                .values(revoked_at=revoked_at, last_used_at=revoked_at)
            )
        return result.rowcount == 1

    def revoke_all_auth_sessions(self, user_id: str, workspace_id: str, revoked_at: str) -> int:
        with self.engine.begin() as connection:
            result = connection.execute(
                auth_sessions.update()
                .where(
                    auth_sessions.c.user_id == user_id,
                    auth_sessions.c.workspace_id == workspace_id,
                    auth_sessions.c.revoked_at == "",
                )
                .values(revoked_at=revoked_at, last_used_at=revoked_at)
            )
        return result.rowcount

    def save_auth_audit_event(self, event: AuthAuditEvent) -> None:
        values = {**asdict(event), "detail_json": json.loads(event.detail_json)}
        with self.engine.begin() as connection:
            connection.execute(auth_audit_events.insert().values(**values))

    def ensure_user_profile(self, user_id: str, workspace_id: str) -> UserProfile:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with self.engine.begin() as connection:
            self._insert_ignore(
                connection,
                user_profiles,
                {
                    "user_id": user_id,
                    "workspace_id": workspace_id,
                    "display_name": user_id,
                    "active_role": "viewer",
                    "personalization_enabled": 0,
                    "created_at": now,
                    "updated_at": now,
                },
                ["user_id", "workspace_id"],
            )
            row = (
                connection.execute(
                    select(user_profiles).where(
                        user_profiles.c.user_id == user_id,
                        user_profiles.c.workspace_id == workspace_id,
                    )
                )
                .mappings()
                .one()
            )
        payload = dict(row)
        payload["personalization_enabled"] = bool(payload["personalization_enabled"])
        return UserProfile(**payload)

    def save_user_profile(self, profile: UserProfile) -> None:
        values = asdict(profile)
        values["personalization_enabled"] = int(profile.personalization_enabled)
        with self.engine.begin() as connection:
            self._upsert(
                connection,
                user_profiles,
                values,
                ["user_id", "workspace_id"],
                [
                    "display_name",
                    "active_role",
                    "personalization_enabled",
                    "updated_at",
                ],
            )

    def list_role_grants(self, user_id: str, workspace_id: str) -> list[RoleGrant]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(role_grants)
                    .where(
                        role_grants.c.user_id == user_id,
                        role_grants.c.workspace_id == workspace_id,
                    )
                    .order_by(role_grants.c.created_at)
                )
                .mappings()
                .all()
            )
        return [
            RoleGrant(
                **{
                    **row,
                    "scope_json": json.dumps(row["scope_json"], ensure_ascii=False, sort_keys=True),
                }
            )
            for row in rows
        ]

    def save_role_grant(self, grant: RoleGrant) -> None:
        values = asdict(grant)
        values["scope_json"] = json.loads(grant.scope_json)
        with self.engine.begin() as connection:
            update_values = {
                "status": grant.status,
                "scope_json": values["scope_json"],
                "granted_by": grant.granted_by,
                "revoked_at": grant.revoked_at,
            }
            conflict_columns = [
                role_grants.c.user_id,
                role_grants.c.workspace_id,
                role_grants.c.role,
            ]
            if connection.dialect.name == "postgresql":
                connection.execute(
                    postgresql_insert(role_grants)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=conflict_columns,
                        set_=update_values,
                    )
                )
                return
            if connection.dialect.name == "sqlite":
                connection.execute(
                    sqlite_insert(role_grants)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=conflict_columns,
                        set_=update_values,
                    )
                )
                return
            existing_id = connection.scalar(
                select(role_grants.c.id).where(
                    role_grants.c.user_id == grant.user_id,
                    role_grants.c.workspace_id == grant.workspace_id,
                    role_grants.c.role == grant.role,
                )
            )
            if existing_id:
                connection.execute(
                    role_grants.update().where(role_grants.c.id == existing_id).values(**values)
                )
            else:
                connection.execute(role_grants.insert().values(**values))

    def get_role_application(self, application_id: str) -> RoleApplication | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(role_applications).where(role_applications.c.id == application_id)
                )
                .mappings()
                .first()
            )
        return RoleApplication(**row) if row else None

    def find_pending_role_application(
        self, user_id: str, workspace_id: str, role: str
    ) -> RoleApplication | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(role_applications)
                    .where(
                        role_applications.c.user_id == user_id,
                        role_applications.c.workspace_id == workspace_id,
                        role_applications.c.role == role,
                        role_applications.c.status == "pending",
                    )
                    .order_by(role_applications.c.created_at.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
        return RoleApplication(**row) if row else None

    def list_role_applications(self, user_id: str, workspace_id: str) -> list[RoleApplication]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(role_applications)
                    .where(
                        role_applications.c.user_id == user_id,
                        role_applications.c.workspace_id == workspace_id,
                    )
                    .order_by(role_applications.c.created_at.desc())
                )
                .mappings()
                .all()
            )
        return [RoleApplication(**row) for row in rows]

    def save_role_application(self, application: RoleApplication) -> None:
        values = asdict(application)
        with self.engine.begin() as connection:
            exists = connection.scalar(
                select(role_applications.c.id).where(role_applications.c.id == application.id)
            )
            if exists:
                connection.execute(
                    role_applications.update()
                    .where(role_applications.c.id == application.id)
                    .values(**values)
                )
            else:
                connection.execute(role_applications.insert().values(**values))

    def save_identity_task(self, task: IdentityTask) -> None:
        values = asdict(task)
        with self.engine.begin() as connection:
            exists = connection.scalar(
                select(identity_tasks.c.id).where(identity_tasks.c.id == task.id)
            )
            if exists:
                connection.execute(
                    identity_tasks.update().where(identity_tasks.c.id == task.id).values(**values)
                )
            else:
                connection.execute(identity_tasks.insert().values(**values))

    def list_identity_tasks(self, user_id: str, workspace_id: str) -> list[IdentityTask]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(identity_tasks)
                    .where(
                        identity_tasks.c.user_id == user_id,
                        identity_tasks.c.workspace_id == workspace_id,
                    )
                    .order_by(identity_tasks.c.status.desc(), identity_tasks.c.created_at.desc())
                )
                .mappings()
                .all()
            )
        return [IdentityTask(**row) for row in rows]

    def get_identity_task(
        self, task_id: str, user_id: str, workspace_id: str
    ) -> IdentityTask | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(identity_tasks).where(
                        identity_tasks.c.id == task_id,
                        identity_tasks.c.user_id == user_id,
                        identity_tasks.c.workspace_id == workspace_id,
                    )
                )
                .mappings()
                .first()
            )
        return IdentityTask(**row) if row else None

    def save_identity_audit_event(self, event: IdentityAuditEvent) -> None:
        values = asdict(event)
        values["detail_json"] = json.loads(event.detail_json)
        with self.engine.begin() as connection:
            connection.execute(identity_audit_events.insert().values(**values))

    def has_user_center_settings(self, user_id: str, workspace_id: str) -> bool:
        with self.engine.connect() as connection:
            return bool(connection.scalar(
                select(func.count()).select_from(user_center_settings).where(
                    user_center_settings.c.user_id == user_id,
                    user_center_settings.c.workspace_id == workspace_id,
                )
            ))

    def ensure_user_center_settings(self, user_id: str, workspace_id: str) -> UserCenterSettings:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with self.engine.begin() as connection:
            self._insert_ignore(
                connection,
                user_center_settings,
                {
                    "user_id": user_id,
                    "workspace_id": workspace_id,
                    "bio": "",
                    "region": "",
                    "profile_visibility": "private",
                    "history_enabled": 1,
                    "recommendation_enabled": 1,
                    "notification_enabled": 1,
                    "created_at": now,
                    "updated_at": now,
                },
                ["user_id", "workspace_id"],
            )
            row = (
                connection.execute(
                    select(user_center_settings).where(
                        user_center_settings.c.user_id == user_id,
                        user_center_settings.c.workspace_id == workspace_id,
                    )
                )
                .mappings()
                .one()
            )
        payload = dict(row)
        for key in ("history_enabled", "recommendation_enabled", "notification_enabled"):
            payload[key] = bool(payload[key])
        return UserCenterSettings(**payload)

    def save_user_center_settings(self, settings: UserCenterSettings) -> None:
        values = asdict(settings)
        for key in ("history_enabled", "recommendation_enabled", "notification_enabled"):
            values[key] = int(values[key])
        with self.engine.begin() as connection:
            self._upsert(
                connection,
                user_center_settings,
                values,
                ["user_id", "workspace_id"],
                [
                    "bio",
                    "region",
                    "profile_visibility",
                    "history_enabled",
                    "recommendation_enabled",
                    "notification_enabled",
                    "updated_at",
                ],
            )

    def list_library_items(self, user_id: str, workspace_id: str) -> list[LibraryItem]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(user_library_items)
                    .where(
                        user_library_items.c.user_id == user_id,
                        user_library_items.c.workspace_id == workspace_id,
                    )
                    .order_by(user_library_items.c.updated_at.desc())
                )
                .mappings()
                .all()
            )
        return [LibraryItem(**row) for row in rows]

    def save_library_item(self, item: LibraryItem) -> None:
        values = asdict(item)
        with self.engine.begin() as connection:
            existing = connection.scalar(
                select(user_library_items.c.id).where(
                    user_library_items.c.user_id == item.user_id,
                    user_library_items.c.workspace_id == item.workspace_id,
                    user_library_items.c.kind == item.kind,
                    user_library_items.c.target_id == item.target_id,
                )
            )
            query = (
                user_library_items.update().where(user_library_items.c.id == existing)
                if existing
                else user_library_items.insert()
            )
            connection.execute(query.values(**values))

    def delete_library_item(
        self, user_id: str, workspace_id: str, kind: str, target_id: str
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                user_library_items.delete().where(
                    user_library_items.c.user_id == user_id,
                    user_library_items.c.workspace_id == workspace_id,
                    user_library_items.c.kind == kind,
                    user_library_items.c.target_id == target_id,
                )
            )

    def list_user_follows(self, user_id: str, workspace_id: str) -> list[UserFollow]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(user_follows)
                    .where(
                        user_follows.c.user_id == user_id,
                        user_follows.c.workspace_id == workspace_id,
                    )
                    .order_by(user_follows.c.updated_at.desc())
                )
                .mappings()
                .all()
            )
        return [UserFollow(**row) for row in rows]

    def save_user_follow(self, follow: UserFollow) -> None:
        values = asdict(follow)
        with self.engine.begin() as connection:
            existing = connection.scalar(
                select(user_follows.c.id).where(
                    user_follows.c.user_id == follow.user_id,
                    user_follows.c.workspace_id == follow.workspace_id,
                    user_follows.c.target_id == follow.target_id,
                )
            )
            query = (
                user_follows.update().where(user_follows.c.id == existing)
                if existing
                else user_follows.insert()
            )
            connection.execute(query.values(**values))

    def delete_user_follow(self, user_id: str, workspace_id: str, target_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                user_follows.delete().where(
                    user_follows.c.user_id == user_id,
                    user_follows.c.workspace_id == workspace_id,
                    user_follows.c.target_id == target_id,
                )
            )

    def list_watch_history(self, user_id: str, workspace_id: str) -> list[WatchHistoryItem]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(user_watch_history)
                    .where(
                        user_watch_history.c.user_id == user_id,
                        user_watch_history.c.workspace_id == workspace_id,
                    )
                    .order_by(user_watch_history.c.viewed_at.desc())
                )
                .mappings()
                .all()
            )
        return [WatchHistoryItem(**{**row, "completed": bool(row["completed"])}) for row in rows]

    def save_watch_history(self, item: WatchHistoryItem) -> None:
        values = {**asdict(item), "completed": int(item.completed)}
        with self.engine.begin() as connection:
            existing = connection.scalar(
                select(user_watch_history.c.id).where(
                    user_watch_history.c.user_id == item.user_id,
                    user_watch_history.c.workspace_id == item.workspace_id,
                    user_watch_history.c.content_id == item.content_id,
                )
            )
            query = (
                user_watch_history.update().where(user_watch_history.c.id == existing)
                if existing
                else user_watch_history.insert()
            )
            connection.execute(query.values(**values))

    def delete_watch_history_item(self, user_id: str, workspace_id: str, content_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                user_watch_history.delete().where(
                    user_watch_history.c.user_id == user_id,
                    user_watch_history.c.workspace_id == workspace_id,
                    user_watch_history.c.content_id == content_id,
                )
            )

    def clear_watch_history(self, user_id: str, workspace_id: str) -> int:
        with self.engine.begin() as connection:
            result = connection.execute(
                user_watch_history.delete().where(
                    user_watch_history.c.user_id == user_id,
                    user_watch_history.c.workspace_id == workspace_id,
                )
            )
            return max(0, result.rowcount)

    def list_user_notifications(self, user_id: str, workspace_id: str) -> list[UserNotification]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(user_notifications)
                    .where(
                        user_notifications.c.user_id == user_id,
                        user_notifications.c.workspace_id == workspace_id,
                    )
                    .order_by(user_notifications.c.created_at.desc())
                )
                .mappings()
                .all()
            )
        return [UserNotification(**row) for row in rows]

    def get_user_notification(
        self, notification_id: str, user_id: str, workspace_id: str
    ) -> UserNotification | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(user_notifications).where(
                        user_notifications.c.id == notification_id,
                        user_notifications.c.user_id == user_id,
                        user_notifications.c.workspace_id == workspace_id,
                    )
                )
                .mappings()
                .first()
            )
        return UserNotification(**row) if row else None

    def save_user_notification(self, notification: UserNotification) -> None:
        values = asdict(notification)
        with self.engine.begin() as connection:
            self._upsert(
                connection,
                user_notifications,
                values,
                ["id"],
                [
                    "kind",
                    "title",
                    "body",
                    "target_href",
                    "read_at",
                ],
            )

    def delete_user_notification(
        self, notification_id: str, user_id: str, workspace_id: str
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                user_notifications.delete().where(
                    user_notifications.c.id == notification_id,
                    user_notifications.c.user_id == user_id,
                    user_notifications.c.workspace_id == workspace_id,
                )
            )

    def save_user_center_audit_event(self, event: UserCenterAuditEvent) -> None:
        values = {**asdict(event), "detail_json": json.loads(event.detail_json)}
        with self.engine.begin() as connection:
            connection.execute(user_center_audit_events.insert().values(**values))

    @staticmethod
    def _learning_id(prefix: str, *values: str) -> str:
        digest = hashlib.sha256(":".join(values).encode()).hexdigest()[:32]
        return f"{prefix}_{digest}"

    def ensure_learning_catalog(self, workspace_id: str) -> None:
        records = catalog_records(workspace_id)
        table_map = (
            ("sources", knowledge_sources, ["id", "workspace_id"]),
            ("paths", learning_paths, ["id", "workspace_id"]),
            ("units", learning_units, ["id", "workspace_id"]),
            ("quizzes", quizzes, ["id", "workspace_id"]),
            ("questions", quiz_questions, ["id", "workspace_id"]),
            ("achievements", achievement_definitions, ["id", "workspace_id"]),
        )
        with self.engine.begin() as connection:
            for key, table, conflicts in table_map:
                for item in records[key]:
                    values = asdict(item)
                    if isinstance(item, LearningUnit):
                        values["required"] = int(item.required)
                    if isinstance(item, QuizQuestion):
                        values["choices_json"] = json.loads(item.choices_json)
                    self._insert_ignore(connection, table, values, conflicts)

    def ensure_learning_profile(self, user_id: str, workspace_id: str) -> LearningProfile:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with self.engine.begin() as connection:
            self._insert_ignore(
                connection,
                learning_profiles,
                {
                    "user_id": user_id,
                    "workspace_id": workspace_id,
                    "timezone": "Asia/Shanghai",
                    "current_streak": 0,
                    "longest_streak": 0,
                    "last_learning_date": "",
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
                ["user_id", "workspace_id"],
            )
            row = connection.execute(
                select(learning_profiles).where(
                    learning_profiles.c.user_id == user_id,
                    learning_profiles.c.workspace_id == workspace_id,
                )
            ).mappings().one()
        return LearningProfile(**row)

    def get_learning_profile(self, user_id: str, workspace_id: str) -> LearningProfile | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(learning_profiles).where(
                    learning_profiles.c.user_id == user_id,
                    learning_profiles.c.workspace_id == workspace_id,
                )
            ).mappings().first()
        return LearningProfile(**row) if row else None

    def list_learning_paths(self, workspace_id: str) -> list[LearningPath]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(learning_paths)
                .where(learning_paths.c.workspace_id == workspace_id)
                .order_by(learning_paths.c.created_at, learning_paths.c.id)
            ).mappings().all()
        return [LearningPath(**row) for row in rows]

    def get_learning_path(self, path_id: str, workspace_id: str) -> LearningPath | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(learning_paths).where(
                    learning_paths.c.id == path_id,
                    learning_paths.c.workspace_id == workspace_id,
                )
            ).mappings().first()
        return LearningPath(**row) if row else None

    def list_learning_units(self, path_id: str, workspace_id: str) -> list[LearningUnit]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(learning_units)
                .where(
                    learning_units.c.path_id == path_id,
                    learning_units.c.workspace_id == workspace_id,
                )
                .order_by(learning_units.c.position)
            ).mappings().all()
        return [LearningUnit(**{**row, "required": bool(row["required"])}) for row in rows]

    def get_learning_unit(self, unit_id: str, workspace_id: str) -> LearningUnit | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(learning_units).where(
                    learning_units.c.id == unit_id,
                    learning_units.c.workspace_id == workspace_id,
                )
            ).mappings().first()
        return LearningUnit(**{**row, "required": bool(row["required"])}) if row else None

    def list_knowledge_sources(self, workspace_id: str) -> list[KnowledgeSource]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(knowledge_sources)
                .where(knowledge_sources.c.workspace_id == workspace_id)
                .order_by(knowledge_sources.c.title)
            ).mappings().all()
        return [KnowledgeSource(**row) for row in rows]

    def get_knowledge_source(self, source_id: str, workspace_id: str) -> KnowledgeSource | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(knowledge_sources).where(
                    knowledge_sources.c.id == source_id,
                    knowledge_sources.c.workspace_id == workspace_id,
                )
            ).mappings().first()
        return KnowledgeSource(**row) if row else None

    def list_path_enrollments(self, user_id: str, workspace_id: str) -> list[PathEnrollment]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(learning_path_enrollments)
                .where(
                    learning_path_enrollments.c.user_id == user_id,
                    learning_path_enrollments.c.workspace_id == workspace_id,
                )
                .order_by(learning_path_enrollments.c.updated_at.desc())
            ).mappings().all()
        return [PathEnrollment(**row) for row in rows]

    def get_path_enrollment(self, user_id: str, workspace_id: str, path_id: str) -> PathEnrollment | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(learning_path_enrollments).where(
                    learning_path_enrollments.c.user_id == user_id,
                    learning_path_enrollments.c.workspace_id == workspace_id,
                    learning_path_enrollments.c.path_id == path_id,
                )
            ).mappings().first()
        return PathEnrollment(**row) if row else None

    def list_learning_progress(self, user_id: str, workspace_id: str) -> list[LearningProgress]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(learning_progress)
                .where(
                    learning_progress.c.user_id == user_id,
                    learning_progress.c.workspace_id == workspace_id,
                )
                .order_by(learning_progress.c.updated_at.desc())
            ).mappings().all()
        return [LearningProgress(**row) for row in rows]

    def get_learning_progress(self, user_id: str, workspace_id: str, unit_id: str) -> LearningProgress | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(learning_progress).where(
                    learning_progress.c.user_id == user_id,
                    learning_progress.c.workspace_id == workspace_id,
                    learning_progress.c.unit_id == unit_id,
                )
            ).mappings().first()
        return LearningProgress(**row) if row else None

    def list_knowledge_cards(self, user_id: str, workspace_id: str) -> list[KnowledgeCard]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(knowledge_cards)
                .where(
                    knowledge_cards.c.user_id == user_id,
                    knowledge_cards.c.workspace_id == workspace_id,
                )
                .order_by(knowledge_cards.c.updated_at.desc())
            ).mappings().all()
        return [KnowledgeCard(**row) for row in rows]

    def get_knowledge_card(self, user_id: str, workspace_id: str, unit_id: str) -> KnowledgeCard | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(knowledge_cards).where(
                    knowledge_cards.c.user_id == user_id,
                    knowledge_cards.c.workspace_id == workspace_id,
                    knowledge_cards.c.unit_id == unit_id,
                )
            ).mappings().first()
        return KnowledgeCard(**row) if row else None

    def get_quiz(self, quiz_id: str, workspace_id: str) -> Quiz | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(quizzes).where(
                    quizzes.c.id == quiz_id,
                    quizzes.c.workspace_id == workspace_id,
                )
            ).mappings().first()
        return Quiz(**row) if row else None

    def get_quiz_for_unit(self, unit_id: str, workspace_id: str) -> Quiz | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(quizzes).where(
                    quizzes.c.unit_id == unit_id,
                    quizzes.c.workspace_id == workspace_id,
                )
            ).mappings().first()
        return Quiz(**row) if row else None

    def list_quiz_questions(self, quiz_id: str, workspace_id: str) -> list[QuizQuestion]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(quiz_questions)
                .where(
                    quiz_questions.c.quiz_id == quiz_id,
                    quiz_questions.c.workspace_id == workspace_id,
                )
                .order_by(quiz_questions.c.position)
            ).mappings().all()
        return [
            QuizQuestion(
                **{
                    **row,
                    "choices_json": json.dumps(
                        row["choices_json"], ensure_ascii=False
                    ),
                }
            )
            for row in rows
        ]

    def list_quiz_attempts(self, user_id: str, workspace_id: str) -> list[QuizAttempt]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(quiz_attempts)
                .where(
                    quiz_attempts.c.user_id == user_id,
                    quiz_attempts.c.workspace_id == workspace_id,
                )
                .order_by(quiz_attempts.c.created_at.desc())
            ).mappings().all()
        return [
            QuizAttempt(
                **{
                    **row,
                    "answers_json": json.dumps(row["answers_json"], ensure_ascii=False, sort_keys=True),
                    "question_snapshot_json": json.dumps(row["question_snapshot_json"], ensure_ascii=False, sort_keys=True),
                    "passed": bool(row["passed"]),
                }
            )
            for row in rows
        ]

    def list_learning_events(self, user_id: str, workspace_id: str) -> list[LearningEvent]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(learning_events)
                .where(
                    learning_events.c.user_id == user_id,
                    learning_events.c.workspace_id == workspace_id,
                )
                .order_by(learning_events.c.created_at.desc())
            ).mappings().all()
        return [
            LearningEvent(
                **{
                    **row,
                    "payload_json": json.dumps(row["payload_json"], ensure_ascii=False, sort_keys=True),
                }
            )
            for row in rows
        ]

    def find_learning_event(self, user_id: str, workspace_id: str, idempotency_key: str) -> LearningEvent | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(learning_events).where(
                    learning_events.c.user_id == user_id,
                    learning_events.c.workspace_id == workspace_id,
                    learning_events.c.idempotency_key == idempotency_key,
                )
            ).mappings().first()
        return LearningEvent(**{**row, "payload_json": json.dumps(row["payload_json"], ensure_ascii=False, sort_keys=True)}) if row else None

    @classmethod
    def _ensure_daily_tasks_connection(
        cls, connection: Any, user_id: str, workspace_id: str, task_date: str
    ) -> None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        templates = (
            ("complete_unit", "完成一个学习节点", "unit.completed"),
            ("save_card", "保存一张知识卡", "knowledge_card.saved"),
            ("pass_quiz", "通过一次测验", "quiz.passed"),
        )
        for kind, title, event_type in templates:
            cls._insert_ignore(
                connection,
                daily_tasks,
                {
                    "id": cls._learning_id("daily", user_id, workspace_id, task_date, kind),
                    "user_id": user_id,
                    "workspace_id": workspace_id,
                    "task_date": task_date,
                    "kind": kind,
                    "title": title,
                    "event_type": event_type,
                    "target_count": 1,
                    "current_count": 0,
                    "status": "open",
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
                ["user_id", "workspace_id", "task_date", "kind"],
            )

    def ensure_daily_tasks(self, user_id: str, workspace_id: str, task_date: str) -> None:
        with self.engine.begin() as connection:
            self._ensure_daily_tasks_connection(connection, user_id, workspace_id, task_date)

    def list_daily_tasks(self, user_id: str, workspace_id: str, task_date: str) -> list[DailyTask]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(daily_tasks)
                .where(
                    daily_tasks.c.user_id == user_id,
                    daily_tasks.c.workspace_id == workspace_id,
                    daily_tasks.c.task_date == task_date,
                )
                .order_by(daily_tasks.c.kind)
            ).mappings().all()
        return [DailyTask(**row) for row in rows]

    def list_achievement_definitions(self, workspace_id: str) -> list[AchievementDefinition]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(achievement_definitions)
                .where(
                    achievement_definitions.c.workspace_id == workspace_id,
                    achievement_definitions.c.status == "active",
                )
                .order_by(achievement_definitions.c.code)
            ).mappings().all()
        return [AchievementDefinition(**row) for row in rows]

    def list_achievement_grants(self, user_id: str, workspace_id: str) -> list[AchievementGrant]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(achievement_grants)
                .where(
                    achievement_grants.c.user_id == user_id,
                    achievement_grants.c.workspace_id == workspace_id,
                )
                .order_by(achievement_grants.c.granted_at.desc())
            ).mappings().all()
        return [AchievementGrant(**row) for row in rows]

    def list_tutor_interactions(self, user_id: str, workspace_id: str) -> list[TutorInteraction]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(tutor_interactions)
                .where(
                    tutor_interactions.c.user_id == user_id,
                    tutor_interactions.c.workspace_id == workspace_id,
                )
                .order_by(tutor_interactions.c.created_at.desc())
                .limit(20)
            ).mappings().all()
        return [
            TutorInteraction(
                **{
                    **row,
                    "citations_json": json.dumps(
                        row["citations_json"], ensure_ascii=False, sort_keys=True
                    ),
                }
            )
            for row in rows
        ]

    def find_tutor_interaction(
        self, user_id: str, workspace_id: str, idempotency_key: str
    ) -> TutorInteraction | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(tutor_interactions).where(
                    tutor_interactions.c.user_id == user_id,
                    tutor_interactions.c.workspace_id == workspace_id,
                    tutor_interactions.c.idempotency_key == idempotency_key,
                )
            ).mappings().first()
        return (
            TutorInteraction(
                **{
                    **row,
                    "citations_json": json.dumps(
                        row["citations_json"], ensure_ascii=False, sort_keys=True
                    ),
                }
            )
            if row
            else None
        )

    def create_tutor_interaction(self, interaction: TutorInteraction) -> bool:
        values = {
            **asdict(interaction),
            "citations_json": json.loads(interaction.citations_json),
        }
        with self.engine.begin() as connection:
            return self._insert_ignore_created(
                connection,
                tutor_interactions,
                values,
                ["user_id", "workspace_id", "idempotency_key"],
            )

    def update_tutor_interaction(
        self, interaction: TutorInteraction, expected_status: str
    ) -> bool:
        values = {
            **asdict(interaction),
            "citations_json": json.loads(interaction.citations_json),
        }
        with self.engine.begin() as connection:
            result = connection.execute(
                tutor_interactions.update()
                .where(
                    tutor_interactions.c.id == interaction.id,
                    tutor_interactions.c.user_id == interaction.user_id,
                    tutor_interactions.c.workspace_id == interaction.workspace_id,
                    tutor_interactions.c.status == expected_status,
                )
                .values(**values)
            )
        return result.rowcount == 1

    def count_tutor_interactions_since(
        self, user_id: str, workspace_id: str, created_after: str
    ) -> int:
        with self.engine.connect() as connection:
            total = connection.scalar(
                select(func.count()).select_from(tutor_interactions).where(
                    tutor_interactions.c.user_id == user_id,
                    tutor_interactions.c.workspace_id == workspace_id,
                    tutor_interactions.c.created_at >= created_after,
                )
            )
        return int(total or 0)

    def commit_learning_activity(self, activity: LearningActivityCommit) -> bool:
        event = activity.event
        event_values = {**asdict(event), "payload_json": json.loads(event.payload_json)}
        with self.engine.begin() as connection:
            if not self._insert_ignore_created(
                connection,
                learning_events,
                event_values,
                ["user_id", "workspace_id", "idempotency_key"],
            ):
                return False
            if activity.enrollment:
                self._insert_ignore(
                    connection,
                    learning_path_enrollments,
                    asdict(activity.enrollment),
                    ["user_id", "workspace_id", "path_id"],
                )
            if activity.progress:
                progress = activity.progress
                expected = activity.expected_progress_version
                if expected == 0:
                    created = self._insert_ignore_created(
                        connection,
                        learning_progress,
                        asdict(progress),
                        ["user_id", "workspace_id", "unit_id"],
                    )
                    if not created:
                        raise LearningConflictError("学习进度版本已变化，请刷新后重试")
                else:
                    result = connection.execute(
                        learning_progress.update()
                        .where(
                            learning_progress.c.user_id == progress.user_id,
                            learning_progress.c.workspace_id == progress.workspace_id,
                            learning_progress.c.unit_id == progress.unit_id,
                            learning_progress.c.version == expected,
                        )
                        .values(**asdict(progress))
                    )
                    if result.rowcount != 1:
                        raise LearningConflictError("学习进度版本已变化，请刷新后重试")
            if activity.card:
                card = activity.card
                expected = activity.expected_card_version
                if expected == 0:
                    created = self._insert_ignore_created(
                        connection,
                        knowledge_cards,
                        asdict(card),
                        ["user_id", "workspace_id", "unit_id"],
                    )
                    if not created:
                        raise LearningConflictError("知识卡版本已变化，请刷新后重试")
                else:
                    result = connection.execute(
                        knowledge_cards.update()
                        .where(
                            knowledge_cards.c.user_id == card.user_id,
                            knowledge_cards.c.workspace_id == card.workspace_id,
                            knowledge_cards.c.unit_id == card.unit_id,
                            knowledge_cards.c.version == expected,
                        )
                        .values(**asdict(card))
                    )
                    if result.rowcount != 1:
                        raise LearningConflictError("知识卡版本已变化，请刷新后重试")
            if activity.attempt:
                values = asdict(activity.attempt)
                values["answers_json"] = json.loads(activity.attempt.answers_json)
                values["question_snapshot_json"] = json.loads(activity.attempt.question_snapshot_json)
                values["passed"] = int(activity.attempt.passed)
                connection.execute(quiz_attempts.insert().values(**values))
            if event.event_type in {"unit.completed", "knowledge_card.saved", "quiz.passed"}:
                profile = connection.execute(
                    select(learning_profiles)
                    .where(
                        learning_profiles.c.user_id == event.user_id,
                        learning_profiles.c.workspace_id == event.workspace_id,
                    )
                    .with_for_update()
                ).mappings().one()
                current_streak = profile["current_streak"]
                if profile["last_learning_date"] != event.activity_date:
                    previous = (
                        datetime.fromisoformat(event.activity_date).date() - timedelta(days=1)
                    ).isoformat()
                    current_streak = current_streak + 1 if profile["last_learning_date"] == previous else 1
                connection.execute(
                    learning_profiles.update()
                    .where(
                        learning_profiles.c.user_id == event.user_id,
                        learning_profiles.c.workspace_id == event.workspace_id,
                    )
                    .values(
                        current_streak=current_streak,
                        longest_streak=max(profile["longest_streak"], current_streak),
                        last_learning_date=event.activity_date,
                        version=profile["version"] + 1,
                        updated_at=event.created_at,
                    )
                )
                self._ensure_daily_tasks_connection(
                    connection, event.user_id, event.workspace_id, event.activity_date
                )
                count = connection.scalar(
                    select(func.count()).select_from(learning_events).where(
                        learning_events.c.user_id == event.user_id,
                        learning_events.c.workspace_id == event.workspace_id,
                        learning_events.c.activity_date == event.activity_date,
                        learning_events.c.event_type == event.event_type,
                    )
                )
                task = connection.execute(
                    select(daily_tasks).where(
                        daily_tasks.c.user_id == event.user_id,
                        daily_tasks.c.workspace_id == event.workspace_id,
                        daily_tasks.c.task_date == event.activity_date,
                        daily_tasks.c.event_type == event.event_type,
                    )
                ).mappings().one()
                connection.execute(
                    daily_tasks.update()
                    .where(daily_tasks.c.id == task["id"])
                    .values(
                        current_count=min(task["target_count"], count),
                        status="completed" if count >= task["target_count"] else "open",
                        version=task["version"] + 1,
                        updated_at=event.created_at,
                    )
                )
                definitions = connection.execute(
                    select(achievement_definitions).where(
                        achievement_definitions.c.workspace_id == event.workspace_id,
                        achievement_definitions.c.event_type == event.event_type,
                        achievement_definitions.c.status == "active",
                    )
                ).mappings().all()
                total = connection.scalar(
                    select(func.count()).select_from(learning_events).where(
                        learning_events.c.user_id == event.user_id,
                        learning_events.c.workspace_id == event.workspace_id,
                        learning_events.c.event_type == event.event_type,
                    )
                )
                for definition in definitions:
                    if total >= definition["threshold"]:
                        self._insert_ignore(
                            connection,
                            achievement_grants,
                            {
                                "id": self._learning_id("grant", event.user_id, event.workspace_id, definition["id"]),
                                "user_id": event.user_id,
                                "workspace_id": event.workspace_id,
                                "definition_id": definition["id"],
                                "definition_version": definition["version"],
                                "triggering_event_id": event.id,
                                "granted_at": event.created_at,
                            },
                            ["user_id", "workspace_id", "definition_id"],
                        )
            if activity.refresh_path_id:
                required = connection.scalar(
                    select(func.count()).select_from(learning_units).where(
                        learning_units.c.path_id == activity.refresh_path_id,
                        learning_units.c.workspace_id == event.workspace_id,
                        learning_units.c.required == 1,
                    )
                )
                completed = connection.scalar(
                    select(func.count())
                    .select_from(
                        learning_progress.join(
                            learning_units,
                            (learning_units.c.id == learning_progress.c.unit_id)
                            & (learning_units.c.workspace_id == learning_progress.c.workspace_id),
                        )
                    )
                    .where(
                        learning_progress.c.user_id == event.user_id,
                        learning_progress.c.workspace_id == event.workspace_id,
                        learning_progress.c.path_id == activity.refresh_path_id,
                        learning_progress.c.status == "completed",
                        learning_units.c.required == 1,
                    )
                )
                if required and completed >= required:
                    enrollment = connection.execute(
                        select(learning_path_enrollments).where(
                            learning_path_enrollments.c.user_id == event.user_id,
                            learning_path_enrollments.c.workspace_id == event.workspace_id,
                            learning_path_enrollments.c.path_id == activity.refresh_path_id,
                        )
                    ).mappings().one()
                    if enrollment["status"] != "completed":
                        connection.execute(
                            learning_path_enrollments.update()
                            .where(learning_path_enrollments.c.id == enrollment["id"])
                            .values(
                                status="completed",
                                version=enrollment["version"] + 1,
                                completed_at=event.created_at,
                                updated_at=event.created_at,
                            )
                        )
        return True

    def get_learning_growth_summary(self, user_id: str, workspace_id: str) -> dict[str, object]:
        profile = self.get_learning_profile(user_id, workspace_id)
        if not profile:
            return {
                "learning_paths": 0, "completed_paths": 0, "completed_units": 0,
                "knowledge_cards": 0, "quiz_attempts": 0, "passed_quizzes": 0,
                "achievements": 0, "achievement_points": 0, "current_streak": 0,
                "longest_streak": 0, "last_learning_date": "",
            }
        enrollments = self.list_path_enrollments(user_id, workspace_id)
        progress = self.list_learning_progress(user_id, workspace_id)
        cards = self.list_knowledge_cards(user_id, workspace_id)
        attempts = self.list_quiz_attempts(user_id, workspace_id)
        grants = self.list_achievement_grants(user_id, workspace_id)
        definitions = {item.id: item for item in self.list_achievement_definitions(workspace_id)}
        return {
            "learning_paths": len(enrollments),
            "completed_paths": sum(item.status == "completed" for item in enrollments),
            "completed_units": sum(item.status == "completed" for item in progress),
            "knowledge_cards": len(cards),
            "quiz_attempts": len(attempts),
            "passed_quizzes": sum(item.passed for item in attempts),
            "achievements": len(grants),
            "achievement_points": sum(
                definitions[item.definition_id].points
                for item in grants
                if item.definition_id in definitions
            ),
            "current_streak": profile.current_streak,
            "longest_streak": profile.longest_streak,
            "last_learning_date": profile.last_learning_date,
        }

    def get_project(self, project_id: str) -> Project | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(select(projects).where(projects.c.id == project_id))
                .mappings()
                .first()
            )
        return Project(**row) if row else None

    def list_projects(self, workspace_id: str, *, limit: int = 20) -> list[Project]:
        safe_limit = max(1, min(limit, 100))
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(projects)
                    .where(projects.c.workspace_id == workspace_id)
                    .order_by(projects.c.updated_at.desc(), projects.c.id.desc())
                    .limit(safe_limit)
                )
                .mappings()
                .all()
            )
        return [Project(**row) for row in rows]

    def next_brief_version(self, project_id: str) -> int:
        with self.engine.connect() as connection:
            value = connection.scalar(
                select(func.coalesce(func.max(brief_versions.c.version), 0) + 1).where(
                    brief_versions.c.project_id == project_id
                )
            )
        return int(value or 1)

    def save_brief(self, brief: BriefVersion) -> None:
        payload = {
            "craft": brief.craft,
            "story_seed": brief.story_seed,
            "audience": brief.audience,
            "platform": brief.platform,
            "tone": brief.tone,
            "goal": brief.goal,
            "duration": brief.duration,
            "aspect_ratio": brief.aspect_ratio,
            "asset_context": brief.asset_context,
        }
        with self.engine.begin() as connection:
            connection.execute(
                brief_versions.insert().values(
                    id=brief.id,
                    project_id=brief.project_id,
                    version=brief.version,
                    payload_json=payload,
                    created_at=brief.created_at,
                )
            )

    def get_brief(self, brief_id: str) -> BriefVersion | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(select(brief_versions).where(brief_versions.c.id == brief_id))
                .mappings()
                .first()
            )
        if not row:
            return None
        return BriefVersion(
            id=row["id"],
            project_id=row["project_id"],
            version=row["version"],
            created_at=row["created_at"],
            **row["payload_json"],
        )

    def save_run(self, run: Run) -> None:
        values = {
            "id": run.id,
            "workspace_id": run.workspace_id,
            "project_id": run.project_id,
            "brief_version_id": run.brief_version_id,
            "status": run.status.value,
            "model_preference": run.model_preference,
            "idempotency_key": run.idempotency_key,
            "request_fingerprint": run.request_fingerprint,
            "attempt": run.attempt,
            "error_code": run.error_code,
            "error_message": run.error_message,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "claimed_by": run.claimed_by,
            "claimed_at": run.claimed_at,
            "lease_until": run.lease_until,
            "heartbeat_at": run.heartbeat_at,
            "lock_version": run.lock_version,
        }
        try:
            with self.engine.begin() as connection:
                exists = connection.scalar(select(runs.c.id).where(runs.c.id == run.id))
                if exists:
                    statement = runs.update().where(runs.c.id == run.id)
                    if run.status is not RunStatus.CANCELLED:
                        statement = statement.where(runs.c.status != RunStatus.CANCELLED.value)
                    connection.execute(
                        statement.values(
                            status=run.status.value,
                            attempt=run.attempt,
                            error_code=run.error_code,
                            error_message=run.error_message,
                            updated_at=run.updated_at,
                            claimed_by=run.claimed_by,
                            claimed_at=run.claimed_at,
                            lease_until=run.lease_until,
                            heartbeat_at=run.heartbeat_at,
                            lock_version=run.lock_version,
                        )
                    )
                else:
                    connection.execute(runs.insert().values(**values))
        except IntegrityError as exc:
            raise RepositoryConflictError("run uniqueness conflict") from exc

    @staticmethod
    def _to_run(row: Any) -> Run | None:
        if not row:
            return None
        data = dict(row)
        data["status"] = RunStatus(data["status"])
        return Run(**data)

    def get_run(self, run_id: str) -> Run | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
        return self._to_run(row)

    def cancel_run(self, run_id: str) -> Run | None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        cancellable = [
            status.value
            for status in RunStatus
            if status not in {RunStatus.PASSED, RunStatus.FAILED, RunStatus.CANCELLED}
        ]
        with self.engine.begin() as connection:
            result = connection.execute(
                runs.update()
                .where(runs.c.id == run_id, runs.c.status.in_(cancellable))
                .values(
                    status=RunStatus.CANCELLED.value,
                    error_code="",
                    error_message="",
                    claimed_by="",
                    claimed_at="",
                    lease_until="",
                    heartbeat_at="",
                    updated_at=now,
                    lock_version=runs.c.lock_version + 1,
                )
            )
        return self.get_run(run_id) if result.rowcount == 1 else None

    def find_run_by_idempotency_key(
        self, workspace_id: str, project_id: str, key: str
    ) -> Run | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(runs).where(
                        runs.c.workspace_id == workspace_id,
                        runs.c.project_id == project_id,
                        runs.c.idempotency_key == key,
                    )
                )
                .mappings()
                .first()
            )
        return self._to_run(row)

    def next_script_version(self, project_id: str) -> int:
        with self.engine.connect() as connection:
            value = connection.scalar(
                select(func.coalesce(func.max(script_versions.c.version), 0) + 1).where(
                    script_versions.c.project_id == project_id
                )
            )
        return int(value or 1)

    def save_script(self, script: ScriptVersion) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                script_versions.insert().values(
                    id=script.id,
                    project_id=script.project_id,
                    run_id=script.run_id,
                    brief_version_id=script.brief_version_id,
                    version=script.version,
                    payload_json=script.payload,
                    evidence_json=script.evidence,
                    created_at=script.created_at,
                )
            )

    def get_script_for_run(self, run_id: str) -> ScriptVersion | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(script_versions).where(script_versions.c.run_id == run_id)
                )
                .mappings()
                .first()
            )
        if not row:
            return None
        return ScriptVersion(
            id=row["id"],
            project_id=row["project_id"],
            run_id=row["run_id"],
            brief_version_id=row["brief_version_id"],
            version=row["version"],
            payload=row["payload_json"],
            evidence=row["evidence_json"],
            created_at=row["created_at"],
        )

    def complete_run_with_script(self, run: Run, script: ScriptVersion) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                script_versions.insert().values(
                    id=script.id,
                    project_id=script.project_id,
                    run_id=script.run_id,
                    brief_version_id=script.brief_version_id,
                    version=script.version,
                    payload_json=script.payload,
                    evidence_json=script.evidence,
                    created_at=script.created_at,
                )
            )
            result = connection.execute(
                runs.update()
                .where(
                    runs.c.id == run.id,
                    runs.c.status != RunStatus.CANCELLED.value,
                )
                .values(
                    status=run.status.value,
                    attempt=run.attempt,
                    error_code=run.error_code,
                    error_message=run.error_message,
                    updated_at=run.updated_at,
                    lease_until="",
                    lock_version=runs.c.lock_version + 1,
                )
            )
            if result.rowcount != 1:
                raise RepositoryConflictError("cancelled run cannot be completed")

    def claim_run(self, run_id: str, worker_id: str, lease_seconds: int = 120) -> Run | None:
        now = datetime.now(UTC)
        now_text = now.isoformat(timespec="milliseconds")
        lease_text = (now + timedelta(seconds=lease_seconds)).isoformat(timespec="milliseconds")
        reclaimable = or_(
            runs.c.status.in_([RunStatus.PENDING.value, RunStatus.RETRYING.value]),
            (
                runs.c.status.in_(
                    [
                        RunStatus.CLAIMED.value,
                        RunStatus.RUNNING.value,
                        RunStatus.RETRIEVING.value,
                        RunStatus.GENERATING.value,
                        RunStatus.VALIDATING.value,
                    ]
                )
                & (runs.c.lease_until != "")
                & (runs.c.lease_until < now_text)
            ),
        )
        with self.engine.begin() as connection:
            result = connection.execute(
                runs.update()
                .where(runs.c.id == run_id, reclaimable)
                .values(
                    status=RunStatus.CLAIMED.value,
                    claimed_by=worker_id,
                    claimed_at=now_text,
                    lease_until=lease_text,
                    heartbeat_at=now_text,
                    updated_at=now_text,
                    lock_version=runs.c.lock_version + 1,
                )
            )
        return self.get_run(run_id) if result.rowcount == 1 else None

    def heartbeat_run(self, run_id: str, worker_id: str, lease_seconds: int = 120) -> bool:
        now = datetime.now(UTC)
        now_text = now.isoformat(timespec="milliseconds")
        lease_text = (now + timedelta(seconds=lease_seconds)).isoformat(timespec="milliseconds")
        with self.engine.begin() as connection:
            result = connection.execute(
                runs.update()
                .where(
                    runs.c.id == run_id,
                    runs.c.claimed_by == worker_id,
                    runs.c.status.not_in(
                        [
                            RunStatus.PASSED.value,
                            RunStatus.FAILED.value,
                            RunStatus.CANCELLED.value,
                        ]
                    ),
                )
                .values(
                    heartbeat_at=now_text,
                    lease_until=lease_text,
                    updated_at=now_text,
                    lock_version=runs.c.lock_version + 1,
                )
            )
        return result.rowcount == 1

    def record_failed_job(self, run_id: str, reason: str) -> None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        try:
            with self.engine.begin() as connection:
                result = connection.execute(
                    failed_jobs.update()
                    .where(failed_jobs.c.run_id == run_id)
                    .values(reason=reason[:4000], created_at=now, resolved_at="")
                )
                if result.rowcount == 0:
                    connection.execute(
                        failed_jobs.insert().values(
                            id=f"failed_{uuid4().hex}",
                            run_id=run_id,
                            reason=reason[:4000],
                            created_at=now,
                            resolved_at="",
                        )
                    )
        except IntegrityError:
            with self.engine.begin() as connection:
                connection.execute(
                    failed_jobs.update()
                    .where(failed_jobs.c.run_id == run_id)
                    .values(reason=reason[:4000], created_at=now, resolved_at="")
                )

    @staticmethod
    def _to_failed_job(row: Any) -> FailedJob | None:
        return FailedJob(**dict(row)) if row else None

    def list_failed_jobs(
        self, workspace_id: str, *, include_resolved: bool = False, limit: int = 100
    ) -> list[FailedJob]:
        statement = (
            select(failed_jobs)
            .join(runs, runs.c.id == failed_jobs.c.run_id)
            .where(runs.c.workspace_id == workspace_id)
            .order_by(failed_jobs.c.created_at.desc(), failed_jobs.c.id.desc())
            .limit(limit)
        )
        if not include_resolved:
            statement = statement.where(failed_jobs.c.resolved_at == "")
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [FailedJob(**dict(row)) for row in rows]

    def get_failed_job(self, failed_job_id: str, workspace_id: str) -> FailedJob | None:
        statement = (
            select(failed_jobs)
            .join(runs, runs.c.id == failed_jobs.c.run_id)
            .where(
                failed_jobs.c.id == failed_job_id,
                runs.c.workspace_id == workspace_id,
            )
        )
        with self.engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return self._to_failed_job(row)

    def retry_failed_job(
        self, failed_job_id: str, workspace_id: str, *, max_attempts: int
    ) -> Run | None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(failed_jobs.c.run_id)
                    .join(runs, runs.c.id == failed_jobs.c.run_id)
                    .where(
                        failed_jobs.c.id == failed_job_id,
                        runs.c.workspace_id == workspace_id,
                        failed_jobs.c.resolved_at == "",
                        runs.c.status == RunStatus.FAILED.value,
                        runs.c.attempt < max_attempts,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            run_id = str(row["run_id"])
            run_update = connection.execute(
                runs.update()
                .where(
                    runs.c.id == run_id,
                    runs.c.workspace_id == workspace_id,
                    runs.c.status == RunStatus.FAILED.value,
                    runs.c.attempt < max_attempts,
                )
                .values(
                    status=RunStatus.RETRYING.value,
                    attempt=runs.c.attempt + 1,
                    error_code="",
                    error_message="",
                    claimed_by="",
                    claimed_at="",
                    lease_until="",
                    heartbeat_at="",
                    updated_at=now,
                    lock_version=runs.c.lock_version + 1,
                )
            )
            job_update = connection.execute(
                failed_jobs.update()
                .where(
                    failed_jobs.c.id == failed_job_id,
                    failed_jobs.c.resolved_at == "",
                )
                .values(resolved_at=now)
            )
            if run_update.rowcount != 1 or job_update.rowcount != 1:
                raise RepositoryConflictError("failed job retry conflict")
        return self.get_run(run_id)

    def resolve_failed_job(self, failed_job_id: str, workspace_id: str) -> FailedJob | None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(failed_jobs.c.resolved_at)
                    .join(runs, runs.c.id == failed_jobs.c.run_id)
                    .where(
                        failed_jobs.c.id == failed_job_id,
                        runs.c.workspace_id == workspace_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            if not row["resolved_at"]:
                connection.execute(
                    failed_jobs.update()
                    .where(failed_jobs.c.id == failed_job_id)
                    .values(resolved_at=now)
                )
        return self.get_failed_job(failed_job_id, workspace_id)

    def reconcile_expired_runs(
        self, *, max_attempts: int, limit: int = 100
    ) -> tuple[list[str], list[str]]:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        active = [
            RunStatus.CLAIMED.value,
            RunStatus.RUNNING.value,
            RunStatus.RETRIEVING.value,
            RunStatus.GENERATING.value,
            RunStatus.VALIDATING.value,
        ]
        requeued: list[str] = []
        failed: list[str] = []
        with self.engine.begin() as connection:
            statement = (
                select(runs.c.id, runs.c.attempt)
                .where(
                    runs.c.status.in_(active),
                    runs.c.lease_until != "",
                    runs.c.lease_until < now,
                )
                .order_by(runs.c.lease_until)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            rows = connection.execute(statement).mappings().all()
            for row in rows:
                if int(row["attempt"]) >= max_attempts:
                    connection.execute(
                        runs.update()
                        .where(runs.c.id == row["id"])
                        .values(
                            status=RunStatus.FAILED.value,
                            error_code="lease_exhausted",
                            error_message="运行租约过期且已达到最大尝试次数",
                            lease_until="",
                            updated_at=now,
                            lock_version=runs.c.lock_version + 1,
                        )
                    )
                    connection.execute(
                        failed_jobs.insert().values(
                            id=f"failed_{uuid4().hex}",
                            run_id=row["id"],
                            reason="lease_exhausted",
                            created_at=now,
                            resolved_at="",
                        )
                    )
                    failed.append(str(row["id"]))
                else:
                    connection.execute(
                        runs.update()
                        .where(runs.c.id == row["id"])
                        .values(
                            status=RunStatus.RETRYING.value,
                            attempt=runs.c.attempt + 1,
                            claimed_by="",
                            claimed_at="",
                            lease_until="",
                            heartbeat_at="",
                            updated_at=now,
                            lock_version=runs.c.lock_version + 1,
                        )
                    )
                    requeued.append(str(row["id"]))
        return requeued, failed
