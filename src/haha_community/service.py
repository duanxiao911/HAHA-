"""Gate C2 application service for server-authoritative community workflows."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path, PurePath
from uuid import uuid4

from haha_community.domain import (
    ADMIN_TRANSITIONS,
    CREATOR_TRANSITIONS,
    REVIEWER_TRANSITIONS,
    CommunityComment,
    CommunityConflictError,
    CommunityMediaAsset,
    CommunityNotFoundError,
    CommunityPermissionError,
    CommunityValidationError,
    KnowledgeAnnotation,
    Submission,
    SubmissionEvent,
    SubmissionStatus,
)
from haha_community.media_storage import FileSystemMediaStorage, MediaStorageError
from haha_community.repository import CommunityRepository
from haha_user_center.service import UserCenterService

REACTION_LIBRARY_KINDS = frozenset({"bookmark", "want_to_learn", "watch_later"})
ANNOTATION_KINDS = frozenset({"craft", "term", "regional_difference", "source", "correction"})
SUBMISSION_TYPES = frozenset({"video", "article", "project", "event"})
EDITABLE_SUBMISSION_STATUSES = frozenset({"draft", "needs_revision", "rejected"})
CREATOR_ROLES = frozenset({"creator", "contributor"})
REVIEW_ROLES = frozenset({"reviewer", "admin"})
MEDIA_LIMITS = {"video": 100 * 1024 * 1024, "image": 15 * 1024 * 1024}
MEDIA_MIME_TYPES = frozenset({"video/mp4", "video/webm", "image/jpeg", "image/png"})


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(":".join(parts).encode()).hexdigest()[:32]
    return f"{prefix}_{digest}"


def _clean(value: object, *, label: str, maximum: int, required: bool = False) -> str:
    cleaned = str(value or "").strip()
    if required and not cleaned:
        raise CommunityValidationError(f"{label}不能为空")
    if len(cleaned) > maximum:
        raise CommunityValidationError(f"{label}不能超过 {maximum} 个字符")
    return cleaned


def _payload(row: dict[str, object]) -> dict[str, object]:
    value = row.get("payload_json", {})
    if not isinstance(value, dict):
        raise CommunityValidationError("社区目录记录损坏")
    return deepcopy(value)


class CommunityService:
    def __init__(
        self,
        repository: CommunityRepository,
        user_center: UserCenterService,
        media_storage: FileSystemMediaStorage | None = None,
    ) -> None:
        self.repository = repository
        self.user_center = user_center
        self.media_storage = media_storage or FileSystemMediaStorage()

    def _ensure_catalog(self, workspace_id: str) -> None:
        self.repository.ensure_seed(workspace_id)

    def _entity(self, workspace_id: str, kind: str, entity_id: str) -> dict[str, object]:
        self._ensure_catalog(workspace_id)
        row = self.repository.get_entity(workspace_id, kind, entity_id)
        if not row:
            raise CommunityNotFoundError(f"{kind} 不存在")
        return _payload(row)

    def bootstrap(self, user_id: str, workspace_id: str) -> dict[str, object]:
        self._ensure_catalog(workspace_id)
        self._reconcile_published_submissions(workspace_id)
        account = self.user_center.bootstrap(user_id, workspace_id)
        rows = self.repository.list_entities(workspace_id)
        grouped: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            if row.get("kind") == "content" and row.get("status") != "published":
                continue
            grouped.setdefault(str(row["kind"]), []).append(_payload(row))

        library = account.get("library", [])
        follows = account.get("follows", [])
        history = account.get("history", [])
        notifications = account.get("notifications", [])
        profile = account.get("profile", {})
        account_info = account.get("account", {})
        assert isinstance(library, list)
        assert isinstance(follows, list)
        assert isinstance(history, list)
        assert isinstance(notifications, list)
        assert isinstance(profile, dict)
        assert isinstance(account_info, dict)

        library_by_target: dict[str, set[str]] = {}
        for item in library:
            if isinstance(item, dict):
                library_by_target.setdefault(str(item.get("target_id", "")), set()).add(
                    str(item.get("kind", ""))
                )
        followed = {
            str(item.get("target_id", "")) for item in follows if isinstance(item, dict)
        }
        history_by_content = {
            str(item.get("content_id", "")): item for item in history if isinstance(item, dict)
        }
        respects = set(self.repository.list_respects(user_id, workspace_id))
        comments = [
            item
            for item in self.repository.list_comments(workspace_id)
            if item.status == "visible"
        ]
        annotations = [
            item
            for item in self.repository.list_annotations(workspace_id)
            if item.verification_status != "deleted"
        ]

        contents: list[dict[str, object]] = []
        for original in grouped.get("content", []):
            content = deepcopy(original)
            content_id = str(content["id"])
            reactions = set(library_by_target.get(content_id, set()))
            if content_id in respects:
                reactions.add("respect")
            history_item = history_by_content.get(content_id)
            content["viewer"] = {
                "reactions": sorted(reactions),
                "followedCreator": str(content.get("creatorId", "")) in followed,
                "viewed": history_item is not None,
                "watchProgressSeconds": int(history_item.get("progress_seconds", 0))
                if isinstance(history_item, dict)
                else 0,
            }
            contents.append(content)
        contents.sort(key=lambda item: str(item.get("publishedAt", "")), reverse=True)

        role = str(profile.get("active_role", "viewer"))
        display_name = str(account_info.get("display_name", user_id))
        return {
            "runtime": {
                "mode": "api",
                "hydrated": True,
                "persistence": "postgresql",
                "recoveryNotice": None,
                "schemaVersion": 2,
                "dataNotice": "内容与账户状态来自服务端；演示目录仍需正式文化审核。",
            },
            "viewer": {
                "id": user_id,
                "workspaceId": workspace_id,
                "displayName": display_name,
                "authState": "authenticated",
                "roleLabel": role,
            },
            "contents": contents,
            "projects": grouped.get("project", []),
            "people": grouped.get("person", []),
            "regions": grouped.get("region", []),
            "sources": grouped.get("source", []),
            "facts": grouped.get("fact", []),
            "followingPersonIds": sorted(followed),
            "history": [
                {
                    "contentId": str(item.get("content_id", "")),
                    "viewedAt": str(item.get("viewed_at", "")),
                    "progressSeconds": int(item.get("progress_seconds", 0)),
                    "completed": bool(item.get("completed", False)),
                }
                for item in history
                if isinstance(item, dict)
            ],
            "comments": [self._comment_payload(item) for item in comments],
            "annotations": [self._annotation_payload(item) for item in annotations],
            "notifications": [
                {
                    "id": str(item.get("id", "")),
                    "workspaceId": workspace_id,
                    "provenance": "server",
                    "createdAt": str(item.get("created_at", "")),
                    "updatedAt": str(item.get("created_at", "")),
                    "recipientId": user_id,
                    "kind": str(item.get("kind", "system")),
                    "title": str(item.get("title", "")),
                    "body": str(item.get("body", "")),
                    "targetHref": str(item.get("target_href", "")),
                    **({"readAt": item["read_at"]} if item.get("read_at") else {}),
                }
                for item in notifications
                if isinstance(item, dict)
            ],
            "searchHistory": [],
            "drafts": [
                self._submission_payload(item)
                for item in self.repository.list_submissions(
                    workspace_id,
                    owner_user_id="" if role in REVIEW_ROLES else user_id,
                )
            ],
        }

    def content(self, user_id: str, workspace_id: str, content_id: str) -> dict[str, object]:
        return self._content_from_snapshot(user_id, workspace_id, content_id)

    def feed(
        self,
        user_id: str,
        workspace_id: str,
        *,
        mode: str,
        channel_id: str = "",
        region_id: str = "",
        cursor: int = 0,
        limit: int = 20,
    ) -> dict[str, object]:
        snapshot = self.bootstrap(user_id, workspace_id)
        items = list(snapshot["contents"])
        follows = set(snapshot["followingPersonIds"])
        if mode == "following":
            items = [item for item in items if str(item.get("creatorId", "")) in follows]
        elif mode == "learning":
            items = [
                item
                for item in items
                if "want_to_learn" in item.get("viewer", {}).get("reactions", [])
            ]
        elif mode == "nearby" and region_id:
            items = [item for item in items if item.get("regionId") == region_id]
        if channel_id and channel_id not in {"hot", "recommended", "following"}:
            items = [
                item
                for item in items
                if item.get("categoryId") == channel_id or item.get("categoryLabel") == channel_id
            ]
        safe_limit = max(1, min(limit, 50))
        start = max(0, cursor)
        page = items[start : start + safe_limit]
        next_cursor = start + len(page)
        return {
            "items": page,
            "nextCursor": str(next_cursor) if next_cursor < len(items) else None,
            "total": len(items),
        }

    def search(
        self,
        user_id: str,
        workspace_id: str,
        *,
        query: str,
        scope: str,
        sort: str = "relevance",
        cursor: int = 0,
        limit: int = 20,
    ) -> dict[str, object]:
        term = _clean(query, label="搜索词", maximum=100, required=True).casefold()
        if sort not in {"relevance", "latest", "popular", "verified"}:
            raise CommunityValidationError("不支持的搜索排序方式")
        snapshot = self.bootstrap(user_id, workspace_id)
        hits: list[dict[str, object]] = []
        groups = [
            ("content", snapshot["contents"], "title", "/content/"),
            ("project", snapshot["projects"], "name", "/heritage-projects/"),
            ("person", snapshot["people"], "displayName", "/inheritors/"),
            ("region", snapshot["regions"], "name", "/map?region="),
        ]
        for kind, items, title_key, href in groups:
            if scope not in {"all", kind}:
                continue
            for item in items:
                values = [
                    str(item.get(title_key, "")),
                    str(item.get("summary", "")),
                    " ".join(str(value) for value in item.get("tags", [])),
                ]
                if any(term in value.casefold() for value in values):
                    title = str(item.get(title_key, ""))
                    hits.append({
                        "kind": kind,
                        "id": str(item.get("id", "")),
                        "title": title,
                        "summary": str(item.get("summary", item.get("bio", ""))),
                        "href": f"{href}{item.get('id', '')}",
                        "score": 100 if term in title.casefold() else 50,
                        "verificationStatus": item.get("verificationStatus", item.get("trust", {}).get("status")),
                        "_publishedAt": str(item.get("publishedAt", item.get("createdAt", ""))),
                        "_popularity": int(item.get("metrics", {}).get("viewCount", 0)),
                    })
        verification_rank = {
            "verified": 5,
            "inheritor_confirmed": 4,
            "expert_reviewed": 3,
            "pending": 2,
            "disputed": 1,
        }
        if sort == "latest":
            hits.sort(
                key=lambda item: (
                    str(item["_publishedAt"]),
                    int(item["score"]),
                    str(item["title"]),
                ),
                reverse=True,
            )
        elif sort == "popular":
            hits.sort(
                key=lambda item: (
                    int(item["_popularity"]),
                    int(item["score"]),
                    str(item["title"]),
                ),
                reverse=True,
            )
        elif sort == "verified":
            hits.sort(
                key=lambda item: (
                    verification_rank.get(str(item["verificationStatus"]), 0),
                    int(item["score"]),
                    str(item["title"]),
                ),
                reverse=True,
            )
        else:
            hits.sort(key=lambda item: (-int(item["score"]), str(item["title"])))
        for hit in hits:
            hit.pop("_publishedAt", None)
            hit.pop("_popularity", None)
        safe_limit = max(1, min(limit, 50))
        start = max(0, cursor)
        result = hits[start : start + safe_limit]
        next_cursor = start + len(result)
        return {
            "items": result,
            "nextCursor": str(next_cursor) if next_cursor < len(hits) else None,
            "total": len(hits),
        }

    def set_reaction(
        self,
        user_id: str,
        workspace_id: str,
        content_id: str,
        reaction: str,
        active: bool,
    ) -> dict[str, object]:
        content = self._entity(workspace_id, "content", content_id)
        if reaction == "respect":
            self.repository.set_respect(user_id, workspace_id, content_id, active)
        elif reaction in REACTION_LIBRARY_KINDS:
            self.user_center.set_library_item(
                user_id,
                workspace_id,
                kind_value=reaction,
                target_id=content_id,
                title=str(content["title"]),
                target_href=f"/content/{content_id}",
                active=active,
            )
        else:
            raise CommunityValidationError("互动类型无效")
        return self._content_from_snapshot(user_id, workspace_id, content_id)

    def set_follow(
        self,
        user_id: str,
        workspace_id: str,
        person_id: str,
        active: bool,
    ) -> dict[str, object]:
        person = self._entity(workspace_id, "person", person_id)
        self.user_center.set_follow(
            user_id,
            workspace_id,
            target_id=person_id,
            display_name=str(person["displayName"]),
            target_href=f"/inheritors/{person_id}",
            active=active,
        )
        return self.bootstrap(user_id, workspace_id)

    def record_history(
        self,
        user_id: str,
        workspace_id: str,
        content_id: str,
        progress_seconds: int,
    ) -> dict[str, object]:
        content = self._entity(workspace_id, "content", content_id)
        self.user_center.record_history(
            user_id,
            workspace_id,
            content_id=content_id,
            title=str(content["title"]),
            target_href=f"/content/{content_id}",
            progress_seconds=progress_seconds,
            duration_seconds=int(content.get("durationSeconds", 0)),
        )
        return self.bootstrap(user_id, workspace_id)

    def remove_history(self, user_id: str, workspace_id: str, content_id: str) -> None:
        self._entity(workspace_id, "content", content_id)
        self.user_center.remove_history_item(user_id, workspace_id, content_id)

    def create_comment(
        self,
        user_id: str,
        workspace_id: str,
        display_name: str,
        content_id: str,
        body: str,
        parent_id: str = "",
        *,
        comment_id: str = "",
    ) -> dict[str, object]:
        self._entity(workspace_id, "content", content_id)
        parent = _clean(parent_id, label="父评论 ID", maximum=64)
        if parent:
            parent_comment = self.repository.get_comment(parent, workspace_id)
            if not parent_comment or parent_comment.content_id != content_id or parent_comment.status != "visible":
                raise CommunityValidationError("父评论不存在或不可回复")
        now = _now()
        comment = CommunityComment(
            id=comment_id or _id("comment"),
            workspace_id=workspace_id,
            content_id=content_id,
            author_user_id=user_id,
            author_name=_clean(display_name, label="作者名称", maximum=200, required=True),
            body=_clean(body, label="评论", maximum=1000, required=True),
            parent_id=parent,
            status="visible",
            created_at=now,
            updated_at=now,
        )
        self.repository.save_comment(comment)
        return self._comment_payload(comment)

    def delete_comment(self, user_id: str, workspace_id: str, comment_id: str) -> None:
        comment = self.repository.get_comment(comment_id, workspace_id)
        if not comment:
            raise CommunityNotFoundError("评论不存在")
        if comment.author_user_id != user_id:
            raise CommunityPermissionError("只能删除自己的评论")
        if comment.status != "deleted":
            self.repository.save_comment(replace(comment, status="deleted", updated_at=_now()))

    def create_annotation(
        self,
        user_id: str,
        workspace_id: str,
        display_name: str,
        content_id: str,
        *,
        timestamp_seconds: int,
        body: str,
        kind: str,
        source_ids: list[str],
        annotation_id: str = "",
    ) -> dict[str, object]:
        content = self._entity(workspace_id, "content", content_id)
        if kind not in ANNOTATION_KINDS:
            raise CommunityValidationError("知识注释类型无效")
        duration = int(content.get("durationSeconds", 0))
        if timestamp_seconds < 0 or (duration and timestamp_seconds > duration):
            raise CommunityValidationError("知识注释时间点超出内容时长")
        clean_sources = []
        for source_id in source_ids[:10]:
            self._entity(workspace_id, "source", source_id)
            clean_sources.append(source_id)
        now = _now()
        annotation = KnowledgeAnnotation(
            id=annotation_id or _id("annotation"),
            workspace_id=workspace_id,
            content_id=content_id,
            author_user_id=user_id,
            author_name=_clean(display_name, label="作者名称", maximum=200, required=True),
            timestamp_seconds=timestamp_seconds,
            body=_clean(body, label="知识注释", maximum=1000, required=True),
            kind=kind,
            source_ids_json=json.dumps(clean_sources, ensure_ascii=False),
            verification_status="pending",
            created_at=now,
            updated_at=now,
        )
        self.repository.save_annotation(annotation)
        return self._annotation_payload(annotation)

    def delete_annotation(self, user_id: str, workspace_id: str, annotation_id: str) -> None:
        annotation = self.repository.get_annotation(annotation_id, workspace_id)
        if not annotation:
            raise CommunityNotFoundError("知识注释不存在")
        if annotation.author_user_id != user_id:
            raise CommunityPermissionError("只能删除自己的知识注释")
        self.repository.save_annotation(replace(
            annotation,
            body="[已由作者删除]",
            verification_status="deleted",
            updated_at=_now(),
        ))

    def list_submissions(
        self, user_id: str, workspace_id: str, actor_role: str
    ) -> list[dict[str, object]]:
        owner = "" if actor_role in REVIEW_ROLES else user_id
        return [
            self._submission_payload(item)
            for item in self.repository.list_submissions(workspace_id, owner_user_id=owner)
        ]

    def create_submission(
        self,
        user_id: str,
        workspace_id: str,
        actor_role: str,
        submission_type: str,
        title: str = "",
        *,
        submission_id: str = "",
    ) -> dict[str, object]:
        if actor_role not in CREATOR_ROLES:
            raise CommunityPermissionError("请先切换到创作者或知识贡献者身份")
        if submission_type not in SUBMISSION_TYPES:
            raise CommunityValidationError("投稿类型无效")
        now = _now()
        identifier = submission_id or _id("submission")
        payload = {
            "id": identifier,
            "workspaceId": workspace_id,
            "provenance": "server",
            "createdAt": now,
            "updatedAt": now,
            "ownerId": user_id,
            "submissionType": submission_type,
            "status": "draft",
            "version": 1,
            "title": _clean(title, label="标题", maximum=200),
            "summary": "",
            "body": "",
            "projectIds": [],
            "personIds": [],
            "sourceIds": [],
            "tags": [],
            "assets": [],
            "assetOrder": [],
            "aiDisclosure": "none",
        }
        submission = Submission(
            id=identifier,
            workspace_id=workspace_id,
            owner_user_id=user_id,
            submission_type=submission_type,
            status="draft",
            version=1,
            title=str(payload["title"]),
            summary="",
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            reviewer_note="",
            reviewed_by="",
            created_at=now,
            updated_at=now,
            submitted_at="",
            published_at="",
        )
        self.repository.save_submission_change(
            submission,
            self._submission_event(
                submission, user_id, "submission.created", "", "draft", {}
            ),
        )
        return self._submission_payload(submission)

    def update_submission(
        self,
        user_id: str,
        workspace_id: str,
        actor_role: str,
        submission_id: str,
        expected_version: int,
        patch: dict[str, object],
    ) -> dict[str, object]:
        if actor_role not in CREATOR_ROLES:
            raise CommunityPermissionError("当前身份不能编辑投稿")
        current = self._owned_submission(submission_id, user_id, workspace_id)
        if current.status not in EDITABLE_SUBMISSION_STATUSES:
            raise CommunityConflictError("当前投稿状态不可编辑")
        if current.version != expected_version:
            raise CommunityConflictError("投稿版本已变化，请刷新后重试")
        payload = json.loads(current.payload_json)
        allowed = {
            "title", "summary", "body", "categoryId", "regionId", "projectIds",
            "personIds", "sourceIds", "tags", "aiDisclosure",
            "assetOrder",
        }
        if set(patch) - allowed:
            raise CommunityValidationError("投稿包含不允许修改的字段")
        for key, value in patch.items():
            payload[key] = value
        payload = self._validate_submission_payload(payload, workspace_id)
        now = _now()
        payload["updatedAt"] = now
        payload["version"] = current.version + 1
        payload["status"] = current.status
        updated = replace(
            current,
            version=current.version + 1,
            title=str(payload["title"]),
            summary=str(payload["summary"]),
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            updated_at=now,
        )
        self.repository.save_submission_change(
            updated,
            self._submission_event(
                updated,
                user_id,
                "submission.updated",
                current.status,
                current.status,
                {"version": updated.version},
            ),
        )
        return self._submission_payload(updated)

    def upload_submission_asset(
        self,
        user_id: str,
        workspace_id: str,
        actor_role: str,
        submission_id: str,
        expected_version: int,
        *,
        staged_path: Path,
        original_name: str,
        kind: str,
        declared_mime_type: str,
        byte_size: int,
        sha256: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        if actor_role not in CREATOR_ROLES:
            raise CommunityPermissionError("当前身份不能上传投稿素材")
        current = self._owned_submission(submission_id, user_id, workspace_id)
        key = _clean(
            idempotency_key, label="幂等键", maximum=200, required=True
        )
        existing = self.repository.find_media_asset_by_idempotency(
            user_id, workspace_id, key
        )
        if existing:
            if (
                existing.submission_id != submission_id
                or existing.sha256 != sha256
                or existing.byte_size != byte_size
            ):
                raise CommunityConflictError("同一幂等键对应了不同素材")
            self.media_storage.discard(staged_path)
            return self._submission_payload(current)
        if current.status not in EDITABLE_SUBMISSION_STATUSES:
            raise CommunityConflictError("当前投稿状态不可修改素材")
        if current.version != expected_version:
            raise CommunityConflictError("投稿版本已变化，请刷新后重试")
        if kind not in MEDIA_LIMITS:
            raise CommunityValidationError("只支持视频或图片素材")
        if byte_size < 1 or byte_size > MEDIA_LIMITS[kind]:
            raise CommunityValidationError("素材大小超过服务端限制")
        if declared_mime_type not in MEDIA_MIME_TYPES:
            raise CommunityValidationError("素材 MIME 类型不受支持")
        safe_name = PurePath(original_name).name.strip()
        if not safe_name or len(safe_name) > 255 or any(ord(char) < 32 for char in safe_name):
            raise CommunityValidationError("素材文件名无效")
        detected_mime = self._detect_media_type(staged_path)
        if detected_mime != declared_mime_type:
            raise CommunityValidationError("文件内容与声明的 MIME 类型不一致")
        expected_kind = "video" if detected_mime.startswith("video/") else "image"
        if expected_kind != kind:
            raise CommunityValidationError("文件内容与素材类型不一致")
        payload = json.loads(current.payload_json)
        assets = payload.get("assets", [])
        if not isinstance(assets, list) or len(assets) >= 20:
            raise CommunityValidationError("每份投稿最多包含 20 个素材")
        now = _now()
        asset_id = _id("media")
        extension = {
            "video/mp4": "mp4",
            "video/webm": "webm",
            "image/jpeg": "jpg",
            "image/png": "png",
        }[detected_mime]
        workspace_partition = hashlib.sha256(workspace_id.encode()).hexdigest()[:16]
        storage_key = f"{workspace_partition}/{asset_id}.{extension}"
        asset = CommunityMediaAsset(
            id=asset_id,
            workspace_id=workspace_id,
            submission_id=submission_id,
            owner_user_id=user_id,
            original_name=safe_name,
            kind=kind,
            declared_mime_type=declared_mime_type,
            detected_mime_type=detected_mime,
            byte_size=byte_size,
            sha256=sha256,
            storage_key=storage_key,
            status="ready",
            idempotency_key=key,
            created_at=now,
            updated_at=now,
        )
        existing_asset_ids = [
            str(item.get("id", "")) for item in assets if isinstance(item, dict)
        ]
        assets.append(self._media_payload(asset))
        payload["assets"] = assets
        order = payload.get("assetOrder", existing_asset_ids)
        if not isinstance(order, list) or set(order) != set(existing_asset_ids):
            order = existing_asset_ids
        payload["assetOrder"] = [
            item for item in order if isinstance(item, str)
        ] + [asset.id]
        payload["updatedAt"] = now
        payload["version"] = current.version + 1
        updated = replace(
            current,
            version=current.version + 1,
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            updated_at=now,
        )
        try:
            self.media_storage.commit(staged_path, storage_key)
            self.repository.save_media_attachment(
                asset,
                updated,
                self._submission_event(
                    updated,
                    user_id,
                    "submission.media_attached",
                    current.status,
                    current.status,
                    {"asset_id": asset.id, "sha256": asset.sha256},
                ),
            )
        except Exception:
            self.media_storage.delete(storage_key)
            raise
        return self._submission_payload(updated)

    def delete_submission_asset(
        self,
        user_id: str,
        workspace_id: str,
        actor_role: str,
        submission_id: str,
        asset_id: str,
        expected_version: int,
    ) -> dict[str, object]:
        if actor_role not in CREATOR_ROLES:
            raise CommunityPermissionError("当前身份不能移除投稿素材")
        current = self._owned_submission(submission_id, user_id, workspace_id)
        if current.status not in EDITABLE_SUBMISSION_STATUSES:
            raise CommunityConflictError("当前投稿状态不可修改素材")
        if current.version != expected_version:
            raise CommunityConflictError("投稿版本已变化，请刷新后重试")
        asset = self.repository.get_media_asset(asset_id, workspace_id)
        if not asset or asset.submission_id != submission_id:
            raise CommunityNotFoundError("投稿素材不存在")
        if asset.owner_user_id != user_id:
            raise CommunityPermissionError("只能移除自己的投稿素材")
        payload = json.loads(current.payload_json)
        assets = payload.get("assets", [])
        if not isinstance(assets, list):
            raise CommunityValidationError("投稿素材记录损坏")
        now = _now()
        payload["assets"] = [item for item in assets if item.get("id") != asset_id]
        order = payload.get(
            "assetOrder",
            [str(item.get("id", "")) for item in assets if isinstance(item, dict)],
        )
        if not isinstance(order, list):
            order = []
        payload["assetOrder"] = [item for item in order if item != asset_id]
        payload["updatedAt"] = now
        payload["version"] = current.version + 1
        updated = replace(
            current,
            version=current.version + 1,
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            updated_at=now,
        )
        self.repository.delete_media_attachment(
            asset_id,
            updated,
            self._submission_event(
                updated,
                user_id,
                "submission.media_removed",
                current.status,
                current.status,
                {"asset_id": asset_id},
            ),
        )
        self.media_storage.delete(asset.storage_key)
        return self._submission_payload(updated)

    def get_published_media(self, asset_id: str) -> tuple[CommunityMediaAsset, Path]:
        asset = self.repository.get_media_asset(asset_id)
        if not asset or asset.status != "ready":
            raise CommunityNotFoundError("媒体素材不存在")
        submission = self.repository.get_submission(asset.submission_id, asset.workspace_id)
        if not submission or submission.status != SubmissionStatus.PUBLISHED.value:
            raise CommunityNotFoundError("媒体素材尚未发布")
        try:
            return asset, self.media_storage.path_for(asset.storage_key)
        except MediaStorageError as exc:
            raise CommunityNotFoundError("媒体文件不存在") from exc

    def transition_submission(
        self,
        user_id: str,
        workspace_id: str,
        actor_role: str,
        submission_id: str,
        expected_version: int,
        next_status_value: str,
        reviewer_note: str = "",
    ) -> dict[str, object]:
        current = self.repository.get_submission(submission_id, workspace_id)
        if not current:
            raise CommunityNotFoundError("投稿不存在")
        if current.version != expected_version:
            raise CommunityConflictError("投稿版本已变化，请刷新后重试")
        try:
            current_status = SubmissionStatus(current.status)
            next_status = SubmissionStatus(next_status_value)
        except ValueError as exc:
            raise CommunityValidationError("投稿状态无效") from exc

        if current.owner_user_id == user_id:
            if actor_role in REVIEW_ROLES and next_status in REVIEWER_TRANSITIONS.get(current_status, frozenset()):
                raise CommunityPermissionError("不能审核自己的投稿")
            if actor_role not in CREATOR_ROLES:
                raise CommunityPermissionError("当前身份不能处理该投稿")
            allowed = CREATOR_TRANSITIONS.get(current_status, frozenset())
        else:
            if actor_role not in REVIEW_ROLES:
                raise CommunityPermissionError("无权处理其他人的投稿")
            allowed_map = ADMIN_TRANSITIONS if actor_role == "admin" else REVIEWER_TRANSITIONS
            allowed = allowed_map.get(current_status, frozenset())
        if next_status not in allowed:
            raise CommunityConflictError(f"不能从 {current.status} 转换到 {next_status.value}")

        payload = json.loads(current.payload_json)
        if next_status == SubmissionStatus.SUBMITTED:
            self._assert_submission_complete(payload)
        now = _now()
        payload["status"] = next_status.value
        payload["version"] = current.version + 1
        payload["updatedAt"] = now
        note = _clean(reviewer_note, label="审核意见", maximum=2000)
        updated = replace(
            current,
            status=next_status.value,
            version=current.version + 1,
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            reviewer_note=note if actor_role in REVIEW_ROLES else current.reviewer_note,
            reviewed_by=user_id if actor_role in REVIEW_ROLES else current.reviewed_by,
            updated_at=now,
            submitted_at=now if next_status == SubmissionStatus.SUBMITTED else current.submitted_at,
            published_at=now if next_status == SubmissionStatus.PUBLISHED else current.published_at,
        )
        self.repository.save_submission_change(
            updated,
            self._submission_event(
                updated,
                user_id,
                "submission.transitioned",
                current.status,
                next_status.value,
                {"note": note},
            ),
        )
        if actor_role in REVIEW_ROLES:
            self.user_center.create_notification(
                updated.owner_user_id,
                workspace_id,
                kind="review",
                title=f"投稿状态更新：{next_status.value}",
                body=note or "审核状态已经更新。",
                target_href=f"/creator/submissions/new?draft={updated.id}",
                idempotency_key=f"submission:{updated.id}:v{updated.version}",
            )
        if next_status == SubmissionStatus.PUBLISHED:
            self._publish_submission(updated)
        return self._submission_payload(updated)

    def get_submission(
        self, user_id: str, workspace_id: str, actor_role: str, submission_id: str
    ) -> dict[str, object]:
        submission = self.repository.get_submission(submission_id, workspace_id)
        if not submission:
            raise CommunityNotFoundError("投稿不存在")
        if submission.owner_user_id != user_id and actor_role not in REVIEW_ROLES:
            raise CommunityPermissionError("无权查看该投稿")
        result = self._submission_payload(submission)
        result["events"] = [
            {
                **asdict(item),
                "detail": json.loads(item.detail_json),
            }
            for item in self.repository.list_submission_events(submission_id, workspace_id)
        ]
        return result

    def preview_import(
        self, user_id: str, workspace_id: str, local_state: dict[str, object]
    ) -> dict[str, object]:
        self._validate_import(local_state)
        known_contents = {
            str(row["id"]) for row in self.repository.list_entities(workspace_id, "content")
        }
        known_people = {
            str(row["id"]) for row in self.repository.list_entities(workspace_id, "person")
        }
        reactions = local_state.get("reactions", {})
        follows = local_state.get("followingPersonIds", [])
        history = local_state.get("history", [])
        assert isinstance(reactions, dict)
        assert isinstance(follows, list)
        assert isinstance(history, list)
        fingerprint = self._import_fingerprint(local_state)
        return {
            "fingerprint": fingerprint,
            "alreadyImported": self.repository.find_import_receipt(user_id, workspace_id, fingerprint) is not None,
            "importable": {
                "reactionTargets": sum(key in known_contents for key in reactions),
                "follows": sum(str(value) in known_people for value in follows),
                "history": sum(isinstance(item, dict) and str(item.get("contentId", "")) in known_contents for item in history),
                "comments": len(local_state.get("comments", [])),
                "annotations": len(local_state.get("annotations", [])),
                "drafts": len(local_state.get("drafts", [])),
            },
            "ignored": ["本地通知", "搜索历史", "审核通过/发布/核验状态"],
        }

    def commit_import(
        self,
        user_id: str,
        workspace_id: str,
        display_name: str,
        local_state: dict[str, object],
    ) -> dict[str, object]:
        preview = self.preview_import(user_id, workspace_id, local_state)
        fingerprint = str(preview["fingerprint"])
        receipt = self.repository.find_import_receipt(user_id, workspace_id, fingerprint)
        if receipt:
            result = receipt.get("result_json", {})
            return dict(result) if isinstance(result, dict) else {"fingerprint": fingerprint, "alreadyImported": True}
        imported = {"reactions": 0, "follows": 0, "history": 0, "comments": 0, "annotations": 0, "drafts": 0}
        skipped = 0
        reactions = local_state.get("reactions", {})
        assert isinstance(reactions, dict)
        for content_id, values in reactions.items():
            if not self.repository.get_entity(workspace_id, "content", str(content_id)) or not isinstance(values, list):
                skipped += 1
                continue
            for reaction in {str(value) for value in values} & (REACTION_LIBRARY_KINDS | {"respect"}):
                self.set_reaction(user_id, workspace_id, str(content_id), reaction, True)
                imported["reactions"] += 1
        for person_id in local_state.get("followingPersonIds", []):
            if self.repository.get_entity(workspace_id, "person", str(person_id)):
                self.set_follow(user_id, workspace_id, str(person_id), True)
                imported["follows"] += 1
            else:
                skipped += 1
        for item in local_state.get("history", []):
            if not isinstance(item, dict):
                skipped += 1
                continue
            content_id = str(item.get("contentId", ""))
            if not self.repository.get_entity(workspace_id, "content", content_id):
                skipped += 1
                continue
            self.record_history(user_id, workspace_id, content_id, int(item.get("progressSeconds", 0)))
            imported["history"] += 1
        for item in local_state.get("comments", []):
            if not isinstance(item, dict):
                skipped += 1
                continue
            content_id = str(item.get("contentId", ""))
            if not self.repository.get_entity(workspace_id, "content", content_id):
                skipped += 1
                continue
            self.create_comment(
                user_id,
                workspace_id,
                display_name,
                content_id,
                str(item.get("body", "")),
                comment_id=_stable_id("comment", user_id, workspace_id, str(item.get("id", ""))),
            )
            imported["comments"] += 1
        for item in local_state.get("annotations", []):
            if not isinstance(item, dict):
                skipped += 1
                continue
            content_id = str(item.get("contentId", ""))
            if not self.repository.get_entity(workspace_id, "content", content_id):
                skipped += 1
                continue
            try:
                self.create_annotation(
                    user_id,
                    workspace_id,
                    display_name,
                    content_id,
                    timestamp_seconds=int(item.get("timestampSeconds", 0)),
                    body=str(item.get("body", "")),
                    kind=str(item.get("kind", "craft")),
                    source_ids=[str(value) for value in item.get("sourceIds", []) if isinstance(value, str)],
                    annotation_id=_stable_id("annotation", user_id, workspace_id, str(item.get("id", ""))),
                )
                imported["annotations"] += 1
            except (CommunityValidationError, CommunityNotFoundError):
                skipped += 1
        for item in local_state.get("drafts", []):
            if not isinstance(item, dict):
                skipped += 1
                continue
            identifier = _stable_id("submission", user_id, workspace_id, str(item.get("id", "")))
            if self.repository.get_submission(identifier, workspace_id):
                imported["drafts"] += 1
                continue
            draft = self.create_submission(
                user_id,
                workspace_id,
                "creator",
                str(item.get("submissionType", "article")),
                str(item.get("title", "")),
                submission_id=identifier,
            )
            patch = {
                key: item[key]
                for key in ("summary", "body", "categoryId", "regionId", "projectIds", "personIds", "sourceIds", "tags", "aiDisclosure")
                if key in item
            }
            self.update_submission(user_id, workspace_id, "creator", identifier, int(draft["version"]), patch)
            imported["drafts"] += 1
        result = {
            "fingerprint": fingerprint,
            "alreadyImported": False,
            "imported": imported,
            "skipped": skipped,
            "trustBoundary": "本地核验、审核和发布状态均未导入",
        }
        self.repository.save_import_receipt(
            _id("import"), user_id, workspace_id, fingerprint, result, _now()
        )
        return result

    def _content_from_snapshot(self, user_id: str, workspace_id: str, content_id: str) -> dict[str, object]:
        snapshot = self.bootstrap(user_id, workspace_id)
        for item in snapshot["contents"]:
            if item.get("id") == content_id:
                return item
        raise CommunityNotFoundError("内容不存在")

    @staticmethod
    def _comment_payload(comment: CommunityComment) -> dict[str, object]:
        return {
            "id": comment.id,
            "workspaceId": comment.workspace_id,
            "provenance": "server",
            "createdAt": comment.created_at,
            "updatedAt": comment.updated_at,
            "contentId": comment.content_id,
            "authorId": comment.author_user_id,
            "authorName": comment.author_name,
            "body": comment.body,
            **({"parentId": comment.parent_id} if comment.parent_id else {}),
            "status": comment.status,
        }

    @staticmethod
    def _annotation_payload(annotation: KnowledgeAnnotation) -> dict[str, object]:
        return {
            "id": annotation.id,
            "workspaceId": annotation.workspace_id,
            "provenance": "server",
            "createdAt": annotation.created_at,
            "updatedAt": annotation.updated_at,
            "contentId": annotation.content_id,
            "authorId": annotation.author_user_id,
            "authorName": annotation.author_name,
            "timestampSeconds": annotation.timestamp_seconds,
            "body": annotation.body,
            "kind": annotation.kind,
            "verificationStatus": annotation.verification_status,
            "sourceIds": json.loads(annotation.source_ids_json),
        }

    @staticmethod
    def _submission_payload(submission: Submission) -> dict[str, object]:
        payload = json.loads(submission.payload_json)
        payload.update({
            "status": submission.status,
            "version": submission.version,
            "reviewerNote": submission.reviewer_note,
            "reviewedBy": submission.reviewed_by,
            "updatedAt": submission.updated_at,
        })
        if submission.submitted_at:
            payload["submittedAt"] = submission.submitted_at
        if submission.published_at:
            payload["publishedAt"] = submission.published_at
        return payload

    def _owned_submission(self, submission_id: str, user_id: str, workspace_id: str) -> Submission:
        submission = self.repository.get_submission(submission_id, workspace_id)
        if not submission:
            raise CommunityNotFoundError("投稿不存在")
        if submission.owner_user_id != user_id:
            raise CommunityPermissionError("无权编辑该投稿")
        return submission

    def _validate_submission_payload(self, payload: dict[str, object], workspace_id: str) -> dict[str, object]:
        payload["title"] = _clean(payload.get("title"), label="标题", maximum=200)
        payload["summary"] = _clean(payload.get("summary"), label="简介", maximum=4000)
        payload["body"] = _clean(payload.get("body"), label="正文", maximum=50_000)
        disclosure = str(payload.get("aiDisclosure", "none"))
        if disclosure not in {"none", "assisted", "generated"}:
            raise CommunityValidationError("AI 披露类型无效")
        payload["aiDisclosure"] = disclosure
        for key, kind, maximum in (
            ("projectIds", "project", 20),
            ("personIds", "person", 20),
            ("sourceIds", "source", 20),
        ):
            values = payload.get(key, [])
            if not isinstance(values, list) or len(values) > maximum:
                raise CommunityValidationError(f"{key} 格式或数量无效")
            cleaned = []
            for value in values:
                identifier = _clean(value, label=key, maximum=200, required=True)
                self._entity(workspace_id, kind, identifier)
                cleaned.append(identifier)
            payload[key] = list(dict.fromkeys(cleaned))
        region_id = _clean(payload.get("regionId"), label="地区", maximum=200)
        if region_id:
            self._entity(workspace_id, "region", region_id)
        payload["regionId"] = region_id or None
        category_id = _clean(payload.get("categoryId"), label="分类", maximum=100)
        payload["categoryId"] = category_id or None
        tags = payload.get("tags", [])
        if not isinstance(tags, list) or len(tags) > 12:
            raise CommunityValidationError("标签格式或数量无效")
        payload["tags"] = list(dict.fromkeys(_clean(value, label="标签", maximum=40, required=True) for value in tags))
        assets = payload.get("assets", [])
        if not isinstance(assets, list) or len(assets) > 20:
            raise CommunityValidationError("素材记录格式或数量无效")
        if any(not isinstance(item, dict) for item in assets):
            raise CommunityValidationError("素材记录格式无效")
        asset_ids = [str(item.get("id", "")) for item in assets]
        if any(not identifier for identifier in asset_ids) or len(set(asset_ids)) != len(asset_ids):
            raise CommunityValidationError("素材标识无效或重复")
        order = payload.get("assetOrder", asset_ids)
        if not isinstance(order, list) or any(not isinstance(item, str) for item in order):
            raise CommunityValidationError("素材展示顺序格式无效")
        if len(order) != len(set(order)) or set(order) != set(asset_ids):
            raise CommunityValidationError("素材展示顺序必须完整且不能重复")
        payload["assetOrder"] = order
        return payload

    @staticmethod
    def _assert_submission_complete(payload: dict[str, object]) -> None:
        missing = []
        if not str(payload.get("title", "")).strip():
            missing.append("标题")
        if not str(payload.get("summary", "")).strip():
            missing.append("简介")
        if payload.get("submissionType") == "article" and not str(payload.get("body", "")).strip():
            missing.append("图文正文")
        if not payload.get("projectIds"):
            missing.append("关联项目")
        if not payload.get("sourceIds"):
            missing.append("事实来源")
        assets = payload.get("assets")
        if not isinstance(assets, list) or not assets:
            missing.append("已上传素材")
        elif any(item.get("localOnly") is not False for item in assets):
            missing.append("服务端已验证素材")
        if missing:
            raise CommunityValidationError(f"提交前仍需补充：{'、'.join(missing)}")

    def _submission_event(
        self,
        submission: Submission,
        actor_user_id: str,
        event_type: str,
        from_status: str,
        to_status: str,
        detail: dict[str, object],
    ) -> SubmissionEvent:
        return SubmissionEvent(
            id=_id("subevent"),
            submission_id=submission.id,
            workspace_id=submission.workspace_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            detail_json=json.dumps(detail, ensure_ascii=False, sort_keys=True),
            created_at=_now(),
        )

    @staticmethod
    def _detect_media_type(path: Path) -> str:
        with path.open("rb") as handle:
            header = handle.read(32)
        if len(header) >= 12 and header[4:8] == b"ftyp":
            return "video/mp4"
        if header.startswith(b"\x1aE\xdf\xa3"):
            return "video/webm"
        if header.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        raise CommunityValidationError("无法识别或不支持该媒体文件内容")

    @staticmethod
    def _media_payload(asset: CommunityMediaAsset) -> dict[str, object]:
        return {
            "id": asset.id,
            "name": asset.original_name,
            "kind": asset.kind,
            "mimeType": asset.detected_mime_type,
            "sizeBytes": asset.byte_size,
            "sha256": asset.sha256,
            "status": asset.status,
            "scanStatus": "signature_verified",
            "url": f"/api/backend/api/community/media/{asset.id}",
            "localOnly": False,
        }

    def _publish_submission(self, submission: Submission) -> None:
        payload = json.loads(submission.payload_json)
        now = submission.published_at or _now()
        person_id = f"account-{submission.owner_user_id}"
        person = self.repository.get_entity(submission.workspace_id, "person", person_id)
        if not person:
            person_payload = {
                "id": person_id,
                "workspaceId": submission.workspace_id,
                "provenance": "account",
                "createdAt": now,
                "updatedAt": now,
                "slug": person_id,
                "displayName": "HAHA 创作者",
                "role": "creator",
                "bio": "平台账户创作者。",
                "regionId": payload.get("regionId") or "region-guizhou",
                "projectIds": payload.get("projectIds", []),
                "verified": False,
                "demoLabel": "内部账户创作者，尚未完成公开身份核验",
            }
            self.repository.save_entity(
                submission.workspace_id, "person", person_id, person_id,
                str(person_payload["displayName"]), "active", "account",
                person_payload, now, now,
            )
            person = self.repository.get_entity(submission.workspace_id, "person", person_id)
        assert person is not None
        person_payload = _payload(person)
        content_id = f"content-{submission.id}"
        content_type = {
            "video": "short_video", "article": "image_story",
            "project": "heritage_project", "event": "event",
        }[submission.submission_type]
        source_payloads = [
            self._entity(submission.workspace_id, "source", source_id)
            for source_id in payload.get("sourceIds", [])
        ]
        uploaded_assets = payload.get("assets", [])
        if not isinstance(uploaded_assets, list):
            uploaded_assets = []
        order = payload.get("assetOrder", [])
        order_index = {
            asset_id: index for index, asset_id in enumerate(order)
        } if isinstance(order, list) else {}
        uploaded_assets = sorted(
            uploaded_assets,
            key=lambda item: order_index.get(str(item.get("id", "")), len(order_index))
            if isinstance(item, dict) else len(order_index),
        )
        published_media = [
            {
                "id": item["id"],
                "kind": item["kind"],
                "url": item["url"],
                "alt": f"{submission.title}的投稿素材",
                "mimeType": item["mimeType"],
            }
            for item in uploaded_assets
            if isinstance(item, dict) and item.get("localOnly") is False
        ]
        cover = {
            "id": f"asset-{content_id}-cover",
            "kind": "image",
            "alt": f"{submission.title}的元数据占位封面",
            "placeholder": {"mark": submission.title[:1] or "稿", "tone": "red"},
        }
        image_cover = next(
            (item for item in published_media if item.get("kind") == "image"), None
        )
        if image_cover:
            cover = dict(image_cover)
        content = {
            "id": content_id,
            "workspaceId": submission.workspace_id,
            "provenance": "creator_submission",
            "createdAt": submission.created_at,
            "updatedAt": now,
            "slug": content_id,
            "contentType": content_type,
            "title": submission.title,
            "summary": submission.summary,
            "cover": cover,
            "creatorId": person_id,
            "creator": person_payload,
            "categoryId": payload.get("categoryId") or "community",
            "categoryLabel": payload.get("categoryId") or "社区投稿",
            "regionId": payload.get("regionId") or "region-guizhou",
            "regionLabel": "社区投稿",
            "projectIds": payload.get("projectIds", []),
            "personIds": payload.get("personIds", []),
            "tags": payload.get("tags", []),
            "metrics": {"viewCount": 0, "interactionCount": 0, "commentCount": 0, "bookmarkCount": 0},
            "reactionCounts": {"bookmark": 0, "want_to_learn": 0, "respect": 0, "watch_later": 0},
            "trust": {"status": "pending", "label": "已审核发布 · 事实待持续复核", "sourceCount": len(source_payloads), "checkedAt": now, "aiAssisted": payload.get("aiDisclosure") != "none"},
            "viewer": {"reactions": [], "followedCreator": False, "viewed": False, "watchProgressSeconds": 0},
            "publishedAt": now,
            "body": str(payload.get("body") or submission.summary),
            "submissionVersion": submission.version,
            "media": published_media or [cover],
            "claims": [],
            "sources": source_payloads,
            "relatedContentIds": [],
        }
        self.repository.save_entity(
            submission.workspace_id, "content", content_id, content_id,
            submission.title, "published", "creator_submission", content,
            submission.created_at, now,
        )

    def _reconcile_published_submissions(self, workspace_id: str) -> None:
        """Repair a public projection after a prior publish write was interrupted."""
        for submission in self.repository.list_submissions(workspace_id):
            if submission.status != SubmissionStatus.PUBLISHED.value:
                continue
            content = self.repository.get_entity(
                workspace_id, "content", f"content-{submission.id}"
            )
            current_version = -1
            if content:
                current_version = int(_payload(content).get("submissionVersion", -1))
            if current_version != submission.version:
                self._publish_submission(submission)

    def _validate_import(self, local_state: dict[str, object]) -> None:
        encoded = json.dumps(local_state, ensure_ascii=False, sort_keys=True).encode()
        if len(encoded) > 1_000_000:
            raise CommunityValidationError("本地档案超过 1 MB 导入上限")
        if local_state.get("schemaVersion") != 1:
            raise CommunityValidationError("只支持本地档案 schemaVersion 1")
        limits = {
            "followingPersonIds": 100,
            "history": 200,
            "comments": 500,
            "annotations": 500,
            "drafts": 100,
        }
        for key, maximum in limits.items():
            value = local_state.get(key, [])
            if not isinstance(value, list) or len(value) > maximum:
                raise CommunityValidationError(f"{key} 格式或数量超限")
        reactions = local_state.get("reactions", {})
        if not isinstance(reactions, dict) or len(reactions) > 500:
            raise CommunityValidationError("reactions 格式或数量超限")

    @staticmethod
    def _import_fingerprint(local_state: dict[str, object]) -> str:
        encoded = json.dumps(local_state, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
