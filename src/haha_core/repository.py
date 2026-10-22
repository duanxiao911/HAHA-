"""Persistence ports and a deterministic SQLite development adapter."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from time import sleep
from typing import Protocol
from uuid import uuid4

from haha_auth.domain import AuthAuditEvent, AuthCredential, AuthSession
from haha_core.domain import (
    BriefVersion,
    FailedJob,
    Project,
    Run,
    RunStatus,
    ScriptRevision,
    ScriptVersion,
)
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
    KnowledgeContribution,
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


class RepositoryConflictError(RuntimeError):
    """A database uniqueness boundary rejected a concurrent write."""


class CreatorRepository(Protocol):
    def ping(self) -> bool: ...

    def ensure_identity(
        self,
        user_id: str,
        workspace_id: str,
        *,
        role: str,
        email: str = "",
        workspace_name: str = "",
    ) -> None: ...

    def get_membership_role(self, user_id: str, workspace_id: str) -> str | None: ...

    def list_role_grants(self, user_id: str, workspace_id: str) -> list[RoleGrant]: ...

    def save_project(self, project: Project) -> None: ...

    def get_project(self, project_id: str) -> Project | None: ...

    def list_projects(self, workspace_id: str, *, limit: int = 20) -> list[Project]: ...

    def next_brief_version(self, project_id: str) -> int: ...

    def save_brief(self, brief: BriefVersion) -> None: ...

    def get_brief(self, brief_id: str) -> BriefVersion | None: ...

    def save_run(self, run: Run) -> None: ...

    def get_run(self, run_id: str) -> Run | None: ...

    def cancel_run(self, run_id: str) -> Run | None: ...

    def find_run_by_idempotency_key(
        self, workspace_id: str, project_id: str, key: str
    ) -> Run | None: ...

    def next_script_version(self, project_id: str) -> int: ...

    def save_script(self, script: ScriptVersion) -> None: ...

    def get_script_for_run(self, run_id: str) -> ScriptVersion | None: ...

    def next_script_revision_version(self, run_id: str) -> int: ...

    def save_script_revision(self, revision: ScriptRevision) -> None: ...

    def get_latest_script_revision(self, run_id: str) -> ScriptRevision | None: ...

    def complete_run_with_script(self, run: Run, script: ScriptVersion, worker_id: str, claim_epoch: int) -> None: ...

    def save_claimed_run(self, run: Run, worker_id: str, claim_epoch: int) -> None: ...

    def claim_run(self, run_id: str, worker_id: str, lease_seconds: int = 120) -> Run | None: ...

    def heartbeat_run(self, run_id: str, worker_id: str, claim_epoch: int, lease_seconds: int = 120) -> bool: ...

    def record_failed_job(self, run_id: str, reason: str) -> None: ...

    def list_failed_jobs(
        self, workspace_id: str, *, include_resolved: bool = False, limit: int = 100
    ) -> list[FailedJob]: ...

    def get_failed_job(self, failed_job_id: str, workspace_id: str) -> FailedJob | None: ...

    def retry_failed_job(
        self, failed_job_id: str, workspace_id: str, *, max_attempts: int
    ) -> Run | None: ...

    def resolve_failed_job(self, failed_job_id: str, workspace_id: str) -> FailedJob | None: ...

    def reconcile_expired_runs(
        self, *, max_attempts: int, limit: int = 100
    ) -> tuple[list[str], list[str]]: ...


class SQLiteCreatorRepository:
    """Local adapter with production-shaped schemas; PostgreSQL can replace this port."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._failed_job_retry_lock = Lock()
        self._auth_session_rotation_lock = Lock()
        self._account_registration_lock = Lock()
        self._memory_uri = ""
        self._memory_keeper: sqlite3.Connection | None = None
        if self.path == ":memory:":
            self._memory_uri = f"file:haha_{uuid4().hex}?mode=memory&cache=shared"
            self._memory_keeper = sqlite3.connect(
                self._memory_uri, uri=True, check_same_thread=False
            )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        if self._memory_uri:
            connection = sqlite3.connect(self._memory_uri, uri=True, check_same_thread=False)
        else:
            connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def ping(self) -> bool:
        with closing(self._connect()) as connection:
            return connection.execute("SELECT 1").fetchone()[0] == 1

    def _initialize(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memberships (
                    user_id TEXT NOT NULL, workspace_id TEXT NOT NULL, role TEXT NOT NULL,
                    created_at TEXT NOT NULL, PRIMARY KEY(user_id, workspace_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE TABLE IF NOT EXISTS auth_credentials (
                    user_id TEXT NOT NULL, workspace_id TEXT NOT NULL, email TEXT NOT NULL,
                    password_salt TEXT NOT NULL, password_hash TEXT NOT NULL,
                    password_iterations INTEGER NOT NULL, status TEXT NOT NULL,
                    failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, workspace_id), UNIQUE(email, workspace_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    refresh_token_hash TEXT NOT NULL, expires_at TEXT NOT NULL,
                    revoked_at TEXT NOT NULL, created_at TEXT NOT NULL, last_used_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE INDEX IF NOT EXISTS ix_auth_sessions_owner
                    ON auth_sessions(user_id, workspace_id, expires_at);
                CREATE TABLE IF NOT EXISTS auth_audit_events (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, detail_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_auth_audit_owner_created
                    ON auth_audit_events(user_id, workspace_id, created_at);
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    display_name TEXT NOT NULL, active_role TEXT NOT NULL,
                    personalization_enabled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, workspace_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE TABLE IF NOT EXISTS role_grants (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    role TEXT NOT NULL, status TEXT NOT NULL, scope_json TEXT NOT NULL,
                    granted_by TEXT NOT NULL, created_at TEXT NOT NULL, revoked_at TEXT NOT NULL,
                    UNIQUE(user_id, workspace_id, role),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE TABLE IF NOT EXISTS role_applications (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    role TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL,
                    decision_note TEXT NOT NULL, reviewed_by TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE INDEX IF NOT EXISTS ix_role_applications_owner_status
                    ON role_applications(user_id, workspace_id, status);
                CREATE TABLE IF NOT EXISTS identity_tasks (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    role TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
                    description TEXT NOT NULL, target_href TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE INDEX IF NOT EXISTS ix_identity_tasks_owner_status
                    ON identity_tasks(user_id, workspace_id, status);
                CREATE TABLE IF NOT EXISTS identity_audit_events (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    actor_user_id TEXT NOT NULL, event_type TEXT NOT NULL,
                    target_role TEXT NOT NULL, detail_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_identity_audit_owner_created
                    ON identity_audit_events(user_id, workspace_id, created_at);
                CREATE TABLE IF NOT EXISTS user_center_settings (
                    user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    bio TEXT NOT NULL, region TEXT NOT NULL,
                    profile_visibility TEXT NOT NULL,
                    history_enabled INTEGER NOT NULL DEFAULT 1,
                    recommendation_enabled INTEGER NOT NULL DEFAULT 1,
                    notification_enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, workspace_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE TABLE IF NOT EXISTS user_library_items (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    kind TEXT NOT NULL, target_id TEXT NOT NULL, title TEXT NOT NULL,
                    target_href TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(user_id, workspace_id, kind, target_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE INDEX IF NOT EXISTS ix_user_library_owner_updated
                    ON user_library_items(user_id, workspace_id, updated_at);
                CREATE TABLE IF NOT EXISTS user_follows (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    target_id TEXT NOT NULL, display_name TEXT NOT NULL,
                    target_href TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(user_id, workspace_id, target_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE TABLE IF NOT EXISTS user_watch_history (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    content_id TEXT NOT NULL, title TEXT NOT NULL, target_href TEXT NOT NULL,
                    progress_seconds INTEGER NOT NULL, duration_seconds INTEGER NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0, viewed_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, workspace_id, content_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE INDEX IF NOT EXISTS ix_user_history_owner_viewed
                    ON user_watch_history(user_id, workspace_id, viewed_at);
                CREATE TABLE IF NOT EXISTS user_notifications (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
                    target_href TEXT NOT NULL, read_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE INDEX IF NOT EXISTS ix_user_notifications_owner_created
                    ON user_notifications(user_id, workspace_id, created_at);
                CREATE TABLE IF NOT EXISTS user_center_audit_events (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, detail_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_user_center_audit_owner_created
                    ON user_center_audit_events(user_id, workspace_id, created_at);
                CREATE TABLE IF NOT EXISTS learning_profiles (
                    user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    timezone TEXT NOT NULL, current_streak INTEGER NOT NULL DEFAULT 0,
                    longest_streak INTEGER NOT NULL DEFAULT 0,
                    last_learning_date TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, workspace_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE TABLE IF NOT EXISTS knowledge_sources (
                    id TEXT NOT NULL, workspace_id TEXT NOT NULL, title TEXT NOT NULL,
                    publisher TEXT NOT NULL, source_type TEXT NOT NULL, url TEXT NOT NULL,
                    version INTEGER NOT NULL, verification_status TEXT NOT NULL,
                    provenance TEXT NOT NULL, checked_at TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(id, workspace_id)
                );
                CREATE TABLE IF NOT EXISTS learning_paths (
                    id TEXT NOT NULL, workspace_id TEXT NOT NULL, title TEXT NOT NULL,
                    summary TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL,
                    provenance TEXT NOT NULL, verification_status TEXT NOT NULL,
                    source_note TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(id, workspace_id)
                );
                CREATE TABLE IF NOT EXISTS learning_units (
                    id TEXT NOT NULL, path_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    position INTEGER NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
                    summary TEXT NOT NULL, source_id TEXT NOT NULL, version INTEGER NOT NULL,
                    required INTEGER NOT NULL DEFAULT 1, estimated_minutes INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(id, workspace_id), UNIQUE(path_id, workspace_id, position),
                    FOREIGN KEY(path_id, workspace_id) REFERENCES learning_paths(id, workspace_id),
                    FOREIGN KEY(source_id, workspace_id) REFERENCES knowledge_sources(id, workspace_id)
                );
                CREATE TABLE IF NOT EXISTS learning_path_enrollments (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    path_id TEXT NOT NULL, source_content_id TEXT NOT NULL,
                    status TEXT NOT NULL, version INTEGER NOT NULL,
                    enrolled_at TEXT NOT NULL, completed_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(user_id, workspace_id, path_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
                    FOREIGN KEY(path_id, workspace_id) REFERENCES learning_paths(id, workspace_id)
                );
                CREATE TABLE IF NOT EXISTS learning_progress (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    path_id TEXT NOT NULL, unit_id TEXT NOT NULL, status TEXT NOT NULL,
                    progress_percent INTEGER NOT NULL, version INTEGER NOT NULL,
                    started_at TEXT NOT NULL, completed_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(user_id, workspace_id, unit_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
                    FOREIGN KEY(unit_id, workspace_id) REFERENCES learning_units(id, workspace_id)
                );
                CREATE INDEX IF NOT EXISTS ix_learning_progress_owner_updated
                    ON learning_progress(user_id, workspace_id, updated_at);
                CREATE TABLE IF NOT EXISTS knowledge_cards (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    path_id TEXT NOT NULL, unit_id TEXT NOT NULL, topic TEXT NOT NULL,
                    body TEXT NOT NULL, source_id TEXT NOT NULL, source_version INTEGER NOT NULL,
                    trust_status TEXT NOT NULL, version INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(user_id, workspace_id, unit_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
                    FOREIGN KEY(unit_id, workspace_id) REFERENCES learning_units(id, workspace_id),
                    FOREIGN KEY(source_id, workspace_id) REFERENCES knowledge_sources(id, workspace_id)
                );
                CREATE TABLE IF NOT EXISTS quizzes (
                    id TEXT NOT NULL, workspace_id TEXT NOT NULL, path_id TEXT NOT NULL,
                    unit_id TEXT NOT NULL, title TEXT NOT NULL, version INTEGER NOT NULL,
                    pass_score INTEGER NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(id, workspace_id), UNIQUE(unit_id, workspace_id),
                    FOREIGN KEY(unit_id, workspace_id) REFERENCES learning_units(id, workspace_id)
                );
                CREATE TABLE IF NOT EXISTS quiz_questions (
                    id TEXT NOT NULL, quiz_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    position INTEGER NOT NULL, prompt TEXT NOT NULL, choices_json TEXT NOT NULL,
                    correct_choice INTEGER NOT NULL, explanation TEXT NOT NULL,
                    source_id TEXT NOT NULL, version INTEGER NOT NULL,
                    PRIMARY KEY(id, workspace_id), UNIQUE(quiz_id, workspace_id, position),
                    FOREIGN KEY(quiz_id, workspace_id) REFERENCES quizzes(id, workspace_id),
                    FOREIGN KEY(source_id, workspace_id) REFERENCES knowledge_sources(id, workspace_id)
                );
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    quiz_id TEXT NOT NULL, quiz_version INTEGER NOT NULL,
                    answers_json TEXT NOT NULL, question_snapshot_json TEXT NOT NULL,
                    score INTEGER NOT NULL, passed INTEGER NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
                    FOREIGN KEY(quiz_id, workspace_id) REFERENCES quizzes(id, workspace_id)
                );
                CREATE INDEX IF NOT EXISTS ix_quiz_attempt_owner_created
                    ON quiz_attempts(user_id, workspace_id, created_at);
                CREATE TABLE IF NOT EXISTS learning_events (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
                    entity_version INTEGER NOT NULL, idempotency_key TEXT NOT NULL,
                    activity_date TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(user_id, workspace_id, idempotency_key),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE INDEX IF NOT EXISTS ix_learning_events_owner_date
                    ON learning_events(user_id, workspace_id, activity_date, event_type);
                CREATE TABLE IF NOT EXISTS tutor_interactions (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL, request_fingerprint TEXT NOT NULL,
                    question TEXT NOT NULL, status TEXT NOT NULL, answer TEXT NOT NULL,
                    citations_json TEXT NOT NULL, model TEXT NOT NULL, request_id TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL, error_code TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(user_id, workspace_id, idempotency_key),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE INDEX IF NOT EXISTS ix_tutor_interactions_owner_created
                    ON tutor_interactions(user_id, workspace_id, created_at);
                CREATE TABLE IF NOT EXISTS daily_tasks (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    task_date TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
                    event_type TEXT NOT NULL, target_count INTEGER NOT NULL,
                    current_count INTEGER NOT NULL, status TEXT NOT NULL,
                    version INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(user_id, workspace_id, task_date, kind),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE TABLE IF NOT EXISTS achievement_definitions (
                    id TEXT NOT NULL, workspace_id TEXT NOT NULL, code TEXT NOT NULL,
                    title TEXT NOT NULL, description TEXT NOT NULL, event_type TEXT NOT NULL,
                    threshold INTEGER NOT NULL, points INTEGER NOT NULL, version INTEGER NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(id, workspace_id), UNIQUE(workspace_id, code, version)
                );
                CREATE TABLE IF NOT EXISTS achievement_grants (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    definition_id TEXT NOT NULL, definition_version INTEGER NOT NULL,
                    triggering_event_id TEXT NOT NULL, granted_at TEXT NOT NULL,
                    UNIQUE(user_id, workspace_id, definition_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
                    FOREIGN KEY(definition_id, workspace_id)
                        REFERENCES achievement_definitions(id, workspace_id),
                    FOREIGN KEY(triggering_event_id) REFERENCES learning_events(id)
                );
                CREATE TABLE IF NOT EXISTS knowledge_contributions (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    topic TEXT NOT NULL, body TEXT NOT NULL, source_title TEXT NOT NULL,
                    source_url TEXT NOT NULL, source_version TEXT NOT NULL,
                    status TEXT NOT NULL, version INTEGER NOT NULL,
                    reviewer_note TEXT NOT NULL, reviewed_by TEXT NOT NULL,
                    submitted_at TEXT NOT NULL, reviewed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
                );
                CREATE INDEX IF NOT EXISTS ix_knowledge_contributions_owner_updated
                    ON knowledge_contributions(user_id, workspace_id, updated_at);
                CREATE INDEX IF NOT EXISTS ix_knowledge_contributions_review_queue
                    ON knowledge_contributions(workspace_id, status, submitted_at);
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, title TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS brief_versions (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(project_id, version),
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT NOT NULL, brief_version_id TEXT NOT NULL,
                    status TEXT NOT NULL, model_preference TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL, request_fingerprint TEXT NOT NULL, attempt INTEGER NOT NULL,
                    error_code TEXT NOT NULL, error_message TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    claimed_by TEXT NOT NULL DEFAULT '', claimed_at TEXT NOT NULL DEFAULT '',
                    lease_until TEXT NOT NULL DEFAULT '', heartbeat_at TEXT NOT NULL DEFAULT '',
                    claim_epoch INTEGER NOT NULL DEFAULT 0,
                    lock_version INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(workspace_id, project_id, idempotency_key),
                    FOREIGN KEY(project_id) REFERENCES projects(id),
                    FOREIGN KEY(brief_version_id) REFERENCES brief_versions(id)
                );
                CREATE TABLE IF NOT EXISTS script_versions (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, run_id TEXT NOT NULL UNIQUE,
                    brief_version_id TEXT NOT NULL, version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL, evidence_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(project_id, version),
                    FOREIGN KEY(project_id) REFERENCES projects(id),
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                );
                CREATE TABLE IF NOT EXISTS script_revisions (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, run_id TEXT NOT NULL,
                    base_script_id TEXT NOT NULL, version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL, review_status TEXT NOT NULL,
                    review_note TEXT NOT NULL DEFAULT '', created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    lock_version INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(run_id, version),
                    FOREIGN KEY(project_id) REFERENCES projects(id),
                    FOREIGN KEY(run_id) REFERENCES runs(id),
                    FOREIGN KEY(base_script_id) REFERENCES script_versions(id)
                );
                CREATE INDEX IF NOT EXISTS ix_script_revisions_run_updated
                    ON script_revisions(run_id, updated_at);
                CREATE TABLE IF NOT EXISTS failed_jobs (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, reason TEXT NOT NULL,
                    created_at TEXT NOT NULL, resolved_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                );
                """
            )
            try:
                connection.execute(
                    """CREATE UNIQUE INDEX IF NOT EXISTS uq_auth_credential_email_lower
                       ON auth_credentials(lower(email))"""
                )
            except sqlite3.IntegrityError:
                # Legacy local databases can contain the same internal email in
                # multiple workspaces. Public registration stays serialized and
                # fail-closed until those demo credentials are reconciled.
                pass
            existing_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(runs)").fetchall()
            }
            for name, definition in {
                "workspace_id": "TEXT NOT NULL DEFAULT ''",
                "request_fingerprint": "TEXT NOT NULL DEFAULT ''",
                "claimed_by": "TEXT NOT NULL DEFAULT ''",
                "claimed_at": "TEXT NOT NULL DEFAULT ''",
                "lease_until": "TEXT NOT NULL DEFAULT ''",
                "heartbeat_at": "TEXT NOT NULL DEFAULT ''",
                "claim_epoch": "INTEGER NOT NULL DEFAULT 0",
                "lock_version": "INTEGER NOT NULL DEFAULT 0",
            }.items():
                if name not in existing_columns:
                    connection.execute(f"ALTER TABLE runs ADD COLUMN {name} {definition}")
            connection.execute(
                """UPDATE runs SET workspace_id = COALESCE(
                       (SELECT workspace_id FROM projects WHERE projects.id = runs.project_id), ''
                   ) WHERE workspace_id = ''"""
            )
            connection.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS uq_runs_workspace_project_key
                   ON runs(workspace_id, project_id, idempotency_key)"""
            )

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
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT OR IGNORE INTO users(id, email, created_at) VALUES (?, ?, ?)",
                (user_id, email, now),
            )
            connection.execute(
                "INSERT OR IGNORE INTO workspaces(id, name, created_at) VALUES (?, ?, ?)",
                (workspace_id, workspace_name or workspace_id, now),
            )
            connection.execute(
                """INSERT OR IGNORE INTO memberships(user_id, workspace_id, role, created_at)
                   VALUES (?, ?, ?, ?)""",
                (user_id, workspace_id, role, now),
            )

    def get_membership_role(self, user_id: str, workspace_id: str) -> str | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT role FROM memberships WHERE user_id = ? AND workspace_id = ?",
                (user_id, workspace_id),
            ).fetchone()
        return str(row["role"]) if row else None

    def get_auth_credential(self, email: str, workspace_id: str) -> AuthCredential | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM auth_credentials WHERE email = ? AND workspace_id = ?",
                (email, workspace_id),
            ).fetchone()
        return AuthCredential(**dict(row)) if row else None

    def get_auth_credential_by_email(self, email: str) -> AuthCredential | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM auth_credentials WHERE lower(email) = lower(?) LIMIT 1",
                (email,),
            ).fetchone()
        return AuthCredential(**dict(row)) if row else None

    def get_auth_credential_by_user(
        self, user_id: str, workspace_id: str
    ) -> AuthCredential | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM auth_credentials WHERE user_id = ? AND workspace_id = ?",
                (user_id, workspace_id),
            ).fetchone()
        return AuthCredential(**dict(row)) if row else None

    def create_personal_account(
        self, credential: AuthCredential, *, workspace_name: str, display_name: str
    ) -> bool:
        with self._account_registration_lock:
            try:
                with closing(self._connect()) as connection, connection:
                    if connection.execute(
                        "SELECT 1 FROM auth_credentials WHERE lower(email) = lower(?)",
                        (credential.email,),
                    ).fetchone():
                        return False
                    connection.execute(
                        "INSERT INTO users(id, email, created_at) VALUES (?, ?, ?)",
                        (credential.user_id, credential.email, credential.created_at),
                    )
                    connection.execute(
                        "INSERT INTO workspaces(id, name, created_at) VALUES (?, ?, ?)",
                        (credential.workspace_id, workspace_name, credential.created_at),
                    )
                    connection.execute(
                        """INSERT INTO memberships(user_id, workspace_id, role, created_at)
                           VALUES (?, ?, 'owner', ?)""",
                        (
                            credential.user_id,
                            credential.workspace_id,
                            credential.created_at,
                        ),
                    )
                    connection.execute(
                        """INSERT INTO user_profiles(
                               user_id, workspace_id, display_name, active_role,
                               personalization_enabled, created_at, updated_at
                           ) VALUES (?, ?, ?, 'viewer', 0, ?, ?)""",
                        (
                            credential.user_id,
                            credential.workspace_id,
                            display_name,
                            credential.created_at,
                            credential.created_at,
                        ),
                    )
                    connection.execute(
                        "INSERT INTO auth_credentials VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        tuple(asdict(credential).values()),
                    )
            except sqlite3.IntegrityError:
                return False
        return True

    def save_auth_credential(self, credential: AuthCredential) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO auth_credentials VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, workspace_id) DO UPDATE SET
                       email=excluded.email, password_salt=excluded.password_salt,
                       password_hash=excluded.password_hash,
                       password_iterations=excluded.password_iterations,
                       status=excluded.status, failed_attempts=excluded.failed_attempts,
                       locked_until=excluded.locked_until, updated_at=excluded.updated_at""",
                tuple(asdict(credential).values()),
            )

    def change_password_and_revoke_sessions(
        self, credential: AuthCredential, revoked_at: str
    ) -> int:
        with closing(self._connect()) as connection, connection:
            result = connection.execute(
                """UPDATE auth_credentials SET
                       password_salt = ?, password_hash = ?, password_iterations = ?,
                       failed_attempts = 0, locked_until = '', updated_at = ?
                   WHERE user_id = ? AND workspace_id = ? AND status = 'active'""",
                (
                    credential.password_salt,
                    credential.password_hash,
                    credential.password_iterations,
                    credential.updated_at,
                    credential.user_id,
                    credential.workspace_id,
                ),
            )
            if result.rowcount != 1:
                raise RuntimeError("账户凭据不可用")
            revoked = connection.execute(
                """UPDATE auth_sessions SET revoked_at = ?, last_used_at = ?
                   WHERE user_id = ? AND workspace_id = ? AND revoked_at = ''""",
                (revoked_at, revoked_at, credential.user_id, credential.workspace_id),
            )
            return int(revoked.rowcount)

    def get_auth_session(self, session_id: str) -> AuthSession | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM auth_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return AuthSession(**dict(row)) if row else None

    def list_auth_sessions(self, user_id: str, workspace_id: str) -> list[AuthSession]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM auth_sessions
                   WHERE user_id = ? AND workspace_id = ?
                   ORDER BY created_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [AuthSession(**dict(row)) for row in rows]

    def save_auth_session(self, session: AuthSession) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO auth_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       refresh_token_hash=excluded.refresh_token_hash,
                       expires_at=excluded.expires_at, revoked_at=excluded.revoked_at,
                       last_used_at=excluded.last_used_at""",
                tuple(asdict(session).values()),
            )

    def rotate_auth_session(self, session: AuthSession, expected_hash: str) -> bool:
        """Atomically consume one refresh secret and install its replacement."""
        with self._auth_session_rotation_lock:
            for attempt in range(5):
                try:
                    with closing(self._connect()) as connection, connection:
                        result = connection.execute(
                            """UPDATE auth_sessions SET refresh_token_hash = ?, expires_at = ?,
                                      revoked_at = ?, last_used_at = ?
                               WHERE id = ? AND refresh_token_hash = ? AND revoked_at = ''""",
                            (
                                session.refresh_token_hash,
                                session.expires_at,
                                session.revoked_at,
                                session.last_used_at,
                                session.id,
                                expected_hash,
                            ),
                        )
                    return result.rowcount == 1
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower() or attempt == 4:
                        raise
                    sleep(0.01 * (attempt + 1))
        return False

    def revoke_auth_session(
        self, session_id: str, user_id: str, workspace_id: str, revoked_at: str
    ) -> bool:
        with closing(self._connect()) as connection, connection:
            result = connection.execute(
                """UPDATE auth_sessions SET revoked_at = ?, last_used_at = ?
                   WHERE id = ? AND user_id = ? AND workspace_id = ?
                     AND revoked_at = ''""",
                (revoked_at, revoked_at, session_id, user_id, workspace_id),
            )
        return result.rowcount == 1

    def revoke_all_auth_sessions(self, user_id: str, workspace_id: str, revoked_at: str) -> int:
        with closing(self._connect()) as connection, connection:
            result = connection.execute(
                """UPDATE auth_sessions SET revoked_at = ?, last_used_at = ?
                   WHERE user_id = ? AND workspace_id = ? AND revoked_at = ''""",
                (revoked_at, revoked_at, user_id, workspace_id),
            )
        return result.rowcount

    def save_auth_audit_event(self, event: AuthAuditEvent) -> None:
        with self._auth_session_rotation_lock:
            for attempt in range(5):
                try:
                    with closing(self._connect()) as connection, connection:
                        connection.execute(
                            "INSERT INTO auth_audit_events VALUES (?, ?, ?, ?, ?, ?)",
                            tuple(asdict(event).values()),
                        )
                    return
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower() or attempt == 4:
                        raise
                    sleep(0.01 * (attempt + 1))

    def ensure_user_profile(self, user_id: str, workspace_id: str) -> UserProfile:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT OR IGNORE INTO user_profiles(
                       user_id, workspace_id, display_name, active_role,
                       personalization_enabled, created_at, updated_at
                   ) VALUES (?, ?, ?, 'viewer', 0, ?, ?)""",
                (user_id, workspace_id, user_id, now, now),
            )
            row = connection.execute(
                "SELECT * FROM user_profiles WHERE user_id = ? AND workspace_id = ?",
                (user_id, workspace_id),
            ).fetchone()
        assert row is not None
        payload = dict(row)
        payload["personalization_enabled"] = bool(payload["personalization_enabled"])
        return UserProfile(**payload)

    def save_user_profile(self, profile: UserProfile) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO user_profiles VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, workspace_id) DO UPDATE SET
                       display_name=excluded.display_name,
                       active_role=excluded.active_role,
                       personalization_enabled=excluded.personalization_enabled,
                       updated_at=excluded.updated_at""",
                (
                    profile.user_id,
                    profile.workspace_id,
                    profile.display_name,
                    profile.active_role,
                    int(profile.personalization_enabled),
                    profile.created_at,
                    profile.updated_at,
                ),
            )

    def list_role_grants(self, user_id: str, workspace_id: str) -> list[RoleGrant]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM role_grants WHERE user_id = ? AND workspace_id = ? ORDER BY created_at",
                (user_id, workspace_id),
            ).fetchall()
        return [RoleGrant(**dict(row)) for row in rows]

    def save_role_grant(self, grant: RoleGrant) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO role_grants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, workspace_id, role) DO UPDATE SET
                       status=excluded.status, scope_json=excluded.scope_json,
                       granted_by=excluded.granted_by, created_at=excluded.created_at,
                       revoked_at=excluded.revoked_at""",
                tuple(asdict(grant).values()),
            )

    def get_role_application(self, application_id: str) -> RoleApplication | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM role_applications WHERE id = ?", (application_id,)
            ).fetchone()
        return RoleApplication(**dict(row)) if row else None

    def find_pending_role_application(
        self, user_id: str, workspace_id: str, role: str
    ) -> RoleApplication | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT * FROM role_applications
                   WHERE user_id = ? AND workspace_id = ? AND role = ? AND status = 'pending'
                   ORDER BY created_at DESC LIMIT 1""",
                (user_id, workspace_id, role),
            ).fetchone()
        return RoleApplication(**dict(row)) if row else None

    def list_role_applications(self, user_id: str, workspace_id: str) -> list[RoleApplication]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM role_applications WHERE user_id = ? AND workspace_id = ?
                   ORDER BY created_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [RoleApplication(**dict(row)) for row in rows]

    def save_role_application(self, application: RoleApplication) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO role_applications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET status=excluded.status,
                       decision_note=excluded.decision_note, reviewed_by=excluded.reviewed_by,
                       updated_at=excluded.updated_at""",
                tuple(asdict(application).values()),
            )

    def save_identity_task(self, task: IdentityTask) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO identity_tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET status=excluded.status,
                       completed_at=excluded.completed_at""",
                tuple(asdict(task).values()),
            )

    def list_identity_tasks(self, user_id: str, workspace_id: str) -> list[IdentityTask]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM identity_tasks WHERE user_id = ? AND workspace_id = ?
                   ORDER BY CASE status WHEN 'open' THEN 0 ELSE 1 END, created_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [IdentityTask(**dict(row)) for row in rows]

    def get_identity_task(
        self, task_id: str, user_id: str, workspace_id: str
    ) -> IdentityTask | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT * FROM identity_tasks
                   WHERE id = ? AND user_id = ? AND workspace_id = ?""",
                (task_id, user_id, workspace_id),
            ).fetchone()
        return IdentityTask(**dict(row)) if row else None

    def save_identity_audit_event(self, event: IdentityAuditEvent) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO identity_audit_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(asdict(event).values()),
            )

    def has_user_center_settings(self, user_id: str, workspace_id: str) -> bool:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT 1 FROM user_center_settings
                   WHERE user_id = ? AND workspace_id = ?""",
                (user_id, workspace_id),
            ).fetchone()
        return row is not None

    def ensure_user_center_settings(self, user_id: str, workspace_id: str) -> UserCenterSettings:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT OR IGNORE INTO user_center_settings(
                       user_id, workspace_id, bio, region, profile_visibility,
                       history_enabled, recommendation_enabled, notification_enabled,
                       created_at, updated_at
                   ) VALUES (?, ?, '', '', 'private', 1, 1, 1, ?, ?)""",
                (user_id, workspace_id, now, now),
            )
            row = connection.execute(
                """SELECT * FROM user_center_settings
                   WHERE user_id = ? AND workspace_id = ?""",
                (user_id, workspace_id),
            ).fetchone()
        assert row is not None
        payload = dict(row)
        for key in ("history_enabled", "recommendation_enabled", "notification_enabled"):
            payload[key] = bool(payload[key])
        return UserCenterSettings(**payload)

    def save_user_center_settings(self, settings: UserCenterSettings) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO user_center_settings(
                       user_id, workspace_id, bio, region, profile_visibility,
                       history_enabled, recommendation_enabled, notification_enabled,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, workspace_id) DO UPDATE SET
                       bio=excluded.bio, region=excluded.region,
                       profile_visibility=excluded.profile_visibility,
                       history_enabled=excluded.history_enabled,
                       recommendation_enabled=excluded.recommendation_enabled,
                       notification_enabled=excluded.notification_enabled,
                       updated_at=excluded.updated_at""",
                (
                    settings.user_id,
                    settings.workspace_id,
                    settings.bio,
                    settings.region,
                    settings.profile_visibility,
                    int(settings.history_enabled),
                    int(settings.recommendation_enabled),
                    int(settings.notification_enabled),
                    settings.created_at,
                    settings.updated_at,
                ),
            )

    def list_library_items(self, user_id: str, workspace_id: str) -> list[LibraryItem]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM user_library_items
                   WHERE user_id = ? AND workspace_id = ? ORDER BY updated_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [LibraryItem(**dict(row)) for row in rows]

    def save_library_item(self, item: LibraryItem) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO user_library_items
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, workspace_id, kind, target_id) DO UPDATE SET
                       title=excluded.title, target_href=excluded.target_href,
                       updated_at=excluded.updated_at""",
                tuple(asdict(item).values()),
            )

    def delete_library_item(
        self, user_id: str, workspace_id: str, kind: str, target_id: str
    ) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """DELETE FROM user_library_items
                   WHERE user_id = ? AND workspace_id = ? AND kind = ? AND target_id = ?""",
                (user_id, workspace_id, kind, target_id),
            )

    def list_user_follows(self, user_id: str, workspace_id: str) -> list[UserFollow]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM user_follows
                   WHERE user_id = ? AND workspace_id = ? ORDER BY updated_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [UserFollow(**dict(row)) for row in rows]

    def save_user_follow(self, follow: UserFollow) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO user_follows VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, workspace_id, target_id) DO UPDATE SET
                       display_name=excluded.display_name,
                       target_href=excluded.target_href, updated_at=excluded.updated_at""",
                tuple(asdict(follow).values()),
            )

    def delete_user_follow(self, user_id: str, workspace_id: str, target_id: str) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """DELETE FROM user_follows
                   WHERE user_id = ? AND workspace_id = ? AND target_id = ?""",
                (user_id, workspace_id, target_id),
            )

    def list_watch_history(self, user_id: str, workspace_id: str) -> list[WatchHistoryItem]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM user_watch_history
                   WHERE user_id = ? AND workspace_id = ? ORDER BY viewed_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        result = []
        for row in rows:
            payload = dict(row)
            payload["completed"] = bool(payload["completed"])
            result.append(WatchHistoryItem(**payload))
        return result

    def save_watch_history(self, item: WatchHistoryItem) -> None:
        values = list(asdict(item).values())
        values[8] = int(item.completed)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO user_watch_history
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, workspace_id, content_id) DO UPDATE SET
                       title=excluded.title, target_href=excluded.target_href,
                       progress_seconds=excluded.progress_seconds,
                       duration_seconds=excluded.duration_seconds,
                       completed=excluded.completed, viewed_at=excluded.viewed_at,
                       updated_at=excluded.updated_at""",
                tuple(values),
            )

    def delete_watch_history_item(self, user_id: str, workspace_id: str, content_id: str) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """DELETE FROM user_watch_history
                   WHERE user_id = ? AND workspace_id = ? AND content_id = ?""",
                (user_id, workspace_id, content_id),
            )

    def clear_watch_history(self, user_id: str, workspace_id: str) -> int:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """DELETE FROM user_watch_history
                   WHERE user_id = ? AND workspace_id = ?""",
                (user_id, workspace_id),
            )
            removed = cursor.rowcount
        return max(0, removed)

    def list_user_notifications(self, user_id: str, workspace_id: str) -> list[UserNotification]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM user_notifications
                   WHERE user_id = ? AND workspace_id = ? ORDER BY created_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [UserNotification(**dict(row)) for row in rows]

    def get_user_notification(
        self, notification_id: str, user_id: str, workspace_id: str
    ) -> UserNotification | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT * FROM user_notifications
                   WHERE id = ? AND user_id = ? AND workspace_id = ?""",
                (notification_id, user_id, workspace_id),
            ).fetchone()
        return UserNotification(**dict(row)) if row else None

    def save_user_notification(self, notification: UserNotification) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO user_notifications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET title=excluded.title,
                       body=excluded.body, target_href=excluded.target_href,
                       read_at=excluded.read_at""",
                tuple(asdict(notification).values()),
            )

    def delete_user_notification(
        self, notification_id: str, user_id: str, workspace_id: str
    ) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """DELETE FROM user_notifications
                   WHERE id = ? AND user_id = ? AND workspace_id = ?""",
                (notification_id, user_id, workspace_id),
            )

    def save_user_center_audit_event(self, event: UserCenterAuditEvent) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO user_center_audit_events VALUES (?, ?, ?, ?, ?, ?)",
                tuple(asdict(event).values()),
            )

    @staticmethod
    def _learning_id(prefix: str, *values: str) -> str:
        digest = hashlib.sha256(":".join(values).encode()).hexdigest()[:32]
        return f"{prefix}_{digest}"

    def ensure_learning_catalog(self, workspace_id: str) -> None:
        records = catalog_records(workspace_id)
        with closing(self._connect()) as connection, connection:
            for item in records["sources"]:
                connection.execute(
                    "INSERT OR IGNORE INTO knowledge_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(asdict(item).values()),
                )
            for item in records["paths"]:
                connection.execute(
                    "INSERT OR IGNORE INTO learning_paths VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(asdict(item).values()),
                )
            for item in records["units"]:
                values = asdict(item)
                values["required"] = int(item.required)
                connection.execute(
                    "INSERT OR IGNORE INTO learning_units VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(values.values()),
                )
            for item in records["quizzes"]:
                connection.execute(
                    "INSERT OR IGNORE INTO quizzes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(asdict(item).values()),
                )
            for item in records["questions"]:
                connection.execute(
                    "INSERT OR IGNORE INTO quiz_questions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(asdict(item).values()),
                )
            for item in records["achievements"]:
                connection.execute(
                    "INSERT OR IGNORE INTO achievement_definitions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(asdict(item).values()),
                )

    def ensure_learning_profile(self, user_id: str, workspace_id: str) -> LearningProfile:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT OR IGNORE INTO learning_profiles
                   VALUES (?, ?, 'Asia/Shanghai', 0, 0, '', 1, ?, ?)""",
                (user_id, workspace_id, now, now),
            )
            row = connection.execute(
                "SELECT * FROM learning_profiles WHERE user_id = ? AND workspace_id = ?",
                (user_id, workspace_id),
            ).fetchone()
        assert row is not None
        return LearningProfile(**dict(row))

    def get_learning_profile(self, user_id: str, workspace_id: str) -> LearningProfile | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM learning_profiles WHERE user_id = ? AND workspace_id = ?",
                (user_id, workspace_id),
            ).fetchone()
        return LearningProfile(**dict(row)) if row else None

    def list_learning_paths(self, workspace_id: str) -> list[LearningPath]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM learning_paths WHERE workspace_id = ? ORDER BY created_at, id",
                (workspace_id,),
            ).fetchall()
        return [LearningPath(**dict(row)) for row in rows]

    def get_learning_path(self, path_id: str, workspace_id: str) -> LearningPath | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM learning_paths WHERE id = ? AND workspace_id = ?",
                (path_id, workspace_id),
            ).fetchone()
        return LearningPath(**dict(row)) if row else None

    def list_learning_units(self, path_id: str, workspace_id: str) -> list[LearningUnit]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM learning_units WHERE path_id = ? AND workspace_id = ?
                   ORDER BY position""",
                (path_id, workspace_id),
            ).fetchall()
        return [LearningUnit(**{**dict(row), "required": bool(row["required"])}) for row in rows]

    def get_learning_unit(self, unit_id: str, workspace_id: str) -> LearningUnit | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM learning_units WHERE id = ? AND workspace_id = ?",
                (unit_id, workspace_id),
            ).fetchone()
        return LearningUnit(**{**dict(row), "required": bool(row["required"])}) if row else None

    def list_knowledge_sources(self, workspace_id: str) -> list[KnowledgeSource]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_sources WHERE workspace_id = ? ORDER BY title",
                (workspace_id,),
            ).fetchall()
        return [KnowledgeSource(**dict(row)) for row in rows]

    def get_knowledge_source(self, source_id: str, workspace_id: str) -> KnowledgeSource | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_sources WHERE id = ? AND workspace_id = ?",
                (source_id, workspace_id),
            ).fetchone()
        return KnowledgeSource(**dict(row)) if row else None

    def list_path_enrollments(self, user_id: str, workspace_id: str) -> list[PathEnrollment]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM learning_path_enrollments
                   WHERE user_id = ? AND workspace_id = ? ORDER BY updated_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [PathEnrollment(**dict(row)) for row in rows]

    def get_path_enrollment(self, user_id: str, workspace_id: str, path_id: str) -> PathEnrollment | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT * FROM learning_path_enrollments
                   WHERE user_id = ? AND workspace_id = ? AND path_id = ?""",
                (user_id, workspace_id, path_id),
            ).fetchone()
        return PathEnrollment(**dict(row)) if row else None

    def list_learning_progress(self, user_id: str, workspace_id: str) -> list[LearningProgress]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM learning_progress WHERE user_id = ? AND workspace_id = ?
                   ORDER BY updated_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [LearningProgress(**dict(row)) for row in rows]

    def get_learning_progress(self, user_id: str, workspace_id: str, unit_id: str) -> LearningProgress | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT * FROM learning_progress
                   WHERE user_id = ? AND workspace_id = ? AND unit_id = ?""",
                (user_id, workspace_id, unit_id),
            ).fetchone()
        return LearningProgress(**dict(row)) if row else None

    def list_knowledge_cards(self, user_id: str, workspace_id: str) -> list[KnowledgeCard]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM knowledge_cards WHERE user_id = ? AND workspace_id = ?
                   ORDER BY updated_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [KnowledgeCard(**dict(row)) for row in rows]

    def get_knowledge_card(self, user_id: str, workspace_id: str, unit_id: str) -> KnowledgeCard | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT * FROM knowledge_cards
                   WHERE user_id = ? AND workspace_id = ? AND unit_id = ?""",
                (user_id, workspace_id, unit_id),
            ).fetchone()
        return KnowledgeCard(**dict(row)) if row else None

    def get_quiz(self, quiz_id: str, workspace_id: str) -> Quiz | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM quizzes WHERE id = ? AND workspace_id = ?",
                (quiz_id, workspace_id),
            ).fetchone()
        return Quiz(**dict(row)) if row else None

    def get_quiz_for_unit(self, unit_id: str, workspace_id: str) -> Quiz | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM quizzes WHERE unit_id = ? AND workspace_id = ?",
                (unit_id, workspace_id),
            ).fetchone()
        return Quiz(**dict(row)) if row else None

    def list_quiz_questions(self, quiz_id: str, workspace_id: str) -> list[QuizQuestion]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM quiz_questions WHERE quiz_id = ? AND workspace_id = ?
                   ORDER BY position""",
                (quiz_id, workspace_id),
            ).fetchall()
        return [QuizQuestion(**dict(row)) for row in rows]

    def list_quiz_attempts(self, user_id: str, workspace_id: str) -> list[QuizAttempt]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM quiz_attempts WHERE user_id = ? AND workspace_id = ?
                   ORDER BY created_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [QuizAttempt(**{**dict(row), "passed": bool(row["passed"])}) for row in rows]

    def list_learning_events(self, user_id: str, workspace_id: str) -> list[LearningEvent]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM learning_events WHERE user_id = ? AND workspace_id = ?
                   ORDER BY created_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [LearningEvent(**dict(row)) for row in rows]

    def find_learning_event(self, user_id: str, workspace_id: str, idempotency_key: str) -> LearningEvent | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT * FROM learning_events
                   WHERE user_id = ? AND workspace_id = ? AND idempotency_key = ?""",
                (user_id, workspace_id, idempotency_key),
            ).fetchone()
        return LearningEvent(**dict(row)) if row else None

    @classmethod
    def _ensure_daily_tasks_connection(
        cls, connection: sqlite3.Connection, user_id: str, workspace_id: str, task_date: str
    ) -> None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        templates = (
            ("complete_unit", "完成一个学习节点", "unit.completed"),
            ("save_card", "保存一张知识卡", "knowledge_card.saved"),
            ("pass_quiz", "通过一次测验", "quiz.passed"),
        )
        for kind, title, event_type in templates:
            connection.execute(
                """INSERT OR IGNORE INTO daily_tasks
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, 'open', 1, ?, ?)""",
                (
                    cls._learning_id("daily", user_id, workspace_id, task_date, kind),
                    user_id,
                    workspace_id,
                    task_date,
                    kind,
                    title,
                    event_type,
                    now,
                    now,
                ),
            )

    def ensure_daily_tasks(self, user_id: str, workspace_id: str, task_date: str) -> None:
        with closing(self._connect()) as connection, connection:
            self._ensure_daily_tasks_connection(connection, user_id, workspace_id, task_date)

    def list_daily_tasks(self, user_id: str, workspace_id: str, task_date: str) -> list[DailyTask]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM daily_tasks
                   WHERE user_id = ? AND workspace_id = ? AND task_date = ? ORDER BY kind""",
                (user_id, workspace_id, task_date),
            ).fetchall()
        return [DailyTask(**dict(row)) for row in rows]

    def list_achievement_definitions(self, workspace_id: str) -> list[AchievementDefinition]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM achievement_definitions
                   WHERE workspace_id = ? AND status = 'active' ORDER BY code""",
                (workspace_id,),
            ).fetchall()
        return [AchievementDefinition(**dict(row)) for row in rows]

    def list_achievement_grants(self, user_id: str, workspace_id: str) -> list[AchievementGrant]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM achievement_grants
                   WHERE user_id = ? AND workspace_id = ? ORDER BY granted_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [AchievementGrant(**dict(row)) for row in rows]

    def list_tutor_interactions(self, user_id: str, workspace_id: str) -> list[TutorInteraction]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM tutor_interactions
                   WHERE user_id = ? AND workspace_id = ? ORDER BY created_at DESC LIMIT 20""",
                (user_id, workspace_id),
            ).fetchall()
        return [TutorInteraction(**dict(row)) for row in rows]

    def find_tutor_interaction(
        self, user_id: str, workspace_id: str, idempotency_key: str
    ) -> TutorInteraction | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT * FROM tutor_interactions
                   WHERE user_id = ? AND workspace_id = ? AND idempotency_key = ?""",
                (user_id, workspace_id, idempotency_key),
            ).fetchone()
        return TutorInteraction(**dict(row)) if row else None

    def create_tutor_interaction(self, interaction: TutorInteraction) -> bool:
        with closing(self._connect()) as connection, connection:
            result = connection.execute(
                "INSERT OR IGNORE INTO tutor_interactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(asdict(interaction).values()),
            )
        return result.rowcount == 1

    def update_tutor_interaction(
        self, interaction: TutorInteraction, expected_status: str
    ) -> bool:
        with closing(self._connect()) as connection, connection:
            result = connection.execute(
                """UPDATE tutor_interactions SET status = ?, answer = ?, citations_json = ?,
                          model = ?, request_id = ?, input_tokens = ?, output_tokens = ?,
                          latency_ms = ?, error_code = ?, updated_at = ?
                   WHERE id = ? AND user_id = ? AND workspace_id = ? AND status = ?""",
                (
                    interaction.status,
                    interaction.answer,
                    interaction.citations_json,
                    interaction.model,
                    interaction.request_id,
                    interaction.input_tokens,
                    interaction.output_tokens,
                    interaction.latency_ms,
                    interaction.error_code,
                    interaction.updated_at,
                    interaction.id,
                    interaction.user_id,
                    interaction.workspace_id,
                    expected_status,
                ),
            )
        return result.rowcount == 1

    def count_tutor_interactions_since(
        self, user_id: str, workspace_id: str, created_after: str
    ) -> int:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT COUNT(*) AS total FROM tutor_interactions
                   WHERE user_id = ? AND workspace_id = ? AND created_at >= ?""",
                (user_id, workspace_id, created_after),
            ).fetchone()
        return int(row["total"]) if row else 0

    def commit_learning_activity(self, activity: LearningActivityCommit) -> bool:
        event = activity.event
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                duplicate = connection.execute(
                    """SELECT id FROM learning_events
                       WHERE user_id = ? AND workspace_id = ? AND idempotency_key = ?""",
                    (event.user_id, event.workspace_id, event.idempotency_key),
                ).fetchone()
                if duplicate:
                    connection.rollback()
                    return False
                connection.execute(
                    "INSERT INTO learning_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(asdict(event).values()),
                )
                if activity.enrollment:
                    connection.execute(
                        "INSERT OR IGNORE INTO learning_path_enrollments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        tuple(asdict(activity.enrollment).values()),
                    )
                if activity.progress:
                    progress = activity.progress
                    expected = activity.expected_progress_version
                    if expected == 0:
                        try:
                            connection.execute(
                                "INSERT INTO learning_progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                tuple(asdict(progress).values()),
                            )
                        except sqlite3.IntegrityError as exc:
                            raise LearningConflictError(
                                "学习进度版本已变化，请刷新后重试"
                            ) from exc
                    else:
                        result = connection.execute(
                            """UPDATE learning_progress SET status = ?, progress_percent = ?,
                               version = ?, started_at = ?, completed_at = ?, updated_at = ?
                               WHERE user_id = ? AND workspace_id = ? AND unit_id = ? AND version = ?""",
                            (
                                progress.status,
                                progress.progress_percent,
                                progress.version,
                                progress.started_at,
                                progress.completed_at,
                                progress.updated_at,
                                progress.user_id,
                                progress.workspace_id,
                                progress.unit_id,
                                expected,
                            ),
                        )
                        if result.rowcount != 1:
                            raise LearningConflictError(
                                "学习进度版本已变化，请刷新后重试"
                            )
                if activity.card:
                    card = activity.card
                    expected = activity.expected_card_version
                    if expected == 0:
                        try:
                            connection.execute(
                                "INSERT INTO knowledge_cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                tuple(asdict(card).values()),
                            )
                        except sqlite3.IntegrityError as exc:
                            raise LearningConflictError(
                                "知识卡版本已变化，请刷新后重试"
                            ) from exc
                    else:
                        result = connection.execute(
                            """UPDATE knowledge_cards SET topic = ?, body = ?, source_id = ?,
                               source_version = ?, trust_status = ?, version = ?, updated_at = ?
                               WHERE user_id = ? AND workspace_id = ? AND unit_id = ? AND version = ?""",
                            (
                                card.topic,
                                card.body,
                                card.source_id,
                                card.source_version,
                                card.trust_status,
                                card.version,
                                card.updated_at,
                                card.user_id,
                                card.workspace_id,
                                card.unit_id,
                                expected,
                            ),
                        )
                        if result.rowcount != 1:
                            raise LearningConflictError(
                                "知识卡版本已变化，请刷新后重试"
                            )
                if activity.attempt:
                    values = asdict(activity.attempt)
                    values["passed"] = int(activity.attempt.passed)
                    connection.execute(
                        "INSERT INTO quiz_attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        tuple(values.values()),
                    )
                if event.event_type in {
                    "unit.completed",
                    "knowledge_card.saved",
                    "quiz.passed",
                }:
                    profile = connection.execute(
                        """SELECT * FROM learning_profiles
                           WHERE user_id = ? AND workspace_id = ?""",
                        (event.user_id, event.workspace_id),
                    ).fetchone()
                    assert profile is not None
                    current_streak = profile["current_streak"]
                    if profile["last_learning_date"] != event.activity_date:
                        previous = (
                            datetime.fromisoformat(event.activity_date).date()
                            - timedelta(days=1)
                        ).isoformat()
                        current_streak = (
                            current_streak + 1
                            if profile["last_learning_date"] == previous
                            else 1
                        )
                    longest_streak = max(profile["longest_streak"], current_streak)
                    connection.execute(
                        """UPDATE learning_profiles SET current_streak = ?, longest_streak = ?,
                           last_learning_date = ?, version = version + 1, updated_at = ?
                           WHERE user_id = ? AND workspace_id = ?""",
                        (
                            current_streak,
                            longest_streak,
                            event.activity_date,
                            event.created_at,
                            event.user_id,
                            event.workspace_id,
                        ),
                    )
                    self._ensure_daily_tasks_connection(
                        connection, event.user_id, event.workspace_id, event.activity_date
                    )
                    count = connection.execute(
                        """SELECT COUNT(*) FROM learning_events
                           WHERE user_id = ? AND workspace_id = ?
                           AND activity_date = ? AND event_type = ?""",
                        (
                            event.user_id,
                            event.workspace_id,
                            event.activity_date,
                            event.event_type,
                        ),
                    ).fetchone()[0]
                    connection.execute(
                        """UPDATE daily_tasks SET current_count = MIN(target_count, ?),
                           status = CASE WHEN ? >= target_count THEN 'completed' ELSE 'open' END,
                           version = version + 1, updated_at = ?
                           WHERE user_id = ? AND workspace_id = ? AND task_date = ?
                           AND event_type = ?""",
                        (
                            count,
                            count,
                            event.created_at,
                            event.user_id,
                            event.workspace_id,
                            event.activity_date,
                            event.event_type,
                        ),
                    )
                    definitions = connection.execute(
                        """SELECT * FROM achievement_definitions
                           WHERE workspace_id = ? AND event_type = ? AND status = 'active'""",
                        (event.workspace_id, event.event_type),
                    ).fetchall()
                    total = connection.execute(
                        """SELECT COUNT(*) FROM learning_events
                           WHERE user_id = ? AND workspace_id = ? AND event_type = ?""",
                        (event.user_id, event.workspace_id, event.event_type),
                    ).fetchone()[0]
                    for definition in definitions:
                        if total >= definition["threshold"]:
                            connection.execute(
                                """INSERT OR IGNORE INTO achievement_grants
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    self._learning_id(
                                        "grant",
                                        event.user_id,
                                        event.workspace_id,
                                        definition["id"],
                                    ),
                                    event.user_id,
                                    event.workspace_id,
                                    definition["id"],
                                    definition["version"],
                                    event.id,
                                    event.created_at,
                                ),
                            )
                if activity.refresh_path_id:
                    required = connection.execute(
                        """SELECT COUNT(*) FROM learning_units
                           WHERE path_id = ? AND workspace_id = ? AND required = 1""",
                        (activity.refresh_path_id, event.workspace_id),
                    ).fetchone()[0]
                    completed = connection.execute(
                        """SELECT COUNT(*) FROM learning_progress p
                           JOIN learning_units u ON u.id = p.unit_id AND u.workspace_id = p.workspace_id
                           WHERE p.user_id = ? AND p.workspace_id = ? AND p.path_id = ?
                           AND u.required = 1 AND p.status = 'completed'""",
                        (event.user_id, event.workspace_id, activity.refresh_path_id),
                    ).fetchone()[0]
                    if required and completed >= required:
                        connection.execute(
                            """UPDATE learning_path_enrollments SET status = 'completed',
                               version = version + 1, completed_at = ?, updated_at = ?
                               WHERE user_id = ? AND workspace_id = ? AND path_id = ?
                               AND status <> 'completed'""",
                            (
                                event.created_at,
                                event.created_at,
                                event.user_id,
                                event.workspace_id,
                                activity.refresh_path_id,
                            ),
                        )
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise

    def get_learning_growth_summary(self, user_id: str, workspace_id: str) -> dict[str, object]:
        profile = self.get_learning_profile(user_id, workspace_id)
        if not profile:
            return {
                "learning_paths": 0,
                "completed_paths": 0,
                "completed_units": 0,
                "knowledge_cards": 0,
                "quiz_attempts": 0,
                "passed_quizzes": 0,
                "achievements": 0,
                "achievement_points": 0,
                "current_streak": 0,
                "longest_streak": 0,
                "last_learning_date": "",
            }
        with closing(self._connect()) as connection:
            enrollment = connection.execute(
                """SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed
                   FROM learning_path_enrollments WHERE user_id = ? AND workspace_id = ?""",
                (user_id, workspace_id),
            ).fetchone()
            completed_units = connection.execute(
                """SELECT COUNT(*) FROM learning_progress
                   WHERE user_id = ? AND workspace_id = ? AND status = 'completed'""",
                (user_id, workspace_id),
            ).fetchone()[0]
            cards = connection.execute(
                "SELECT COUNT(*) FROM knowledge_cards WHERE user_id = ? AND workspace_id = ?",
                (user_id, workspace_id),
            ).fetchone()[0]
            attempts = connection.execute(
                """SELECT COUNT(*) AS total,
                   SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) AS passed
                   FROM quiz_attempts WHERE user_id = ? AND workspace_id = ?""",
                (user_id, workspace_id),
            ).fetchone()
            achievements = connection.execute(
                """SELECT COUNT(*) AS total, COALESCE(SUM(d.points), 0) AS points
                   FROM achievement_grants g JOIN achievement_definitions d
                   ON d.id = g.definition_id AND d.workspace_id = g.workspace_id
                   WHERE g.user_id = ? AND g.workspace_id = ?""",
                (user_id, workspace_id),
            ).fetchone()
        return {
            "learning_paths": enrollment["total"],
            "completed_paths": enrollment["completed"] or 0,
            "completed_units": completed_units,
            "knowledge_cards": cards,
            "quiz_attempts": attempts["total"],
            "passed_quizzes": attempts["passed"] or 0,
            "achievements": achievements["total"],
            "achievement_points": achievements["points"],
            "current_streak": profile.current_streak,
            "longest_streak": profile.longest_streak,
            "last_learning_date": profile.last_learning_date,
        }

    def list_knowledge_contributions(self, user_id: str, workspace_id: str) -> list[KnowledgeContribution]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM knowledge_contributions
                   WHERE user_id = ? AND workspace_id = ? ORDER BY updated_at DESC""",
                (user_id, workspace_id),
            ).fetchall()
        return [KnowledgeContribution(**dict(row)) for row in rows]

    def list_knowledge_contribution_queue(self, workspace_id: str) -> list[KnowledgeContribution]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM knowledge_contributions
                   WHERE workspace_id = ? AND status = 'submitted' ORDER BY submitted_at, id""",
                (workspace_id,),
            ).fetchall()
        return [KnowledgeContribution(**dict(row)) for row in rows]

    def get_knowledge_contribution(self, contribution_id: str, workspace_id: str) -> KnowledgeContribution | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_contributions WHERE id = ? AND workspace_id = ?",
                (contribution_id, workspace_id),
            ).fetchone()
        return KnowledgeContribution(**dict(row)) if row else None

    def save_knowledge_contribution(self, contribution: KnowledgeContribution, expected_version: int | None) -> bool:
        values = asdict(contribution)
        with closing(self._connect()) as connection, connection:
            if expected_version is None:
                try:
                    connection.execute(
                        "INSERT INTO knowledge_contributions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        tuple(values.values()),
                    )
                    return True
                except sqlite3.IntegrityError:
                    return False
            assignments = ", ".join(f"{key} = ?" for key in values)
            result = connection.execute(
                f"UPDATE knowledge_contributions SET {assignments} WHERE id = ? AND workspace_id = ? AND version = ?",
                (*values.values(), contribution.id, contribution.workspace_id, expected_version),
            )
            return result.rowcount == 1

    def save_project(self, project: Project) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
                (
                    project.id,
                    project.workspace_id,
                    project.title,
                    project.created_at,
                    project.updated_at,
                ),
            )

    def get_project(self, project_id: str) -> Project | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        return Project(**dict(row)) if row else None

    def list_projects(self, workspace_id: str, *, limit: int = 20) -> list[Project]:
        safe_limit = max(1, min(limit, 100))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM projects
                   WHERE workspace_id = ?
                   ORDER BY updated_at DESC, id DESC
                   LIMIT ?""",
                (workspace_id, safe_limit),
            ).fetchall()
        return [Project(**dict(row)) for row in rows]

    def next_brief_version(self, project_id: str) -> int:
        with closing(self._connect()) as connection, connection:
            value = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM brief_versions WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
        return int(value)

    def save_brief(self, brief: BriefVersion) -> None:
        payload = asdict(brief)
        for key in ("id", "project_id", "version", "created_at"):
            payload.pop(key)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO brief_versions VALUES (?, ?, ?, ?, ?)",
                (
                    brief.id,
                    brief.project_id,
                    brief.version,
                    json.dumps(payload, ensure_ascii=False),
                    brief.created_at,
                ),
            )

    def get_brief(self, brief_id: str) -> BriefVersion | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM brief_versions WHERE id = ?", (brief_id,)
            ).fetchone()
        if not row:
            return None
        return BriefVersion(
            id=row["id"],
            project_id=row["project_id"],
            version=row["version"],
            created_at=row["created_at"],
            **json.loads(row["payload_json"]),
        )

    def save_run(self, run: Run) -> None:
        values = (
            run.id,
            run.workspace_id,
            run.project_id,
            run.brief_version_id,
            run.status.value,
            run.model_preference,
            run.idempotency_key,
            run.request_fingerprint,
            run.attempt,
            run.error_code,
            run.error_message,
            run.created_at,
            run.updated_at,
            run.claimed_by,
            run.claimed_at,
            run.lease_until,
            run.heartbeat_at,
            run.claim_epoch,
            run.lock_version,
        )
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    """INSERT INTO runs (
                       id, workspace_id, project_id, brief_version_id, status,
                       model_preference, idempotency_key, request_fingerprint, attempt,
                       error_code, error_message, created_at, updated_at, claimed_by,
                       claimed_at, lease_until, heartbeat_at, claim_epoch, lock_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET status=excluded.status, attempt=excluded.attempt,
                    error_code=excluded.error_code, error_message=excluded.error_message,
                    updated_at=excluded.updated_at, claimed_by=excluded.claimed_by,
                    claimed_at=excluded.claimed_at, lease_until=excluded.lease_until,
                    heartbeat_at=excluded.heartbeat_at, claim_epoch=excluded.claim_epoch,
                    lock_version=excluded.lock_version
                    WHERE runs.status != 'CANCELLED' OR excluded.status = 'CANCELLED'""",
                    values,
                )
        except sqlite3.IntegrityError as exc:
            raise RepositoryConflictError("run uniqueness conflict") from exc

    def _row_to_run(self, row: sqlite3.Row | None) -> Run | None:
        if not row:
            return None
        data = dict(row)
        data["status"] = RunStatus(data["status"])
        return Run(**data)

    def get_run(self, run_id: str) -> Run | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._row_to_run(row)

    def cancel_run(self, run_id: str) -> Run | None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        cancellable = tuple(
            status.value
            for status in RunStatus
            if status not in {RunStatus.PASSED, RunStatus.FAILED, RunStatus.CANCELLED}
        )
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                f"""UPDATE runs SET status = ?, error_code = '', error_message = '',
                       claimed_by = '', claimed_at = '', lease_until = '', heartbeat_at = '',
                       updated_at = ?, lock_version = lock_version + 1
                       WHERE id = ? AND status IN ({",".join("?" for _ in cancellable)})""",
                (RunStatus.CANCELLED.value, now, run_id, *cancellable),
            )
            connection.commit()
            if cursor.rowcount != 1:
                return None
        return self.get_run(run_id)

    def find_run_by_idempotency_key(
        self, workspace_id: str, project_id: str, key: str
    ) -> Run | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE workspace_id = ? AND project_id = ? AND idempotency_key = ?",
                (workspace_id, project_id, key),
            ).fetchone()
        return self._row_to_run(row)

    def next_script_version(self, project_id: str) -> int:
        with closing(self._connect()) as connection, connection:
            value = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM script_versions WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
        return int(value)

    def save_script(self, script: ScriptVersion) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO script_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    script.id,
                    script.project_id,
                    script.run_id,
                    script.brief_version_id,
                    script.version,
                    json.dumps(script.payload, ensure_ascii=False),
                    json.dumps(script.evidence, ensure_ascii=False),
                    script.created_at,
                ),
            )

    def get_script_for_run(self, run_id: str) -> ScriptVersion | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM script_versions WHERE run_id = ?", (run_id,)
            ).fetchone()
        if not row:
            return None
        return ScriptVersion(
            id=row["id"],
            project_id=row["project_id"],
            run_id=row["run_id"],
            brief_version_id=row["brief_version_id"],
            version=row["version"],
            payload=json.loads(row["payload_json"]),
            evidence=json.loads(row["evidence_json"]),
            created_at=row["created_at"],
        )

    def next_script_revision_version(self, run_id: str) -> int:
        with closing(self._connect()) as connection:
            value = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM script_revisions WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
        return int(value)

    def save_script_revision(self, revision: ScriptRevision) -> None:
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    "INSERT INTO script_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        revision.id, revision.project_id, revision.run_id,
                        revision.base_script_id, revision.version,
                        json.dumps(revision.payload, ensure_ascii=False),
                        revision.review_status, revision.review_note, revision.created_by,
                        revision.created_at, revision.updated_at, revision.lock_version,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise RepositoryConflictError("script revision conflict") from exc

    def get_latest_script_revision(self, run_id: str) -> ScriptRevision | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM script_revisions WHERE run_id = ? ORDER BY version DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return ScriptRevision(
            id=row["id"], project_id=row["project_id"], run_id=row["run_id"],
            base_script_id=row["base_script_id"], version=row["version"],
            payload=json.loads(row["payload_json"]), review_status=row["review_status"],
            review_note=row["review_note"], created_by=row["created_by"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            lock_version=row["lock_version"],
        )

    def save_claimed_run(self, run: Run, worker_id: str, claim_epoch: int) -> None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """UPDATE runs SET status = ?, attempt = ?, error_code = ?, error_message = ?,
                   updated_at = ?, claimed_by = ?, claimed_at = ?, lease_until = ?,
                   heartbeat_at = ?, lock_version = lock_version + 1
                   WHERE id = ? AND claimed_by = ? AND claim_epoch = ?
                     AND lease_until != '' AND lease_until >= ? AND status != ?""",
                (run.status.value, run.attempt, run.error_code, run.error_message,
                 run.updated_at, run.claimed_by, run.claimed_at, run.lease_until,
                 run.heartbeat_at, run.id, worker_id, claim_epoch, now,
                 RunStatus.CANCELLED.value),
            )
            if cursor.rowcount != 1:
                raise RepositoryConflictError("worker no longer owns this run lease")

    def complete_run_with_script(
        self, run: Run, script: ScriptVersion, worker_id: str, claim_epoch: int
    ) -> None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO script_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    script.id,
                    script.project_id,
                    script.run_id,
                    script.brief_version_id,
                    script.version,
                    json.dumps(script.payload, ensure_ascii=False),
                    json.dumps(script.evidence, ensure_ascii=False),
                    script.created_at,
                ),
            )
            cursor = connection.execute(
                """UPDATE runs SET status = ?, attempt = ?, error_code = ?, error_message = ?,
                   updated_at = ?, claimed_by = '', claimed_at = '', lease_until = '',
                   heartbeat_at = '', lock_version = lock_version + 1
                   WHERE id = ? AND claimed_by = ? AND claim_epoch = ?
                     AND lease_until != '' AND lease_until >= ? AND status != ?""",
                (
                    run.status.value,
                    run.attempt,
                    run.error_code,
                    run.error_message,
                    run.updated_at,
                    run.id,
                    worker_id,
                    claim_epoch,
                    now,
                    RunStatus.CANCELLED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise RepositoryConflictError("cancelled run cannot be completed")

    def claim_run(self, run_id: str, worker_id: str, lease_seconds: int = 120) -> Run | None:
        now = datetime.now(UTC)
        now_text = now.isoformat(timespec="milliseconds")
        lease_text = (now + timedelta(seconds=lease_seconds)).isoformat(timespec="milliseconds")
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """UPDATE runs SET status = ?, claimed_by = ?, claimed_at = ?,
                   lease_until = ?, heartbeat_at = ?, updated_at = ?, lock_version = lock_version + 1
                   , claim_epoch = claim_epoch + 1
                   WHERE id = ? AND (
                     status IN (?, ?) OR
                     (status IN (?, ?, ?, ?, ?) AND lease_until != '' AND lease_until < ?)
                   )""",
                (
                    RunStatus.CLAIMED.value,
                    worker_id,
                    now_text,
                    lease_text,
                    now_text,
                    now_text,
                    run_id,
                    RunStatus.PENDING.value,
                    RunStatus.RETRYING.value,
                    RunStatus.CLAIMED.value,
                    RunStatus.RUNNING.value,
                    RunStatus.RETRIEVING.value,
                    RunStatus.GENERATING.value,
                    RunStatus.VALIDATING.value,
                    now_text,
                ),
            )
            connection.commit()
            if cursor.rowcount != 1:
                return None
        return self.get_run(run_id)

    def heartbeat_run(self, run_id: str, worker_id: str, claim_epoch: int, lease_seconds: int = 120) -> bool:
        now = datetime.now(UTC)
        now_text = now.isoformat(timespec="milliseconds")
        lease_text = (now + timedelta(seconds=lease_seconds)).isoformat(timespec="milliseconds")
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """UPDATE runs SET heartbeat_at = ?, lease_until = ?, updated_at = ?,
                   lock_version = lock_version + 1
                   WHERE id = ? AND claimed_by = ? AND claim_epoch = ?
                     AND status NOT IN (?, ?, ?)""",
                (
                    now_text,
                    lease_text,
                    now_text,
                    run_id,
                    worker_id,
                    claim_epoch,
                    RunStatus.PASSED.value,
                    RunStatus.FAILED.value,
                    RunStatus.CANCELLED.value,
                ),
            )
        return cursor.rowcount == 1

    def record_failed_job(self, run_id: str, reason: str) -> None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO failed_jobs(id, run_id, reason, created_at, resolved_at)
                   VALUES (?, ?, ?, ?, '')
                   ON CONFLICT(run_id) DO UPDATE SET reason = excluded.reason,
                   created_at = excluded.created_at, resolved_at = ''""",
                (f"failed_{uuid4().hex}", run_id, reason[:4000], now),
            )

    @staticmethod
    def _row_to_failed_job(row: sqlite3.Row | None) -> FailedJob | None:
        return FailedJob(**dict(row)) if row else None

    def list_failed_jobs(
        self, workspace_id: str, *, include_resolved: bool = False, limit: int = 100
    ) -> list[FailedJob]:
        resolved_clause = "" if include_resolved else "AND failed_jobs.resolved_at = ''"
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""SELECT failed_jobs.* FROM failed_jobs
                    JOIN runs ON runs.id = failed_jobs.run_id
                    WHERE runs.workspace_id = ? {resolved_clause}
                    ORDER BY failed_jobs.created_at DESC, failed_jobs.id DESC
                    LIMIT ?""",
                (workspace_id, limit),
            ).fetchall()
        return [FailedJob(**dict(row)) for row in rows]

    def get_failed_job(self, failed_job_id: str, workspace_id: str) -> FailedJob | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT failed_jobs.* FROM failed_jobs
                   JOIN runs ON runs.id = failed_jobs.run_id
                   WHERE failed_jobs.id = ? AND runs.workspace_id = ?""",
                (failed_job_id, workspace_id),
            ).fetchone()
        return self._row_to_failed_job(row)

    def retry_failed_job(
        self, failed_job_id: str, workspace_id: str, *, max_attempts: int
    ) -> Run | None:
        with self._failed_job_retry_lock:
            return self._retry_failed_job_transaction(
                failed_job_id,
                workspace_id,
                max_attempts=max_attempts,
            )

    def _retry_failed_job_transaction(
        self, failed_job_id: str, workspace_id: str, *, max_attempts: int
    ) -> Run | None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT failed_jobs.run_id FROM failed_jobs
                   JOIN runs ON runs.id = failed_jobs.run_id
                   WHERE failed_jobs.id = ? AND runs.workspace_id = ?
                     AND failed_jobs.resolved_at = '' AND runs.status = ?
                     AND runs.attempt < ?""",
                (failed_job_id, workspace_id, RunStatus.FAILED.value, max_attempts),
            ).fetchone()
            if not row:
                connection.rollback()
                return None
            run_id = str(row["run_id"])
            run_update = connection.execute(
                """UPDATE runs SET status = ?, attempt = attempt + 1,
                   error_code = '', error_message = '', claimed_by = '', claimed_at = '',
                   lease_until = '', heartbeat_at = '', updated_at = ?,
                   lock_version = lock_version + 1
                   WHERE id = ? AND workspace_id = ? AND status = ? AND attempt < ?""",
                (
                    RunStatus.RETRYING.value,
                    now,
                    run_id,
                    workspace_id,
                    RunStatus.FAILED.value,
                    max_attempts,
                ),
            )
            job_update = connection.execute(
                """UPDATE failed_jobs SET resolved_at = ?
                   WHERE id = ? AND resolved_at = ''""",
                (now, failed_job_id),
            )
            if run_update.rowcount != 1 or job_update.rowcount != 1:
                connection.rollback()
                return None
            connection.commit()
        return self.get_run(run_id)

    def resolve_failed_job(self, failed_job_id: str, workspace_id: str) -> FailedJob | None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT failed_jobs.resolved_at FROM failed_jobs
                   JOIN runs ON runs.id = failed_jobs.run_id
                   WHERE failed_jobs.id = ? AND runs.workspace_id = ?""",
                (failed_job_id, workspace_id),
            ).fetchone()
            if not row:
                connection.rollback()
                return None
            if not row["resolved_at"]:
                connection.execute(
                    "UPDATE failed_jobs SET resolved_at = ? WHERE id = ?",
                    (now, failed_job_id),
                )
            connection.commit()
        return self.get_failed_job(failed_job_id, workspace_id)

    def reconcile_expired_runs(
        self, *, max_attempts: int, limit: int = 100
    ) -> tuple[list[str], list[str]]:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        requeued: list[str] = []
        failed: list[str] = []
        active = (
            RunStatus.CLAIMED.value,
            RunStatus.RUNNING.value,
            RunStatus.RETRIEVING.value,
            RunStatus.GENERATING.value,
            RunStatus.VALIDATING.value,
        )
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                f"""SELECT id, attempt FROM runs
                    WHERE status IN ({",".join("?" for _ in active)})
                      AND lease_until != '' AND lease_until < ?
                    ORDER BY lease_until LIMIT ?""",
                (*active, now, limit),
            ).fetchall()
            for row in rows:
                if int(row["attempt"]) >= max_attempts:
                    connection.execute(
                        """UPDATE runs SET status = ?, error_code = ?, error_message = ?,
                           lease_until = '', updated_at = ?, lock_version = lock_version + 1
                           WHERE id = ?""",
                        (
                            RunStatus.FAILED.value,
                            "lease_exhausted",
                            "运行租约过期且已达到最大尝试次数",
                            now,
                            row["id"],
                        ),
                    )
                    connection.execute(
                        """INSERT OR IGNORE INTO failed_jobs
                           (id, run_id, reason, created_at, resolved_at) VALUES (?, ?, ?, ?, '')""",
                        (f"failed_{uuid4().hex}", row["id"], "lease_exhausted", now),
                    )
                    failed.append(str(row["id"]))
                else:
                    connection.execute(
                        """UPDATE runs SET status = ?, attempt = attempt + 1, claimed_by = '',
                           claimed_at = '', lease_until = '', heartbeat_at = '', updated_at = ?,
                           lock_version = lock_version + 1 WHERE id = ?""",
                        (RunStatus.RETRYING.value, now, row["id"]),
                    )
                    requeued.append(str(row["id"]))
            connection.commit()
        return requeued, failed
