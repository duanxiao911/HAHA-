"""Persistence contract for the Gate C2 community bounded context."""

from __future__ import annotations

from typing import Protocol

from haha_community.domain import (
    CommunityComment,
    KnowledgeAnnotation,
    Submission,
    SubmissionEvent,
)


class CommunityRepository(Protocol):
    def ping(self) -> bool: ...

    def ensure_seed(self, workspace_id: str) -> None: ...

    def list_entities(self, workspace_id: str, kind: str = "") -> list[dict[str, object]]: ...

    def get_entity(
        self, workspace_id: str, kind: str, entity_id: str
    ) -> dict[str, object] | None: ...

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
    ) -> None: ...

    def set_respect(
        self, user_id: str, workspace_id: str, content_id: str, active: bool
    ) -> None: ...

    def list_respects(self, user_id: str, workspace_id: str) -> list[str]: ...

    def save_comment(self, comment: CommunityComment) -> None: ...

    def list_comments(self, workspace_id: str) -> list[CommunityComment]: ...

    def get_comment(self, comment_id: str, workspace_id: str) -> CommunityComment | None: ...

    def save_annotation(self, annotation: KnowledgeAnnotation) -> None: ...

    def list_annotations(self, workspace_id: str) -> list[KnowledgeAnnotation]: ...

    def get_annotation(
        self, annotation_id: str, workspace_id: str
    ) -> KnowledgeAnnotation | None: ...

    def save_submission(self, submission: Submission) -> None: ...

    def get_submission(self, submission_id: str, workspace_id: str) -> Submission | None: ...

    def list_submissions(
        self, workspace_id: str, *, owner_user_id: str = ""
    ) -> list[Submission]: ...

    def save_submission_revision(self, submission: Submission) -> None: ...

    def save_submission_event(self, event: SubmissionEvent) -> None: ...

    def save_submission_change(
        self, submission: Submission, event: SubmissionEvent
    ) -> None: ...

    def list_submission_events(
        self, submission_id: str, workspace_id: str
    ) -> list[SubmissionEvent]: ...

    def find_import_receipt(
        self, user_id: str, workspace_id: str, fingerprint: str
    ) -> dict[str, object] | None: ...

    def save_import_receipt(
        self,
        receipt_id: str,
        user_id: str,
        workspace_id: str,
        fingerprint: str,
        result: dict[str, object],
        created_at: str,
    ) -> None: ...
