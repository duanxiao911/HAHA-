"""Persistence ports and a deterministic SQLite development adapter."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from haha_core.domain import BriefVersion, FailedJob, Project, Run, RunStatus, ScriptVersion


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
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower():
                    return None
                raise
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
