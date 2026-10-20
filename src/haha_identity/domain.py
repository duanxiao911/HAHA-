"""Framework-independent identity domain objects and invariants."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BusinessRole(StrEnum):
    VIEWER = "viewer"
    BUYER = "buyer"
    LEARNER = "learner"
    CREATOR = "creator"
    CONTRIBUTOR = "contributor"
    SELLER = "seller"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class RoleApplicationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


CONSUMER_ROLES = frozenset({
    BusinessRole.VIEWER,
    BusinessRole.BUYER,
    BusinessRole.LEARNER,
})
BASE_ROLES = CONSUMER_ROLES
SELF_ACTIVATABLE_ROLES = frozenset({BusinessRole.CREATOR})
APPLICATION_ROLES = frozenset({BusinessRole.CONTRIBUTOR, BusinessRole.SELLER})
CONTROLLED_ROLES = frozenset({BusinessRole.REVIEWER, BusinessRole.ADMIN})
PUBLIC_PROFESSIONAL_ROLES = SELF_ACTIVATABLE_ROLES | APPLICATION_ROLES


@dataclass(frozen=True, slots=True)
class UserProfile:
    user_id: str
    workspace_id: str
    display_name: str
    active_role: str
    personalization_enabled: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class RoleGrant:
    id: str
    user_id: str
    workspace_id: str
    role: str
    status: str
    scope_json: str
    granted_by: str
    created_at: str
    revoked_at: str


@dataclass(frozen=True, slots=True)
class RoleApplication:
    id: str
    user_id: str
    workspace_id: str
    role: str
    status: str
    reason: str
    decision_note: str
    reviewed_by: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class IdentityTask:
    id: str
    user_id: str
    workspace_id: str
    role: str
    kind: str
    title: str
    description: str
    target_href: str
    status: str
    created_at: str
    completed_at: str


@dataclass(frozen=True, slots=True)
class IdentityAuditEvent:
    id: str
    user_id: str
    workspace_id: str
    actor_user_id: str
    event_type: str
    target_role: str
    detail_json: str
    created_at: str
