from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from haha_api.main import create_app
from haha_auth.service import AuthService
from haha_community.domain import CommunityValidationError, SubmissionEvent
from haha_community.media_storage import FileSystemMediaStorage
from haha_community.service import CommunityService
from haha_community.sqlalchemy_repository import SQLAlchemyCommunityRepository
from haha_core.repository import SQLiteCreatorRepository
from haha_identity.domain import RoleGrant
from haha_identity.service import IdentityService
from haha_user_center.service import UserCenterService

WORKSPACE = "community-c2"
SMALL_MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"test-media"
SMALL_PNG = b"\x89PNG\r\n\x1a\n" + b"test-image"


def _headers(user_id: str, workspace_id: str = WORKSPACE) -> dict[str, str]:
    return {"X-User-ID": user_id, "X-Workspace-ID": workspace_id}


def _runtime(media_root: Path | None = None) -> tuple[
    SQLiteCreatorRepository,
    SQLAlchemyCommunityRepository,
    TestClient,
]:
    repository = SQLiteCreatorRepository(":memory:")
    community = SQLAlchemyCommunityRepository.for_sqlite_path(":memory:")
    storage = FileSystemMediaStorage(media_root) if media_root else None
    return repository, community, TestClient(
        create_app(repository, community, media_storage=storage)
    )


def _grant_controlled_role(
    repository: SQLiteCreatorRepository,
    user_id: str,
    role: str,
) -> None:
    repository.ensure_identity(user_id, WORKSPACE, role="owner")
    IdentityService(repository).bootstrap(user_id, WORKSPACE)
    now = datetime.now(UTC).isoformat(timespec="milliseconds")
    repository.save_role_grant(RoleGrant(
        id=f"grant_{uuid4().hex}",
        user_id=user_id,
        workspace_id=WORKSPACE,
        role=role,
        status="active",
        scope_json="{}",
        granted_by="test-admin",
        created_at=now,
        revoked_at="",
    ))


def _activate_creator(client: TestClient, user_id: str) -> None:
    headers = _headers(user_id)
    assert client.get("/api/identity/me", headers=headers).status_code == 200
    assert client.post(
        "/api/identity/roles/creator/activate", headers=headers
    ).status_code == 200
    assert client.post(
        "/api/identity/context", headers=headers, json={"role": "creator"}
    ).status_code == 200


def _complete_draft_payload(snapshot: dict[str, object]) -> dict[str, object]:
    projects = snapshot["projects"]
    regions = snapshot["regions"]
    sources = snapshot["sources"]
    assert isinstance(projects, list)
    assert isinstance(regions, list)
    assert isinstance(sources, list)
    return {
        "title": "一针一线的苗绣故事",
        "summary": "记录材料、针法与传承人的工作过程，并保留事实来源。",
        "body": "这是经来源支持的完整投稿正文，不应在发布时被简介替代。",
        "categoryId": "刺绣",
        "regionId": regions[0]["id"],
        "projectIds": [projects[0]["id"]],
        "personIds": [],
        "sourceIds": [sources[0]["id"]],
        "tags": ["苗绣", "工艺记录"],
        "aiDisclosure": "assisted",
    }


def test_server_catalog_is_workspace_scoped_and_has_explicit_demo_provenance() -> None:
    _, community, client = _runtime()

    first = client.get("/api/community/bootstrap", headers=_headers("viewer-a"))
    second = client.get(
        "/api/community/bootstrap",
        headers=_headers("viewer-b", "community-other"),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["runtime"]["mode"] == "api"
    assert len(first.json()["contents"]) == 10
    assert all(item["provenance"] == "demo_seed" for item in first.json()["contents"])
    assert all(item["workspaceId"] == WORKSPACE for item in first.json()["contents"])
    assert all(
        item["workspaceId"] == "community-other"
        for item in second.json()["contents"]
    )
    assert len(community.list_entities(WORKSPACE, "content")) == 10
    assert len(community.list_entities("community-other", "content")) == 10


def test_search_sort_contract_is_executed_by_the_server() -> None:
    _, _, client = _runtime()
    headers = _headers("search-user")

    latest = client.get(
        "/api/community/search",
        headers=headers,
        params={"q": "演示", "scope": "all", "sort": "latest", "limit": 50},
    )
    popular = client.get(
        "/api/community/search",
        headers=headers,
        params={"q": "工序", "scope": "content", "sort": "popular", "limit": 50},
    )
    invalid = client.get(
        "/api/community/search",
        headers=headers,
        params={"q": "演示", "sort": "not-a-sort"},
    )

    assert latest.status_code == 200
    assert popular.status_code == 200
    assert invalid.status_code == 422
    popular_ids = [item["id"] for item in popular.json()["items"]]
    assert popular_ids == ["content-bamboo-01", "content-ceramics-02"]
    assert all("_publishedAt" not in item for item in latest.json()["items"])
    assert all("_popularity" not in item for item in latest.json()["items"])


def test_c2_endpoints_require_a_valid_jwt_and_ignore_spoofed_workspace_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HAHA_ENVIRONMENT", "development")
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", "c2-jwt-contract-secret-that-is-long-enough-2026")
    monkeypatch.setenv("HAHA_PASSWORD_PBKDF2_ITERATIONS", "1000")
    repository = SQLiteCreatorRepository(":memory:")
    AuthService(repository).bootstrap_account(
        user_id="jwt-viewer",
        workspace_id="jwt-workspace",
        email="jwt-viewer@haha.local",
        password="Strong-C2-Test-Password-2026",
        role="viewer",
    )
    community = SQLAlchemyCommunityRepository.for_sqlite_path(":memory:")
    client = TestClient(create_app(repository, community))

    assert client.get("/api/community/bootstrap").status_code == 401
    assert client.get(
        "/api/community/bootstrap",
        headers={"X-User-ID": "attacker", "X-Workspace-ID": "spoofed"},
    ).status_code == 401

    login = client.post(
        "/api/auth/login",
        json={
            "email": "jwt-viewer@haha.local",
            "password": "Strong-C2-Test-Password-2026",
            "workspace_id": "jwt-workspace",
        },
    )
    assert login.status_code == 200
    headers = {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Workspace-ID": "spoofed",
    }
    bootstrap = client.get("/api/community/bootstrap", headers=headers)
    assert bootstrap.status_code == 200
    assert bootstrap.json()["viewer"]["workspaceId"] == "jwt-workspace"
    assert all(
        item["workspaceId"] == "jwt-workspace"
        for item in bootstrap.json()["contents"]
    )
    assert client.post(
        "/api/community/submissions",
        headers=headers,
        json={"submission_type": "video", "title": "越权投稿"},
    ).status_code == 403


def test_interactions_are_server_authoritative_and_owner_scoped() -> None:
    _, _, client = _runtime()
    viewer_a = _headers("viewer-a")
    viewer_b = _headers("viewer-b")
    snapshot = client.get("/api/community/bootstrap", headers=viewer_a).json()
    content_id = snapshot["contents"][0]["id"]
    person_id = snapshot["contents"][0]["creatorId"]
    source_id = snapshot["sources"][0]["id"]

    assert client.put(
        f"/api/community/contents/{content_id}/reactions/bookmark",
        headers=viewer_a,
    ).status_code == 200
    assert client.put(
        f"/api/community/people/{person_id}/follow", headers=viewer_a
    ).status_code == 200
    assert client.put(
        f"/api/community/contents/{content_id}/history",
        headers=viewer_a,
        json={"progress_seconds": 19},
    ).status_code == 200

    restored = client.get("/api/community/bootstrap", headers=viewer_a).json()
    content = next(item for item in restored["contents"] if item["id"] == content_id)
    assert "bookmark" in content["viewer"]["reactions"]
    assert content["viewer"]["followedCreator"] is True
    assert content["viewer"]["watchProgressSeconds"] == 19

    comment = client.post(
        f"/api/community/contents/{content_id}/comments",
        headers=viewer_a,
        json={"body": "这条工艺说明很清楚。"},
    )
    assert comment.status_code == 201
    assert client.delete(
        f"/api/community/comments/{comment.json()['id']}", headers=viewer_b
    ).status_code == 403
    assert client.delete(
        f"/api/community/comments/{comment.json()['id']}", headers=viewer_a
    ).status_code == 200

    annotation = client.post(
        f"/api/community/contents/{content_id}/annotations",
        headers=viewer_a,
        json={
            "timestamp_seconds": 3,
            "body": "针脚名称需要补充来源。",
            "kind": "correction",
            "source_ids": [source_id],
        },
    )
    assert annotation.status_code == 201
    assert annotation.json()["verificationStatus"] == "pending"
    assert client.delete(
        f"/api/community/annotations/{annotation.json()['id']}", headers=viewer_b
    ).status_code == 403

    assert client.put(
        "/api/community/contents/not-a-content/reactions/bookmark",
        headers=viewer_a,
    ).status_code == 404
    assert client.get("/api/community/bootstrap", headers=viewer_b).json()[
        "followingPersonIds"
    ] == []


def test_submission_versions_roles_audit_publish_and_notification_close_the_loop(
    tmp_path: Path,
) -> None:
    repository, community, client = _runtime(tmp_path / "media")
    creator_id = "creator-a"
    creator_headers = _headers(creator_id)
    snapshot = client.get("/api/community/bootstrap", headers=creator_headers).json()

    denied = client.post(
        "/api/community/submissions",
        headers=creator_headers,
        json={"submission_type": "video", "title": "未授权投稿"},
    )
    assert denied.status_code == 403

    _activate_creator(client, creator_id)
    created = client.post(
        "/api/community/submissions",
        headers=creator_headers,
        json={"submission_type": "video", "title": "新投稿"},
    )
    assert created.status_code == 201
    submission_id = created.json()["id"]
    assert created.json()["version"] == 1

    updated = client.patch(
        f"/api/community/submissions/{submission_id}",
        headers=creator_headers,
        json={"expected_version": 1, **_complete_draft_payload(snapshot)},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    upload = client.put(
        f"/api/community/submissions/{submission_id}/assets",
        headers={
            **creator_headers,
            "Content-Type": "video/mp4",
            "Idempotency-Key": "upload-c2-real-video-1",
            "X-Upload-Filename": "internal-preview.mp4",
            "X-Upload-Kind": "video",
        },
        params={"expected_version": 2},
        content=SMALL_MP4,
    )
    assert upload.status_code == 200
    assert upload.json()["version"] == 3
    media_asset = upload.json()["assets"][0]
    assert media_asset["localOnly"] is False
    assert media_asset["scanStatus"] == "signature_verified"
    assert client.get(f"/api/community/media/{media_asset['id']}").status_code == 404
    retry = client.put(
        f"/api/community/submissions/{submission_id}/assets",
        headers={
            **creator_headers,
            "Content-Type": "video/mp4",
            "Idempotency-Key": "upload-c2-real-video-1",
            "X-Upload-Filename": "internal-preview.mp4",
            "X-Upload-Kind": "video",
        },
        params={"expected_version": 2},
        content=SMALL_MP4,
    )
    assert retry.status_code == 200
    assert retry.json()["version"] == 3
    image_upload = client.put(
        f"/api/community/submissions/{submission_id}/assets",
        headers={
            **creator_headers,
            "Content-Type": "image/png",
            "Idempotency-Key": "upload-c2-real-image-1",
            "X-Upload-Filename": "cover.png",
            "X-Upload-Kind": "image",
        },
        params={"expected_version": 3},
        content=SMALL_PNG,
    )
    assert image_upload.status_code == 200
    image_asset = image_upload.json()["assets"][1]
    reordered = client.patch(
        f"/api/community/submissions/{submission_id}",
        headers=creator_headers,
        json={
            "expected_version": 4,
            "assetOrder": [image_asset["id"], media_asset["id"]],
        },
    )
    assert reordered.status_code == 200
    assert reordered.json()["assetOrder"] == [image_asset["id"], media_asset["id"]]
    stale = client.patch(
        f"/api/community/submissions/{submission_id}",
        headers=creator_headers,
        json={"expected_version": 1, "summary": "覆盖新版本"},
    )
    assert stale.status_code == 409

    checking = client.post(
        f"/api/community/submissions/{submission_id}/transition",
        headers=creator_headers,
        json={"expected_version": 5, "status": "checking"},
    )
    assert checking.status_code == 200
    submitted = client.post(
        f"/api/community/submissions/{submission_id}/transition",
        headers=creator_headers,
        json={"expected_version": 6, "status": "submitted"},
    )
    assert submitted.status_code == 200

    _grant_controlled_role(repository, creator_id, "reviewer")
    self_review = client.post(
        f"/api/community/submissions/{submission_id}/transition",
        headers=creator_headers,
        json={"expected_version": 7, "status": "reviewing"},
    )
    assert self_review.status_code == 403

    reviewer_id = "reviewer-b"
    _grant_controlled_role(repository, reviewer_id, "reviewer")
    reviewer_headers = _headers(reviewer_id)
    reviewing = client.post(
        f"/api/community/submissions/{submission_id}/transition",
        headers=reviewer_headers,
        json={"expected_version": 7, "status": "reviewing"},
    )
    assert reviewing.status_code == 200
    approved = client.post(
        f"/api/community/submissions/{submission_id}/transition",
        headers=reviewer_headers,
        json={
            "expected_version": 8,
            "status": "approved",
            "reviewer_note": "来源与披露已核对。",
        },
    )
    assert approved.status_code == 200

    reviewer_publish = client.post(
        f"/api/community/submissions/{submission_id}/transition",
        headers=reviewer_headers,
        json={"expected_version": 9, "status": "published"},
    )
    assert reviewer_publish.status_code == 409

    admin_id = "admin-c"
    _grant_controlled_role(repository, admin_id, "admin")
    published = client.post(
        f"/api/community/submissions/{submission_id}/transition",
        headers=_headers(admin_id),
        json={"expected_version": 9, "status": "published"},
    )
    assert published.status_code == 200
    assert published.json()["version"] == 10
    playback = client.get(f"/api/community/media/{media_asset['id']}")
    assert playback.status_code == 200
    assert playback.headers["content-type"].startswith("video/mp4")
    assert playback.content == SMALL_MP4
    partial = client.get(
        f"/api/community/media/{media_asset['id']}", headers={"Range": "bytes=0-7"}
    )
    assert partial.status_code == 206
    assert partial.content == SMALL_MP4[:8]

    projection = community.get_entity(WORKSPACE, "content", f"content-{submission_id}")
    assert projection is not None
    stale_payload = dict(projection["payload_json"])
    stale_payload["body"] = "中断后遗留的旧投影"
    stale_payload["submissionVersion"] = 9
    community.save_entity(
        WORKSPACE,
        "content",
        f"content-{submission_id}",
        str(projection["slug"]),
        str(projection["title"]),
        "published",
        "creator_submission",
        stale_payload,
        str(projection["created_at"]),
        str(projection["updated_at"]),
    )

    creator_snapshot = client.get(
        "/api/community/bootstrap", headers=creator_headers
    ).json()
    assert any(
        item["id"] == f"content-{submission_id}"
        for item in creator_snapshot["contents"]
    )
    published_content = next(
        item
        for item in creator_snapshot["contents"]
        if item["id"] == f"content-{submission_id}"
    )
    assert published_content["body"] == "这是经来源支持的完整投稿正文，不应在发布时被简介替代。"
    assert [item["id"] for item in published_content["media"]] == [
        image_asset["id"], media_asset["id"]
    ]
    assert published_content["cover"]["id"] == image_asset["id"]
    assert published_content["media"][1]["id"] == media_asset["id"]
    assert published_content["media"][1]["url"] == (
        f"/api/backend/api/community/media/{media_asset['id']}"
    )
    assert any(
        item["kind"] == "review" for item in creator_snapshot["notifications"]
    )
    audited = client.get(
        f"/api/community/submissions/{submission_id}",
        headers=_headers(admin_id),
    )
    assert audited.status_code == 200
    assert [event["to_status"] for event in audited.json()["events"]][-1] == "published"
    assert len(community.list_submission_events(submission_id, WORKSPACE)) == 10


def test_article_submission_requires_a_real_body_before_review() -> None:
    payload = {
        "submissionType": "article",
        "title": "图文投稿",
        "summary": "摘要",
        "body": "",
        "projectIds": ["project-demo"],
        "sourceIds": ["source-demo"],
        "assets": [{"id": "asset-demo", "localOnly": False}],
    }
    with pytest.raises(CommunityValidationError, match="图文正文"):
        CommunityService._assert_submission_complete(payload)


def test_media_upload_rejects_spoofed_content_and_unauthorized_users(
    tmp_path: Path,
) -> None:
    repository, community, client = _runtime(tmp_path / "media-security")
    creator_id = "media-owner"
    creator_headers = _headers(creator_id)
    _activate_creator(client, creator_id)
    created = client.post(
        "/api/community/submissions",
        headers=creator_headers,
        json={"submission_type": "video", "title": "安全上传"},
    ).json()
    endpoint = f"/api/community/submissions/{created['id']}/assets"
    upload_headers = {
        "Content-Type": "video/mp4",
        "Idempotency-Key": "media-security-upload-1",
        "X-Upload-Filename": "../../payload.mp4",
        "X-Upload-Kind": "video",
    }

    unauthorized = client.put(
        endpoint,
        headers={**_headers("other-user"), **upload_headers},
        params={"expected_version": 1},
        content=SMALL_MP4,
    )
    assert unauthorized.status_code == 403

    spoofed = client.put(
        endpoint,
        headers={**creator_headers, **upload_headers},
        params={"expected_version": 1},
        content=b"not-an-mp4",
    )
    assert spoofed.status_code == 400
    assert community.list_submission_media(created["id"], WORKSPACE) == []
    assert not list((tmp_path / "media-security" / ".staging").iterdir())


def test_local_archive_import_is_idempotent_and_downgrades_trust() -> None:
    _, community, client = _runtime()
    user_headers = _headers("import-user")
    snapshot = client.get("/api/community/bootstrap", headers=user_headers).json()
    content_id = snapshot["contents"][0]["id"]
    source_id = snapshot["sources"][0]["id"]
    project_id = snapshot["projects"][0]["id"]
    local_state = {
        "schemaVersion": 1,
        "reactions": {content_id: ["respect", "bookmark"]},
        "followingPersonIds": [],
        "history": [],
        "comments": [],
        "annotations": [{
            "id": "local-annotation-verified",
            "contentId": content_id,
            "timestampSeconds": 1,
            "body": "浏览器中曾标记为已核验",
            "kind": "source",
            "sourceIds": [source_id],
            "verificationStatus": "verified",
        }],
        "drafts": [{
            "id": "local-published-draft",
            "submissionType": "article",
            "status": "published",
            "title": "浏览器发布状态不可信",
            "summary": "导入后必须回到草稿状态。",
            "projectIds": [project_id],
            "personIds": [],
            "sourceIds": [source_id],
            "tags": [],
            "assets": [],
            "aiDisclosure": "none",
        }],
        "notifications": [],
        "searchHistory": [],
    }

    preview = client.post(
        "/api/community/imports/preview",
        headers=user_headers,
        json={"local_state": local_state},
    )
    assert preview.status_code == 200
    assert preview.json()["alreadyImported"] is False

    first = client.post(
        "/api/community/imports/commit",
        headers=user_headers,
        json={"local_state": local_state},
    )
    second = client.post(
        "/api/community/imports/commit",
        headers=user_headers,
        json={"local_state": local_state},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["trustBoundary"] == "本地核验、审核和发布状态均未导入"

    restored = client.get("/api/community/bootstrap", headers=user_headers).json()
    imported_annotation = next(
        item for item in restored["annotations"]
        if item["body"] == "浏览器中曾标记为已核验"
    )
    imported_draft = next(
        item for item in restored["drafts"]
        if item["title"] == "浏览器发布状态不可信"
    )
    assert imported_annotation["verificationStatus"] == "pending"
    assert imported_draft["status"] == "draft"
    assert len(community.list_annotations(WORKSPACE)) == 1
    assert len(community.list_submissions(WORKSPACE, owner_user_id="import-user")) == 1


def test_submission_state_revision_and_audit_event_rollback_together() -> None:
    repository = SQLiteCreatorRepository(":memory:")
    repository.ensure_identity("atomic-user", WORKSPACE, role="owner")
    community = SQLAlchemyCommunityRepository.for_sqlite_path(":memory:")
    service = CommunityService(community, UserCenterService(repository))
    created = service.create_submission(
        "atomic-user", WORKSPACE, "creator", "article", "事务测试"
    )
    current = community.get_submission(str(created["id"]), WORKSPACE)
    assert current is not None
    payload = json.loads(current.payload_json)
    payload.update({"title": "不应提交", "version": 2})
    candidate = replace(
        current,
        version=2,
        title="不应提交",
        payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )
    duplicate_event = community.list_submission_events(current.id, WORKSPACE)[0]

    with pytest.raises(IntegrityError):
        community.save_submission_change(
            candidate,
            SubmissionEvent(
                id=duplicate_event.id,
                submission_id=current.id,
                workspace_id=WORKSPACE,
                actor_user_id="atomic-user",
                event_type="submission.updated",
                from_status="draft",
                to_status="draft",
                detail_json="{}",
                created_at=datetime.now(UTC).isoformat(timespec="milliseconds"),
            ),
        )

    restored = community.get_submission(current.id, WORKSPACE)
    assert restored is not None
    assert restored.version == 1
    assert restored.title == "事务测试"
    assert len(community.list_submission_events(current.id, WORKSPACE)) == 1
