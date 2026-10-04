"""Framework-independent domain contracts for production creator runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class RunStatus(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    RETRIEVING = "RETRIEVING"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"


TERMINAL_RUN_STATUSES = frozenset(
    {RunStatus.PASSED, RunStatus.FAILED, RunStatus.CANCELLED}
)

ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PENDING: frozenset({RunStatus.CLAIMED, RunStatus.CANCELLED}),
    RunStatus.CLAIMED: frozenset({RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.RUNNING: frozenset({RunStatus.RETRIEVING, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.RETRIEVING: frozenset({RunStatus.GENERATING, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.GENERATING: frozenset({RunStatus.VALIDATING, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.VALIDATING: frozenset(
        {RunStatus.PASSED, RunStatus.FAILED, RunStatus.RETRYING, RunStatus.CANCELLED}
    ),
    RunStatus.RETRYING: frozenset({RunStatus.CLAIMED, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.PASSED: frozenset(),
    RunStatus.FAILED: frozenset({RunStatus.RETRYING}),
    RunStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class Project:
    id: str
    workspace_id: str
    title: str
    created_at: str
    updated_at: str

    @classmethod
    def create(cls, title: str, workspace_id: str) -> Project:
        now = utc_now()
        return cls(new_id("prj"), workspace_id, title.strip(), now, now)


@dataclass(frozen=True, slots=True)
class User:
    id: str
    email: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Workspace:
    id: str
    name: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Membership:
    user_id: str
    workspace_id: str
    role: str
    created_at: str


@dataclass(frozen=True, slots=True)
class BriefVersion:
    id: str
    project_id: str
    version: int
    craft: str
    story_seed: str
    audience: str
    platform: str
    tone: str
    goal: str
    duration: str
    aspect_ratio: str
    asset_context: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Run:
    id: str
    workspace_id: str
    project_id: str
    brief_version_id: str
    status: RunStatus
    model_preference: str
    idempotency_key: str
    request_fingerprint: str
    attempt: int
    error_code: str
    error_message: str
    created_at: str
    updated_at: str
    claimed_by: str = ""
    claimed_at: str = ""
    lease_until: str = ""
    heartbeat_at: str = ""
    lock_version: int = 0

    @classmethod
    def create(
        cls,
        *,
        workspace_id: str,
        project_id: str,
        brief_version_id: str,
        model_preference: str,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> Run:
        now = utc_now()
        return cls(
            id=new_id("run"),
            workspace_id=workspace_id,
            project_id=project_id,
            brief_version_id=brief_version_id,
            status=RunStatus.PENDING,
            model_preference=model_preference,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            attempt=1,
            error_code="",
            error_message="",
            created_at=now,
            updated_at=now,
            claimed_by="",
            claimed_at="",
            lease_until="",
            heartbeat_at="",
            lock_version=0,
        )

    def transition(
        self,
        target: RunStatus,
        *,
        error_code: str = "",
        error_message: str = "",
    ) -> Run:
        if target not in ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"非法运行状态转换：{self.status} -> {target}")
        return Run(
            id=self.id,
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            brief_version_id=self.brief_version_id,
            status=target,
            model_preference=self.model_preference,
            idempotency_key=self.idempotency_key,
            request_fingerprint=self.request_fingerprint,
            attempt=self.attempt + (1 if target is RunStatus.RETRYING else 0),
            error_code=error_code,
            error_message=error_message,
            created_at=self.created_at,
            updated_at=utc_now(),
            claimed_by="" if target in TERMINAL_RUN_STATUSES else self.claimed_by,
            claimed_at="" if target in TERMINAL_RUN_STATUSES else self.claimed_at,
            lease_until="" if target in TERMINAL_RUN_STATUSES else self.lease_until,
            heartbeat_at="" if target in TERMINAL_RUN_STATUSES else self.heartbeat_at,
            lock_version=self.lock_version,
        )


@dataclass(frozen=True, slots=True)
class VerificationIssue:
    code: str
    field: str
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    passed: bool
    issues: tuple[VerificationIssue, ...]
    checked_at: str = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class ScriptVersion:
    id: str
    project_id: str
    run_id: str
    brief_version_id: str
    version: int
    payload: dict[str, Any]
    evidence: dict[str, Any]
    created_at: str
