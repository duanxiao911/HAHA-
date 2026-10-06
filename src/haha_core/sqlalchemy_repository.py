"""SQLAlchemy repository used by PostgreSQL production deployments."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Column,
    ForeignKey,
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
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from haha_core.domain import BriefVersion, FailedJob, Project, Run, RunStatus, ScriptVersion
from haha_core.repository import RepositoryConflictError

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
    UniqueConstraint("workspace_id", "project_id", "idempotency_key", name="uq_run_idempotency_scope"),
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

    def save_project(self, project: Project) -> None:
        with self.engine.begin() as connection:
            connection.execute(projects.insert().values(**asdict(project)))

    def ping(self) -> bool:
        with self.engine.connect() as connection:
            return connection.scalar(select(1)) == 1

    def ensure_identity(
        self, user_id: str, workspace_id: str, *, role: str, email: str = "",
        workspace_name: str = "",
    ) -> None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with self.engine.begin() as connection:
            if not connection.scalar(select(users.c.id).where(users.c.id == user_id)):
                connection.execute(users.insert().values(id=user_id, email=email, created_at=now))
            if not connection.scalar(
                select(workspaces.c.id).where(workspaces.c.id == workspace_id)
            ):
                connection.execute(
                    workspaces.insert().values(
                        id=workspace_id, name=workspace_name or workspace_id, created_at=now
                    )
                )
            if not connection.scalar(
                select(memberships.c.user_id).where(
                    memberships.c.user_id == user_id,
                    memberships.c.workspace_id == workspace_id,
                )
            ):
                connection.execute(
                    memberships.insert().values(
                        user_id=user_id,
                        workspace_id=workspace_id,
                        role=role,
                        created_at=now,
                    )
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

    def get_project(self, project_id: str) -> Project | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(projects).where(projects.c.id == project_id)).mappings().first()
        return Project(**row) if row else None

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
            row = connection.execute(
                select(brief_versions).where(brief_versions.c.id == brief_id)
            ).mappings().first()
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
                        statement = statement.where(
                            runs.c.status != RunStatus.CANCELLED.value
                        )
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
            row = connection.execute(
                select(runs).where(
                    runs.c.workspace_id == workspace_id,
                    runs.c.project_id == project_id,
                    runs.c.idempotency_key == key,
                )
            ).mappings().first()
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
            row = connection.execute(
                select(script_versions).where(script_versions.c.run_id == run_id)
            ).mappings().first()
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
                runs.c.status.in_([
                    RunStatus.CLAIMED.value,
                    RunStatus.RUNNING.value,
                    RunStatus.RETRIEVING.value,
                    RunStatus.GENERATING.value,
                    RunStatus.VALIDATING.value,
                ])
                & (runs.c.lease_until != "")
                & (runs.c.lease_until < now_text)
            ),
        )
        with self.engine.begin() as connection:
            result = connection.execute(
                runs.update().where(runs.c.id == run_id, reclaimable).values(
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
                runs.update().where(
                    runs.c.id == run_id,
                    runs.c.claimed_by == worker_id,
                    runs.c.status.not_in([
                        RunStatus.PASSED.value,
                        RunStatus.FAILED.value,
                        RunStatus.CANCELLED.value,
                    ]),
                ).values(
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
                    failed_jobs.update().where(failed_jobs.c.run_id == run_id).values(
                        reason=reason[:4000], created_at=now, resolved_at=""
                    )
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
                    failed_jobs.update().where(failed_jobs.c.run_id == run_id).values(
                        reason=reason[:4000], created_at=now, resolved_at=""
                    )
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
            row = connection.execute(
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
            ).mappings().first()
            if not row:
                return None
            run_id = str(row["run_id"])
            run_update = connection.execute(
                runs.update().where(
                    runs.c.id == run_id,
                    runs.c.workspace_id == workspace_id,
                    runs.c.status == RunStatus.FAILED.value,
                    runs.c.attempt < max_attempts,
                ).values(
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
                failed_jobs.update().where(
                    failed_jobs.c.id == failed_job_id,
                    failed_jobs.c.resolved_at == "",
                ).values(resolved_at=now)
            )
            if run_update.rowcount != 1 or job_update.rowcount != 1:
                raise RepositoryConflictError("failed job retry conflict")
        return self.get_run(run_id)

    def resolve_failed_job(
        self, failed_job_id: str, workspace_id: str
    ) -> FailedJob | None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        with self.engine.begin() as connection:
            row = connection.execute(
                select(failed_jobs.c.resolved_at)
                .join(runs, runs.c.id == failed_jobs.c.run_id)
                .where(
                    failed_jobs.c.id == failed_job_id,
                    runs.c.workspace_id == workspace_id,
                )
                .with_for_update()
            ).mappings().first()
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
                        runs.update().where(runs.c.id == row["id"]).values(
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
                        runs.update().where(runs.c.id == row["id"]).values(
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
