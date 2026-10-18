"""Framework-independent Gate C2 domain objects and invariants."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CommunityNotFoundError(RuntimeError):
    pass


class CommunityPermissionError(RuntimeError):
    pass


class CommunityConflictError(RuntimeError):
    pass


class CommunityValidationError(ValueError):
    pass


class SubmissionStatus(StrEnum):
    DRAFT = "draft"
    CHECKING = "checking"
    NEEDS_REVISION = "needs_revision"
    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


CREATOR_TRANSITIONS: dict[SubmissionStatus, frozenset[SubmissionStatus]] = {
    SubmissionStatus.DRAFT: frozenset({SubmissionStatus.CHECKING, SubmissionStatus.ARCHIVED}),
    SubmissionStatus.CHECKING: frozenset(
        {SubmissionStatus.SUBMITTED, SubmissionStatus.NEEDS_REVISION}
    ),
    SubmissionStatus.NEEDS_REVISION: frozenset(
        {SubmissionStatus.CHECKING, SubmissionStatus.ARCHIVED}
    ),
    SubmissionStatus.REJECTED: frozenset(
        {SubmissionStatus.NEEDS_REVISION, SubmissionStatus.ARCHIVED}
    ),
    SubmissionStatus.SUBMITTED: frozenset({SubmissionStatus.ARCHIVED}),
    SubmissionStatus.REVIEWING: frozenset(),
    SubmissionStatus.APPROVED: frozenset(),
    SubmissionStatus.PUBLISHED: frozenset({SubmissionStatus.ARCHIVED}),
    SubmissionStatus.ARCHIVED: frozenset(),
}

REVIEWER_TRANSITIONS: dict[SubmissionStatus, frozenset[SubmissionStatus]] = {
    SubmissionStatus.SUBMITTED: frozenset({SubmissionStatus.REVIEWING}),
    SubmissionStatus.REVIEWING: frozenset(
        {
            SubmissionStatus.APPROVED,
            SubmissionStatus.NEEDS_REVISION,
            SubmissionStatus.REJECTED,
        }
    ),
}

ADMIN_TRANSITIONS: dict[SubmissionStatus, frozenset[SubmissionStatus]] = {
    **REVIEWER_TRANSITIONS,
    SubmissionStatus.APPROVED: frozenset({SubmissionStatus.PUBLISHED}),
}


@dataclass(frozen=True, slots=True)
class Submission:
    id: str
    workspace_id: str
    owner_user_id: str
    submission_type: str
    status: str
    version: int
    title: str
    summary: str
    payload_json: str
    reviewer_note: str
    reviewed_by: str
    created_at: str
    updated_at: str
    submitted_at: str
    published_at: str


@dataclass(frozen=True, slots=True)
class CommunityComment:
    id: str
    workspace_id: str
    content_id: str
    author_user_id: str
    author_name: str
    body: str
    parent_id: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class KnowledgeAnnotation:
    id: str
    workspace_id: str
    content_id: str
    author_user_id: str
    author_name: str
    timestamp_seconds: int
    body: str
    kind: str
    source_ids_json: str
    verification_status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class SubmissionEvent:
    id: str
    submission_id: str
    workspace_id: str
    actor_user_id: str
    event_type: str
    from_status: str
    to_status: str
    detail_json: str
    created_at: str


@dataclass(frozen=True, slots=True)
class CommunityMediaAsset:
    """A server-owned binary attached to a creator submission."""

    id: str
    workspace_id: str
    submission_id: str
    owner_user_id: str
    original_name: str
    kind: str
    declared_mime_type: str
    detected_mime_type: str
    byte_size: int
    sha256: str
    storage_key: str
    status: str
    idempotency_key: str
    created_at: str
    updated_at: str
