"""SQLAlchemy persistence adapter for the Gate C2 community domain."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    and_,
    create_engine,
    delete,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from haha_community.domain import (
    CommunityComment,
    CommunityConflictError,
    KnowledgeAnnotation,
    Submission,
    SubmissionEvent,
)
from haha_community.seed import CATALOG_VERSION, seed_entities

community_metadata = MetaData()

community_entities = Table(
    "community_entities",
    community_metadata,
    Column("id", String(200), primary_key=True),
    Column("workspace_id", String(100), primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("slug", String(200), nullable=False),
    Column("title", String(300), nullable=False),
    Column("status", String(32), nullable=False),
    Column("provenance", String(32), nullable=False),
    Column("catalog_version", String(64), nullable=False),
    Column("payload_json", JSON, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("workspace_id", "kind", "slug", name="uq_community_entity_slug"),
)
Index("ix_community_entity_feed", community_entities.c.workspace_id, community_entities.c.kind, community_entities.c.status)

community_respects = Table(
    "community_respects",
    community_metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("content_id", String(200), nullable=False),
    Column("created_at", String(40), nullable=False),
    UniqueConstraint("user_id", "workspace_id", "content_id", name="uq_community_respect_owner"),
)

community_comments = Table(
    "community_comments",
    community_metadata,
    Column("id", String(64), primary_key=True),
    Column("workspace_id", String(100), nullable=False),
    Column("content_id", String(200), nullable=False),
    Column("author_user_id", String(200), nullable=False),
    Column("author_name", String(200), nullable=False),
    Column("body", String(1000), nullable=False),
    Column("parent_id", String(64), nullable=False, server_default=""),
    Column("status", String(20), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)
Index("ix_community_comment_content", community_comments.c.workspace_id, community_comments.c.content_id, community_comments.c.created_at)

community_annotations = Table(
    "community_annotations",
    community_metadata,
    Column("id", String(64), primary_key=True),
    Column("workspace_id", String(100), nullable=False),
    Column("content_id", String(200), nullable=False),
    Column("author_user_id", String(200), nullable=False),
    Column("author_name", String(200), nullable=False),
    Column("timestamp_seconds", Integer, nullable=False),
    Column("body", String(1000), nullable=False),
    Column("kind", String(40), nullable=False),
    Column("source_ids_json", JSON, nullable=False),
    Column("verification_status", String(20), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)
Index("ix_community_annotation_content", community_annotations.c.workspace_id, community_annotations.c.content_id, community_annotations.c.timestamp_seconds)

community_submissions = Table(
    "community_submissions",
    community_metadata,
    Column("id", String(64), primary_key=True),
    Column("workspace_id", String(100), nullable=False),
    Column("owner_user_id", String(200), nullable=False),
    Column("submission_type", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("version", Integer, nullable=False),
    Column("title", String(200), nullable=False),
    Column("summary", String(4000), nullable=False),
    Column("payload_json", JSON, nullable=False),
    Column("reviewer_note", String(2000), nullable=False, server_default=""),
    Column("reviewed_by", String(200), nullable=False, server_default=""),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    Column("submitted_at", String(40), nullable=False, server_default=""),
    Column("published_at", String(40), nullable=False, server_default=""),
)
Index("ix_community_submission_owner", community_submissions.c.workspace_id, community_submissions.c.owner_user_id, community_submissions.c.updated_at)
Index("ix_community_submission_queue", community_submissions.c.workspace_id, community_submissions.c.status, community_submissions.c.updated_at)

community_submission_revisions = Table(
    "community_submission_revisions",
    community_metadata,
    Column("id", String(100), primary_key=True),
    Column("submission_id", String(64), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("version", Integer, nullable=False),
    Column("payload_json", JSON, nullable=False),
    Column("created_at", String(40), nullable=False),
    UniqueConstraint("submission_id", "version", name="uq_community_submission_revision"),
    ForeignKeyConstraint(
        ["submission_id"], ["community_submissions.id"], ondelete="CASCADE"
    ),
)

community_submission_events = Table(
    "community_submission_events",
    community_metadata,
    Column("id", String(64), primary_key=True),
    Column("submission_id", String(64), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("actor_user_id", String(200), nullable=False),
    Column("event_type", String(100), nullable=False),
    Column("from_status", String(32), nullable=False),
    Column("to_status", String(32), nullable=False),
    Column("detail_json", JSON, nullable=False),
    Column("created_at", String(40), nullable=False),
    ForeignKeyConstraint(
        ["submission_id"], ["community_submissions.id"], ondelete="CASCADE"
    ),
)
Index("ix_community_submission_event", community_submission_events.c.submission_id, community_submission_events.c.created_at)

community_import_receipts = Table(
    "community_import_receipts",
    community_metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("fingerprint", String(64), nullable=False),
    Column("result_json", JSON, nullable=False),
    Column("created_at", String(40), nullable=False),
    UniqueConstraint("user_id", "workspace_id", "fingerprint", name="uq_community_import_fingerprint"),
)


def _engine(database_url: str) -> Engine:
    options: dict[str, Any] = {"pool_pre_ping": True}
    if database_url == "sqlite+pysqlite:///:memory:":
        options.update(connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(database_url, **options)


def _url_from_path(path: str | Path) -> str:
    if str(path) == ":memory:":
        return "sqlite+pysqlite:///:memory:"
    return f"sqlite+pysqlite:///{Path(path).resolve().as_posix()}"


class SQLAlchemyCommunityRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine = _engine(database_url)
        if create_schema:
            community_metadata.create_all(self.engine)

    @classmethod
    def for_sqlite_path(cls, path: str | Path) -> SQLAlchemyCommunityRepository:
        return cls(_url_from_path(path), create_schema=True)

    def ping(self) -> bool:
        with self.engine.connect() as connection:
            return connection.scalar(select(1)) == 1

    @staticmethod
    def _insert_ignore(connection: Any, table: Table, values: dict[str, object], columns: list[str]) -> None:
        elements = [getattr(table.c, name) for name in columns]
        if connection.dialect.name == "postgresql":
            connection.execute(postgresql_insert(table).values(**values).on_conflict_do_nothing(index_elements=elements))
        elif connection.dialect.name == "sqlite":
            connection.execute(sqlite_insert(table).values(**values).on_conflict_do_nothing(index_elements=elements))
        else:
            criteria = [getattr(table.c, name) == values[name] for name in columns]
            if not connection.scalar(select(table.c.id).where(*criteria)):
                connection.execute(table.insert().values(**values))

    def ensure_seed(self, workspace_id: str) -> None:
        with self.engine.begin() as connection:
            for item in seed_entities(workspace_id):
                payload = item["payload"]
                assert isinstance(payload, dict)
                self._insert_ignore(
                    connection,
                    community_entities,
                    {
                        "id": str(payload["id"]),
                        "workspace_id": workspace_id,
                        "kind": str(item["kind"]),
                        "slug": str(item["slug"]),
                        "title": str(item["title"]),
                        "status": str(item["status"]),
                        "provenance": "demo_seed",
                        "catalog_version": CATALOG_VERSION,
                        "payload_json": payload,
                        "created_at": str(payload["createdAt"]),
                        "updated_at": str(payload["updatedAt"]),
                    },
                    ["id", "workspace_id"],
                )

    def list_entities(self, workspace_id: str, kind: str = "") -> list[dict[str, object]]:
        query = select(community_entities).where(community_entities.c.workspace_id == workspace_id)
        if kind:
            query = query.where(community_entities.c.kind == kind)
        query = query.order_by(community_entities.c.kind, community_entities.c.created_at, community_entities.c.id)
        with self.engine.connect() as connection:
            return [dict(row._mapping) for row in connection.execute(query)]

    def get_entity(self, workspace_id: str, kind: str, entity_id: str) -> dict[str, object] | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(community_entities).where(
                community_entities.c.workspace_id == workspace_id,
                community_entities.c.kind == kind,
                community_entities.c.id == entity_id,
            )).first()
            return dict(row._mapping) if row else None

    def save_entity(
        self,
        workspace_id: str,
        kind: str,
        entity_id: str,
        slug: str,
        title: str,
        status: str,
        provenance: str,
        payload: dict[str, object],
        created_at: str,
        updated_at: str,
    ) -> None:
        values = {
            "id": entity_id,
            "workspace_id": workspace_id,
            "kind": kind,
            "slug": slug,
            "title": title,
            "status": status,
            "provenance": provenance,
            "catalog_version": CATALOG_VERSION,
            "payload_json": payload,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        with self.engine.begin() as connection:
            existing = connection.scalar(select(community_entities.c.id).where(
                community_entities.c.id == entity_id,
                community_entities.c.workspace_id == workspace_id,
            ))
            if existing:
                connection.execute(update(community_entities).where(
                    community_entities.c.id == entity_id,
                    community_entities.c.workspace_id == workspace_id,
                ).values(**values))
            else:
                connection.execute(community_entities.insert().values(**values))

    def set_respect(self, user_id: str, workspace_id: str, content_id: str, active: bool) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        with self.engine.begin() as connection:
            criteria = and_(
                community_respects.c.user_id == user_id,
                community_respects.c.workspace_id == workspace_id,
                community_respects.c.content_id == content_id,
            )
            if not active:
                connection.execute(delete(community_respects).where(criteria))
                return
            self._insert_ignore(connection, community_respects, {
                "id": f"respect_{uuid4().hex}", "user_id": user_id,
                "workspace_id": workspace_id, "content_id": content_id,
                "created_at": datetime.now(UTC).isoformat(timespec="milliseconds"),
            }, ["user_id", "workspace_id", "content_id"])

    def list_respects(self, user_id: str, workspace_id: str) -> list[str]:
        with self.engine.connect() as connection:
            return list(connection.scalars(select(community_respects.c.content_id).where(
                community_respects.c.user_id == user_id,
                community_respects.c.workspace_id == workspace_id,
            )))

    def save_comment(self, comment: CommunityComment) -> None:
        values = asdict(comment)
        with self.engine.begin() as connection:
            existing = connection.scalar(select(community_comments.c.id).where(community_comments.c.id == comment.id))
            if existing:
                connection.execute(update(community_comments).where(community_comments.c.id == comment.id).values(**values))
            else:
                connection.execute(community_comments.insert().values(**values))

    def list_comments(self, workspace_id: str) -> list[CommunityComment]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(community_comments).where(
                community_comments.c.workspace_id == workspace_id
            ).order_by(community_comments.c.created_at)).all()
            return [CommunityComment(**dict(row._mapping)) for row in rows]

    def get_comment(self, comment_id: str, workspace_id: str) -> CommunityComment | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(community_comments).where(
                community_comments.c.id == comment_id,
                community_comments.c.workspace_id == workspace_id,
            )).first()
            return CommunityComment(**dict(row._mapping)) if row else None

    def save_annotation(self, annotation: KnowledgeAnnotation) -> None:
        values = asdict(annotation)
        values["source_ids_json"] = json.loads(annotation.source_ids_json)
        with self.engine.begin() as connection:
            existing = connection.scalar(select(community_annotations.c.id).where(community_annotations.c.id == annotation.id))
            if existing:
                connection.execute(update(community_annotations).where(community_annotations.c.id == annotation.id).values(**values))
            else:
                connection.execute(community_annotations.insert().values(**values))

    def list_annotations(self, workspace_id: str) -> list[KnowledgeAnnotation]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(community_annotations).where(
                community_annotations.c.workspace_id == workspace_id
            ).order_by(community_annotations.c.timestamp_seconds)).all()
            result = []
            for row in rows:
                values = dict(row._mapping)
                values["source_ids_json"] = json.dumps(values["source_ids_json"], ensure_ascii=False)
                result.append(KnowledgeAnnotation(**values))
            return result

    def get_annotation(self, annotation_id: str, workspace_id: str) -> KnowledgeAnnotation | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(community_annotations).where(
                community_annotations.c.id == annotation_id,
                community_annotations.c.workspace_id == workspace_id,
            )).first()
            if not row:
                return None
            values = dict(row._mapping)
            values["source_ids_json"] = json.dumps(values["source_ids_json"], ensure_ascii=False)
            return KnowledgeAnnotation(**values)

    @staticmethod
    def _save_submission(connection: Any, submission: Submission) -> None:
        values = asdict(submission)
        values["payload_json"] = json.loads(submission.payload_json)
        existing = connection.execute(select(
            community_submissions.c.version,
            community_submissions.c.payload_json,
        ).where(
            community_submissions.c.id == submission.id,
            community_submissions.c.workspace_id == submission.workspace_id,
        )).first()
        if not existing:
            if submission.version != 1:
                raise CommunityConflictError("新投稿必须从版本 1 开始")
            connection.execute(community_submissions.insert().values(**values))
            return
        if (
            int(existing.version) == submission.version
            and existing.payload_json == values["payload_json"]
        ):
            return
        result = connection.execute(update(community_submissions).where(
            community_submissions.c.id == submission.id,
            community_submissions.c.workspace_id == submission.workspace_id,
            community_submissions.c.version == submission.version - 1,
        ).values(**values))
        if result.rowcount != 1:
            raise CommunityConflictError("投稿已被其他会话修改，请刷新后重试")

    def save_submission(self, submission: Submission) -> None:
        with self.engine.begin() as connection:
            self._save_submission(connection, submission)

    @staticmethod
    def _submission(row: Any) -> Submission:
        values = dict(row._mapping)
        values["payload_json"] = json.dumps(values["payload_json"], ensure_ascii=False, sort_keys=True)
        return Submission(**values)

    def get_submission(self, submission_id: str, workspace_id: str) -> Submission | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(community_submissions).where(
                community_submissions.c.id == submission_id,
                community_submissions.c.workspace_id == workspace_id,
            )).first()
            return self._submission(row) if row else None

    def list_submissions(self, workspace_id: str, *, owner_user_id: str = "") -> list[Submission]:
        query = select(community_submissions).where(community_submissions.c.workspace_id == workspace_id)
        if owner_user_id:
            query = query.where(community_submissions.c.owner_user_id == owner_user_id)
        query = query.order_by(community_submissions.c.updated_at.desc())
        with self.engine.connect() as connection:
            return [self._submission(row) for row in connection.execute(query)]

    def save_submission_revision(self, submission: Submission) -> None:
        with self.engine.begin() as connection:
            self._insert_ignore(connection, community_submission_revisions, {
                "id": f"{submission.id}:v{submission.version}",
                "submission_id": submission.id,
                "workspace_id": submission.workspace_id,
                "version": submission.version,
                "payload_json": json.loads(submission.payload_json),
                "created_at": submission.updated_at,
            }, ["submission_id", "version"])

    def save_submission_event(self, event: SubmissionEvent) -> None:
        values = asdict(event)
        values["detail_json"] = json.loads(event.detail_json)
        with self.engine.begin() as connection:
            connection.execute(community_submission_events.insert().values(**values))

    def save_submission_change(
        self, submission: Submission, event: SubmissionEvent
    ) -> None:
        """Atomically persist current state, immutable revision, and audit event."""
        event_values = asdict(event)
        event_values["detail_json"] = json.loads(event.detail_json)
        with self.engine.begin() as connection:
            self._save_submission(connection, submission)
            self._insert_ignore(connection, community_submission_revisions, {
                "id": f"{submission.id}:v{submission.version}",
                "submission_id": submission.id,
                "workspace_id": submission.workspace_id,
                "version": submission.version,
                "payload_json": json.loads(submission.payload_json),
                "created_at": submission.updated_at,
            }, ["submission_id", "version"])
            connection.execute(
                community_submission_events.insert().values(**event_values)
            )

    def list_submission_events(self, submission_id: str, workspace_id: str) -> list[SubmissionEvent]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(community_submission_events).where(
                community_submission_events.c.submission_id == submission_id,
                community_submission_events.c.workspace_id == workspace_id,
            ).order_by(community_submission_events.c.created_at)).all()
            result = []
            for row in rows:
                values = dict(row._mapping)
                values["detail_json"] = json.dumps(values["detail_json"], ensure_ascii=False, sort_keys=True)
                result.append(SubmissionEvent(**values))
            return result

    def find_import_receipt(self, user_id: str, workspace_id: str, fingerprint: str) -> dict[str, object] | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(community_import_receipts).where(
                community_import_receipts.c.user_id == user_id,
                community_import_receipts.c.workspace_id == workspace_id,
                community_import_receipts.c.fingerprint == fingerprint,
            )).first()
            return dict(row._mapping) if row else None

    def save_import_receipt(self, receipt_id: str, user_id: str, workspace_id: str, fingerprint: str, result: dict[str, object], created_at: str) -> None:
        with self.engine.begin() as connection:
            self._insert_ignore(connection, community_import_receipts, {
                "id": receipt_id, "user_id": user_id, "workspace_id": workspace_id,
                "fingerprint": fingerprint, "result_json": result, "created_at": created_at,
            }, ["user_id", "workspace_id", "fingerprint"])
