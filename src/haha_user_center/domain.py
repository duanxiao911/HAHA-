"""Framework-independent account-center domain objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LibraryKind(StrEnum):
    BOOKMARK = "bookmark"
    WANT_TO_LEARN = "want_to_learn"
    WATCH_LATER = "watch_later"


class ProfileVisibility(StrEnum):
    PRIVATE = "private"
    MEMBERS = "members"
    PUBLIC = "public"


@dataclass(frozen=True, slots=True)
class UserCenterSettings:
    user_id: str
    workspace_id: str
    bio: str
    region: str
    profile_visibility: str
    history_enabled: bool
    recommendation_enabled: bool
    notification_enabled: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class LibraryItem:
    id: str
    user_id: str
    workspace_id: str
    kind: str
    target_id: str
    title: str
    target_href: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class UserFollow:
    id: str
    user_id: str
    workspace_id: str
    target_id: str
    display_name: str
    target_href: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class WatchHistoryItem:
    id: str
    user_id: str
    workspace_id: str
    content_id: str
    title: str
    target_href: str
    progress_seconds: int
    duration_seconds: int
    completed: bool
    viewed_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class UserNotification:
    id: str
    user_id: str
    workspace_id: str
    kind: str
    title: str
    body: str
    target_href: str
    read_at: str
    created_at: str


@dataclass(frozen=True, slots=True)
class UserCenterAuditEvent:
    id: str
    user_id: str
    workspace_id: str
    event_type: str
    detail_json: str
    created_at: str
