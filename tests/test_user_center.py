from __future__ import annotations

from fastapi.testclient import TestClient

from haha_api.main import create_app
from haha_core.repository import SQLiteCreatorRepository
from haha_user_center.service import UserCenterService


def _repository() -> SQLiteCreatorRepository:
    repository = SQLiteCreatorRepository(":memory:")
    repository.ensure_identity("member-a", "workspace-a", role="owner")
    repository.ensure_identity("member-b", "workspace-a", role="viewer")
    return repository


def test_bootstrap_creates_private_account_and_one_welcome_notification() -> None:
    service = UserCenterService(_repository())
    first = service.bootstrap("member-a", "workspace-a")
    second = service.bootstrap("member-a", "workspace-a")

    assert first["account"]["profile_visibility"] == "private"
    assert first["preferences"]["history_enabled"] is True
    assert first["summary"]["unread_notifications"] == 1
    assert len(second["notifications"]) == 1


def test_library_follow_and_history_are_durable_and_idempotent() -> None:
    service = UserCenterService(_repository())
    service.bootstrap("member-a", "workspace-a")
    for _ in range(2):
        service.set_library_item(
            "member-a", "workspace-a", kind_value="bookmark", target_id="video-1",
            title="苗绣的一天", target_href="/content/video-1", active=True,
        )
        service.set_follow(
            "member-a", "workspace-a", target_id="person-1", display_name="银匠阿婆",
            target_href="/inheritors/person-1", active=True,
        )
        service.record_history(
            "member-a", "workspace-a", content_id="video-1", title="苗绣的一天",
            target_href="/content/video-1", progress_seconds=92, duration_seconds=100,
        )
    snapshot = service.snapshot("member-a", "workspace-a")
    assert snapshot["summary"]["bookmarks"] == 1
    assert snapshot["summary"]["following"] == 1
    assert snapshot["summary"]["history"] == 1
    assert snapshot["history"][0]["completed"] is True


def test_history_opt_out_stops_new_writes_and_clear_is_owner_scoped() -> None:
    service = UserCenterService(_repository())
    service.bootstrap("member-a", "workspace-a")
    service.bootstrap("member-b", "workspace-a")
    service.record_history("member-b", "workspace-a", content_id="other", title="他人记录", target_href="/content/other", progress_seconds=1, duration_seconds=10)
    service.update_preferences(
        "member-a", "workspace-a", history_enabled=False,
        recommendation_enabled=True, personalization_enabled=False,
        notification_enabled=True,
    )
    assert service.record_history("member-a", "workspace-a", content_id="blocked", title="不应保存", target_href="/content/blocked", progress_seconds=1, duration_seconds=10) is None
    assert service.clear_history("member-a", "workspace-a") == 0
    assert service.snapshot("member-b", "workspace-a")["summary"]["history"] == 1


def test_user_center_api_persists_profile_assets_and_blocks_cross_user_notice() -> None:
    client = TestClient(create_app(_repository()))
    headers_a = {"X-User-ID": "member-a", "X-Workspace-ID": "workspace-a"}
    headers_b = {"X-User-ID": "member-b", "X-Workspace-ID": "workspace-a"}
    initial = client.get("/api/user-center", headers=headers_a)
    assert initial.status_code == 200
    notice_id = initial.json()["notifications"][0]["id"]

    profile = client.patch("/api/user-center/profile", headers=headers_a, json={
        "display_name": "非遗探索者", "bio": "关注传统工艺", "region": "贵州",
        "profile_visibility": "members",
    })
    assert profile.status_code == 200
    assert profile.json()["account"]["region"] == "贵州"
    saved = client.put("/api/user-center/library/want_to_learn/video-1", headers=headers_a, json={
        "title": "苗绣的一天", "target_href": "/content/video-1",
    })
    assert saved.status_code == 200
    assert saved.json()["summary"]["want_to_learn"] == 1
    assert client.post(f"/api/user-center/notifications/{notice_id}/read", headers=headers_b).status_code == 404
    assert client.post(f"/api/user-center/notifications/{notice_id}/read", headers=headers_a).status_code == 200


def test_user_center_api_rejects_external_links_and_unknown_library_kind() -> None:
    client = TestClient(create_app(_repository()))
    headers = {"X-User-ID": "member-a", "X-Workspace-ID": "workspace-a"}
    assert client.put("/api/user-center/library/bookmark/a", headers=headers, json={
        "title": "外链", "target_href": "https://example.com",
    }).status_code == 400
    assert client.put("/api/user-center/library/invalid/a", headers=headers, json={
        "title": "无效类型", "target_href": "/content/a",
    }).status_code == 400
