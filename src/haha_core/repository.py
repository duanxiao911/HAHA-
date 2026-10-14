"""Persistence ports and a deterministic SQLite development adapter."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Protocol
from uuid import uuid4

from haha_auth.domain import AuthAuditEvent, AuthCredential, AuthSession
from haha_core.domain import BriefVersion, FailedJob, Project, Run, RunStatus, ScriptVersion
from haha_identity.domain import (
    IdentityAuditEvent,
    IdentityTask,
    RoleApplication,
    RoleGrant,
    UserProfile,
)
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
        self, user_id: str, workspace_id: str, *, role: str, email: str = "",
        workspace_name: str = "",
    ) -> None: ...

    def get_membership_role(self, user_id: str, workspace_id: str) -> str | None: ...

    def save_project(self, project: Project) -> None: ...

    def get_project(self, project_id: str) -> Project | None: ...

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

    def complete_run_with_script(self, run: Run, script: ScriptVersion) -> None: ...

    def claim_run(self, run_id: str, worker_id: str, lease_seconds: int = 120) -> Run | None: ...

    def heartbeat_run(self, run_id: str, worker_id: str, lease_seconds: int = 120) -> bool: ...

    def record_failed_job(self, run_id: str, reason: str) -> None: ...

    def list_failed_jobs(
        self, workspace_id: str, *, include_resolved: bool = False, limit: int = 100
    ) -> list[FailedJob]: ...

    def get_failed_job(self, failed_job_id: str, workspace_id: str) -> FailedJob | None: ...

    def retry_failed_job(
        self, failed_job_id: str, workspace_id: str, *, max_attempts: int
    ) -> Run | None: ...

    def resolve_failed_job(
        self, failed_job_id: str, workspace_id: str
    ) -> FailedJob | None: ...

    def reconcile_expired_runs(
        self, *, max_attempts: int, limit: int = 100
    ) -> tuple[list[str], list[str]]: ...


class SQLiteCreatorRepository:
    """Local adapter with production-shaped schemas; PostgreSQL can replace this port."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._failed_job_retry_lock = Lock()
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
            connection = sqlite3.connect(
                self._memory_uri, uri=True, check_same_thread=False
            )
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
                CREATE TABLE IF NOT EXISTS failed_jobs (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, reason TEXT NOT NULL,
                    created_at TEXT NOT NULL, resolved_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                );
                """
            )
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
        self, user_id: str, workspace_id: str, *, role: str, email: str = "",
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

    def revoke_all_auth_sessions(
        self, user_id: str, workspace_id: str, revoked_at: str
    ) -> int:
        with closing(self._connect()) as connection, connection:
            result = connection.execute(
                """UPDATE auth_sessions SET revoked_at = ?, last_used_at = ?
                   WHERE user_id = ? AND workspace_id = ? AND revoked_at = ''""",
                (revoked_at, revoked_at, user_id, workspace_id),
            )
        return result.rowcount

    def save_auth_audit_event(self, event: AuthAuditEvent) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO auth_audit_events VALUES (?, ?, ?, ?, ?, ?)",
                tuple(asdict(event).values()),
            )

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
                    profile.user_id, profile.workspace_id, profile.display_name,
                    profile.active_role, int(profile.personalization_enabled),
                    profile.created_at, profile.updated_at,
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

    def find_pending_role_application(self, user_id: str, workspace_id: str, role: str) -> RoleApplication | None:
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

    def get_identity_task(self, task_id: str, user_id: str, workspace_id: str) -> IdentityTask | None:
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

    def ensure_user_center_settings(
        self, user_id: str, workspace_id: str
    ) -> UserCenterSettings:
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
                    settings.user_id, settings.workspace_id, settings.bio,
                    settings.region, settings.profile_visibility,
                    int(settings.history_enabled), int(settings.recommendation_enabled),
                    int(settings.notification_enabled), settings.created_at,
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

    def delete_user_follow(
        self, user_id: str, workspace_id: str, target_id: str
    ) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """DELETE FROM user_follows
                   WHERE user_id = ? AND workspace_id = ? AND target_id = ?""",
                (user_id, workspace_id, target_id),
            )

    def list_watch_history(
        self, user_id: str, workspace_id: str
    ) -> list[WatchHistoryItem]:
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

    def delete_watch_history_item(
        self, user_id: str, workspace_id: str, content_id: str
    ) -> None:
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

    def list_user_notifications(
        self, user_id: str, workspace_id: str
    ) -> list[UserNotification]:
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

    def save_project(self, project: Project) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
                (project.id, project.workspace_id, project.title, project.created_at, project.updated_at),
            )

    def get_project(self, project_id: str) -> Project | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return Project(**dict(row)) if row else None

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
                (brief.id, brief.project_id, brief.version, json.dumps(payload, ensure_ascii=False), brief.created_at),
            )

    def get_brief(self, brief_id: str) -> BriefVersion | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute("SELECT * FROM brief_versions WHERE id = ?", (brief_id,)).fetchone()
        if not row:
            return None
        return BriefVersion(
            id=row["id"], project_id=row["project_id"], version=row["version"],
            created_at=row["created_at"], **json.loads(row["payload_json"])
        )

    def save_run(self, run: Run) -> None:
        values = (
            run.id, run.workspace_id, run.project_id, run.brief_version_id, run.status.value,
            run.model_preference, run.idempotency_key, run.request_fingerprint, run.attempt,
            run.error_code, run.error_message, run.created_at, run.updated_at,
            run.claimed_by, run.claimed_at, run.lease_until, run.heartbeat_at, run.lock_version,
        )
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    """INSERT INTO runs (
                       id, workspace_id, project_id, brief_version_id, status,
                       model_preference, idempotency_key, request_fingerprint, attempt,
                       error_code, error_message, created_at, updated_at, claimed_by,
                       claimed_at, lease_until, heartbeat_at, lock_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET status=excluded.status, attempt=excluded.attempt,
                    error_code=excluded.error_code, error_message=excluded.error_message,
                    updated_at=excluded.updated_at, claimed_by=excluded.claimed_by,
                    claimed_at=excluded.claimed_at, lease_until=excluded.lease_until,
                    heartbeat_at=excluded.heartbeat_at, lock_version=excluded.lock_version
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
                       WHERE id = ? AND status IN ({','.join('?' for _ in cancellable)})""",
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
                    script.id, script.project_id, script.run_id, script.brief_version_id,
                    script.version, json.dumps(script.payload, ensure_ascii=False),
                    json.dumps(script.evidence, ensure_ascii=False), script.created_at,
                ),
            )

    def get_script_for_run(self, run_id: str) -> ScriptVersion | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute("SELECT * FROM script_versions WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return ScriptVersion(
            id=row["id"], project_id=row["project_id"], run_id=row["run_id"],
            brief_version_id=row["brief_version_id"], version=row["version"],
            payload=json.loads(row["payload_json"]), evidence=json.loads(row["evidence_json"]),
            created_at=row["created_at"],
        )

    def complete_run_with_script(self, run: Run, script: ScriptVersion) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO script_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    script.id, script.project_id, script.run_id, script.brief_version_id,
                    script.version, json.dumps(script.payload, ensure_ascii=False),
                    json.dumps(script.evidence, ensure_ascii=False), script.created_at,
                ),
            )
            cursor = connection.execute(
                "UPDATE runs SET status = ?, attempt = ?, error_code = ?, error_message = ?, updated_at = ?, lease_until = '', lock_version = lock_version + 1 WHERE id = ? AND status != ?",
                (
                    run.status.value,
                    run.attempt,
                    run.error_code,
                    run.error_message,
                    run.updated_at,
                    run.id,
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
                   WHERE id = ? AND (
                     status IN (?, ?) OR
                     (status IN (?, ?, ?, ?, ?) AND lease_until != '' AND lease_until < ?)
                   )""",
                (
                    RunStatus.CLAIMED.value, worker_id, now_text, lease_text, now_text, now_text,
                    run_id, RunStatus.PENDING.value, RunStatus.RETRYING.value,
                    RunStatus.CLAIMED.value, RunStatus.RUNNING.value, RunStatus.RETRIEVING.value,
                    RunStatus.GENERATING.value, RunStatus.VALIDATING.value, now_text,
                ),
            )
            connection.commit()
            if cursor.rowcount != 1:
                return None
        return self.get_run(run_id)

    def heartbeat_run(self, run_id: str, worker_id: str, lease_seconds: int = 120) -> bool:
        now = datetime.now(UTC)
        now_text = now.isoformat(timespec="milliseconds")
        lease_text = (now + timedelta(seconds=lease_seconds)).isoformat(timespec="milliseconds")
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """UPDATE runs SET heartbeat_at = ?, lease_until = ?, updated_at = ?,
                   lock_version = lock_version + 1
                   WHERE id = ? AND claimed_by = ? AND status NOT IN (?, ?, ?)""",
                (now_text, lease_text, now_text, run_id, worker_id,
                 RunStatus.PASSED.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value),
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

    def resolve_failed_job(
        self, failed_job_id: str, workspace_id: str
    ) -> FailedJob | None:
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
                    WHERE status IN ({','.join('?' for _ in active)})
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
                        (RunStatus.FAILED.value, "lease_exhausted",
                         "运行租约过期且已达到最大尝试次数", now, row["id"]),
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
