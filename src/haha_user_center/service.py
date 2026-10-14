"""Application service for the durable public account center."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from uuid import uuid4

from haha_identity.service import IdentityService
from haha_user_center.domain import (
    LibraryItem,
    LibraryKind,
    ProfileVisibility,
    UserCenterAuditEvent,
    UserFollow,
    UserNotification,
    WatchHistoryItem,
)
from haha_user_center.repository import UserCenterRepository


class UserCenterNotFoundError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _clean(value: str, *, label: str, maximum: int, required: bool = False) -> str:
    cleaned = value.strip()
    if required and not cleaned:
        raise ValueError(f"{label}不能为空")
    if len(cleaned) > maximum:
        raise ValueError(f"{label}不能超过 {maximum} 个字符")
    return cleaned


def _target_id(value: str) -> str:
    return _clean(value, label="目标 ID", maximum=200, required=True)


def _href(value: str) -> str:
    cleaned = _clean(value, label="目标链接", maximum=500)
    if cleaned and (not cleaned.startswith("/") or cleaned.startswith("//")):
        raise ValueError("目标链接必须是站内相对路径")
    return cleaned


class UserCenterService:
    def __init__(self, repository: UserCenterRepository) -> None:
        self.repository = repository
        self.identity = IdentityService(repository)

    def bootstrap(self, user_id: str, workspace_id: str) -> dict[str, object]:
        self.identity.bootstrap(user_id, workspace_id)
        self.repository.ensure_user_center_settings(user_id, workspace_id)
        self._ensure_welcome_notification(user_id, workspace_id)
        return self.snapshot(user_id, workspace_id)

    def snapshot(self, user_id: str, workspace_id: str) -> dict[str, object]:
        identity = self.identity.snapshot(user_id, workspace_id)
        profile = identity["profile"]
        assert isinstance(profile, dict)
        settings = self.repository.ensure_user_center_settings(user_id, workspace_id)
        library = self.repository.list_library_items(user_id, workspace_id)
        follows = self.repository.list_user_follows(user_id, workspace_id)
        history = self.repository.list_watch_history(user_id, workspace_id)
        notifications = self.repository.list_user_notifications(user_id, workspace_id)
        unread = sum(1 for item in notifications if not item.read_at)
        open_tasks = sum(
            1 for item in identity["tasks"]
            if isinstance(item, dict) and item.get("status") == "open"
        )
        next_learning = next(
            (item for item in library if item.kind == LibraryKind.WANT_TO_LEARN.value),
            None,
        )
        return {
            **identity,
            "account": {
                "display_name": profile["display_name"],
                "bio": settings.bio,
                "region": settings.region,
                "profile_visibility": settings.profile_visibility,
            },
            "preferences": {
                "history_enabled": settings.history_enabled,
                "recommendation_enabled": settings.recommendation_enabled,
                "personalization_enabled": profile["personalization_enabled"],
                "notification_enabled": settings.notification_enabled,
            },
            "library": [asdict(item) for item in library],
            "follows": [asdict(item) for item in follows],
            "history": [asdict(item) for item in history],
            "notifications": [asdict(item) for item in notifications],
            "summary": {
                "bookmarks": sum(item.kind == LibraryKind.BOOKMARK.value for item in library),
                "want_to_learn": sum(item.kind == LibraryKind.WANT_TO_LEARN.value for item in library),
                "watch_later": sum(item.kind == LibraryKind.WATCH_LATER.value for item in library),
                "following": len(follows),
                "history": len(history),
                "unread_notifications": unread,
                "open_tasks": open_tasks,
            },
            "today": {
                "continue_watching": asdict(history[0]) if history else None,
                "next_learning": asdict(next_learning) if next_learning else None,
                "open_tasks": open_tasks,
                "unread_notifications": unread,
            },
        }

    def update_profile(
        self,
        user_id: str,
        workspace_id: str,
        *,
        display_name: str,
        bio: str,
        region: str,
        profile_visibility: str,
    ) -> dict[str, object]:
        visibility = ProfileVisibility(profile_visibility)
        profile = self.repository.ensure_user_profile(user_id, workspace_id)
        settings = self.repository.ensure_user_center_settings(user_id, workspace_id)
        now = _now()
        self.repository.save_user_profile(replace(
            profile,
            display_name=_clean(
                display_name, label="显示名称", maximum=50, required=True
            ),
            updated_at=now,
        ))
        self.repository.save_user_center_settings(replace(
            settings,
            bio=_clean(bio, label="个人简介", maximum=300),
            region=_clean(region, label="所在地区", maximum=100),
            profile_visibility=visibility.value,
            updated_at=now,
        ))
        self._audit(user_id, workspace_id, "user_center.profile.updated", {
            "profile_visibility": visibility.value,
        })
        return self.snapshot(user_id, workspace_id)

    def update_preferences(
        self,
        user_id: str,
        workspace_id: str,
        *,
        history_enabled: bool,
        recommendation_enabled: bool,
        personalization_enabled: bool,
        notification_enabled: bool,
    ) -> dict[str, object]:
        settings = self.repository.ensure_user_center_settings(user_id, workspace_id)
        profile = self.repository.ensure_user_profile(user_id, workspace_id)
        now = _now()
        self.repository.save_user_center_settings(replace(
            settings,
            history_enabled=history_enabled,
            recommendation_enabled=recommendation_enabled,
            notification_enabled=notification_enabled,
            updated_at=now,
        ))
        self.repository.save_user_profile(replace(
            profile,
            personalization_enabled=personalization_enabled,
            updated_at=now,
        ))
        self._audit(user_id, workspace_id, "user_center.preferences.updated", {
            "history_enabled": history_enabled,
            "recommendation_enabled": recommendation_enabled,
            "personalization_enabled": personalization_enabled,
            "notification_enabled": notification_enabled,
        })
        return self.snapshot(user_id, workspace_id)

    def set_library_item(
        self,
        user_id: str,
        workspace_id: str,
        *,
        kind_value: str,
        target_id: str,
        title: str,
        target_href: str,
        active: bool,
    ) -> dict[str, object]:
        kind = LibraryKind(kind_value)
        target = _target_id(target_id)
        if active:
            now = _now()
            existing = next((item for item in self.repository.list_library_items(
                user_id, workspace_id
            ) if item.kind == kind.value and item.target_id == target), None)
            self.repository.save_library_item(LibraryItem(
                id=existing.id if existing else _id("library"),
                user_id=user_id,
                workspace_id=workspace_id,
                kind=kind.value,
                target_id=target,
                title=_clean(title, label="内容标题", maximum=200, required=True),
                target_href=_href(target_href),
                created_at=existing.created_at if existing else now,
                updated_at=now,
            ))
        else:
            self.repository.delete_library_item(
                user_id, workspace_id, kind.value, target
            )
        return self.snapshot(user_id, workspace_id)

    def set_follow(
        self,
        user_id: str,
        workspace_id: str,
        *,
        target_id: str,
        display_name: str,
        target_href: str,
        active: bool,
    ) -> dict[str, object]:
        target = _target_id(target_id)
        if active:
            now = _now()
            existing = next((item for item in self.repository.list_user_follows(
                user_id, workspace_id
            ) if item.target_id == target), None)
            self.repository.save_user_follow(UserFollow(
                id=existing.id if existing else _id("follow"),
                user_id=user_id,
                workspace_id=workspace_id,
                target_id=target,
                display_name=_clean(
                    display_name, label="关注对象名称", maximum=200, required=True
                ),
                target_href=_href(target_href),
                created_at=existing.created_at if existing else now,
                updated_at=now,
            ))
        else:
            self.repository.delete_user_follow(user_id, workspace_id, target)
        return self.snapshot(user_id, workspace_id)

    def record_history(
        self,
        user_id: str,
        workspace_id: str,
        *,
        content_id: str,
        title: str,
        target_href: str,
        progress_seconds: int,
        duration_seconds: int,
    ) -> WatchHistoryItem | None:
        settings = self.repository.ensure_user_center_settings(user_id, workspace_id)
        if not settings.history_enabled:
            return None
        content = _target_id(content_id)
        duration = max(0, min(duration_seconds, 24 * 60 * 60))
        progress = max(0, min(progress_seconds, duration if duration else progress_seconds))
        now = _now()
        existing = next((item for item in self.repository.list_watch_history(
            user_id, workspace_id
        ) if item.content_id == content), None)
        item = WatchHistoryItem(
            id=existing.id if existing else _id("history"),
            user_id=user_id,
            workspace_id=workspace_id,
            content_id=content,
            title=_clean(title, label="内容标题", maximum=200, required=True),
            target_href=_href(target_href),
            progress_seconds=progress,
            duration_seconds=duration,
            completed=bool(duration and progress / duration >= 0.9),
            viewed_at=now,
            updated_at=now,
        )
        self.repository.save_watch_history(item)
        return item

    def remove_history_item(
        self, user_id: str, workspace_id: str, content_id: str
    ) -> None:
        self.repository.delete_watch_history_item(
            user_id, workspace_id, _target_id(content_id)
        )

    def clear_history(self, user_id: str, workspace_id: str) -> int:
        removed = self.repository.clear_watch_history(user_id, workspace_id)
        self._audit(user_id, workspace_id, "user_center.history.cleared", {
            "removed_count": removed,
        })
        return removed

    def mark_notification_read(
        self, notification_id: str, user_id: str, workspace_id: str
    ) -> UserNotification:
        notification = self.repository.get_user_notification(
            notification_id, user_id, workspace_id
        )
        if not notification:
            raise UserCenterNotFoundError("通知不存在")
        if notification.read_at:
            return notification
        updated = replace(notification, read_at=_now())
        self.repository.save_user_notification(updated)
        return updated

    def delete_notification(
        self, notification_id: str, user_id: str, workspace_id: str
    ) -> None:
        if not self.repository.get_user_notification(
            notification_id, user_id, workspace_id
        ):
            raise UserCenterNotFoundError("通知不存在")
        self.repository.delete_user_notification(
            notification_id, user_id, workspace_id
        )

    def _ensure_welcome_notification(self, user_id: str, workspace_id: str) -> None:
        digest = hashlib.sha256(
            f"{user_id}:{workspace_id}:welcome".encode()
        ).hexdigest()[:32]
        notification = UserNotification(
            id=f"notice_{digest}",
            user_id=user_id,
            workspace_id=workspace_id,
            kind="system",
            title="文化账户已启用",
            body="收藏、想学、关注和观看进度现在由服务端保存。",
            target_href="/identity",
            read_at="",
            created_at=_now(),
        )
        if not self.repository.get_user_notification(
            notification.id, user_id, workspace_id
        ):
            self.repository.save_user_notification(notification)

    def _audit(
        self,
        user_id: str,
        workspace_id: str,
        event_type: str,
        detail: dict[str, object],
    ) -> None:
        self.repository.save_user_center_audit_event(UserCenterAuditEvent(
            id=_id("ucaudit"),
            user_id=user_id,
            workspace_id=workspace_id,
            event_type=event_type,
            detail_json=json.dumps(detail, ensure_ascii=False, sort_keys=True),
            created_at=_now(),
        ))
