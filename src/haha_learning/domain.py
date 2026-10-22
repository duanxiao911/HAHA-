"""Framework-independent contracts for Gate C3 learning state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LearningPermissionError(RuntimeError):
    """The account does not hold an active learner grant."""


class LearningNotFoundError(RuntimeError):
    """A learning resource does not exist in the current workspace."""


class LearningConflictError(RuntimeError):
    """A version, state, or idempotency invariant was violated."""


class LearningTutorUnavailableError(RuntimeError):
    """The real tutor provider is unavailable or returned an unsafe result."""


class LearningTutorRateLimitError(RuntimeError):
    """The account exhausted its rolling tutor request allowance."""


class ProgressStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    PENDING = "pending"
    DEMO_ONLY = "demo_only"
    DISPUTED = "disputed"


class ContributionStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class LearningProfile:
    user_id: str
    workspace_id: str
    timezone: str
    current_streak: int
    longest_streak: int
    last_learning_date: str
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class LearningPath:
    id: str
    workspace_id: str
    title: str
    summary: str
    status: str
    version: int
    provenance: str
    verification_status: str
    source_note: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class LearningUnit:
    id: str
    path_id: str
    workspace_id: str
    position: int
    kind: str
    title: str
    summary: str
    source_id: str
    version: int
    required: bool
    estimated_minutes: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class KnowledgeSource:
    id: str
    workspace_id: str
    title: str
    publisher: str
    source_type: str
    url: str
    version: int
    verification_status: str
    provenance: str
    checked_at: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class PathEnrollment:
    id: str
    user_id: str
    workspace_id: str
    path_id: str
    source_content_id: str
    status: str
    version: int
    enrolled_at: str
    completed_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class LearningProgress:
    id: str
    user_id: str
    workspace_id: str
    path_id: str
    unit_id: str
    status: str
    progress_percent: int
    version: int
    started_at: str
    completed_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class KnowledgeCard:
    id: str
    user_id: str
    workspace_id: str
    path_id: str
    unit_id: str
    topic: str
    body: str
    source_id: str
    source_version: int
    trust_status: str
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Quiz:
    id: str
    workspace_id: str
    path_id: str
    unit_id: str
    title: str
    version: int
    pass_score: int
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class QuizQuestion:
    id: str
    quiz_id: str
    workspace_id: str
    position: int
    prompt: str
    choices_json: str
    correct_choice: int
    explanation: str
    source_id: str
    version: int


@dataclass(frozen=True, slots=True)
class QuizAttempt:
    id: str
    user_id: str
    workspace_id: str
    quiz_id: str
    quiz_version: int
    answers_json: str
    question_snapshot_json: str
    score: int
    passed: bool
    created_at: str


@dataclass(frozen=True, slots=True)
class LearningEvent:
    id: str
    user_id: str
    workspace_id: str
    event_type: str
    entity_type: str
    entity_id: str
    entity_version: int
    idempotency_key: str
    activity_date: str
    payload_json: str
    created_at: str


@dataclass(frozen=True, slots=True)
class DailyTask:
    id: str
    user_id: str
    workspace_id: str
    task_date: str
    kind: str
    title: str
    event_type: str
    target_count: int
    current_count: int
    status: str
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class AchievementDefinition:
    id: str
    workspace_id: str
    code: str
    title: str
    description: str
    event_type: str
    threshold: int
    points: int
    version: int
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class AchievementGrant:
    id: str
    user_id: str
    workspace_id: str
    definition_id: str
    definition_version: int
    triggering_event_id: str
    granted_at: str


@dataclass(frozen=True, slots=True)
class TutorInteraction:
    id: str
    user_id: str
    workspace_id: str
    idempotency_key: str
    request_fingerprint: str
    question: str
    status: str
    answer: str
    citations_json: str
    model: str
    request_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    error_code: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class KnowledgeContribution:
    id: str
    user_id: str
    workspace_id: str
    topic: str
    body: str
    source_title: str
    source_url: str
    source_version: str
    status: str
    version: int
    reviewer_note: str
    reviewed_by: str
    submitted_at: str
    reviewed_at: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class LearningActivityCommit:
    event: LearningEvent
    enrollment: PathEnrollment | None = None
    progress: LearningProgress | None = None
    expected_progress_version: int | None = None
    card: KnowledgeCard | None = None
    expected_card_version: int | None = None
    attempt: QuizAttempt | None = None
    refresh_path_id: str = ""
