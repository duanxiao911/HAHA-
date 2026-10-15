"""Real Docker/PostgreSQL HTTP acceptance for Community Gate C2.

This script targets the explicitly opted-in development-auth stack. Controlled
reviewer/admin grants are provisioned through the database adapter because the
public product correctly has no self-service elevation endpoint.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from haha_core.sqlalchemy_repository import SQLAlchemyCreatorRepository
from haha_identity.domain import RoleGrant
from haha_identity.service import IdentityService

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "e2e" / "community-gate-c2-api"
API_URL = os.getenv("HAHA_E2E_API_URL", "http://127.0.0.1:8000").rstrip("/")
POSTGRES_URL = os.getenv("HAHA_TEST_POSTGRES_URL", "")
WORKSPACE = os.getenv("HAHA_C2_E2E_WORKSPACE", "c2-real-e2e")


def request(
    method: str,
    path: str,
    user_id: str,
    payload: dict[str, object] | None = None,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    headers = {
        "Accept": "application/json",
        "X-User-ID": user_id,
        "X-Workspace-ID": WORKSPACE,
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    call = urllib.request.Request(
        f"{API_URL}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(call, timeout=15) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            detail = json.loads(body) if body else None
        except json.JSONDecodeError:
            detail = body.decode(errors="replace")
        return exc.code, detail


def grant_controlled_role(
    repository: SQLAlchemyCreatorRepository,
    user_id: str,
    role: str,
) -> None:
    service = IdentityService(repository)
    service.bootstrap(user_id, WORKSPACE)
    grants = repository.list_role_grants(user_id, WORKSPACE)
    if not any(item.role == role and item.status == "active" for item in grants):
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        repository.save_role_grant(RoleGrant(
            id=f"grant_{uuid4().hex}",
            user_id=user_id,
            workspace_id=WORKSPACE,
            role=role,
            status="active",
            scope_json="{}",
            granted_by="c2-e2e-provisioner",
            created_at=now,
            revoked_at="",
        ))
    service.switch_context(user_id, WORKSPACE, role)


def main() -> None:
    if not POSTGRES_URL:
        raise SystemExit("HAHA_TEST_POSTGRES_URL is required")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    creator = f"c2-creator-{uuid4().hex[:8]}"
    outsider = f"c2-outsider-{uuid4().hex[:8]}"
    reviewer = f"c2-reviewer-{uuid4().hex[:8]}"
    admin = f"c2-admin-{uuid4().hex[:8]}"
    assertions: dict[str, bool] = {}

    status, snapshot = request("GET", "/api/community/bootstrap", creator)
    seed_contents = [
        item
        for item in snapshot.get("contents", [])
        if item.get("provenance") == "demo_seed"
    ]
    assertions["bootstrap_api_mode"] = (
        status == 200
        and snapshot["runtime"]["mode"] == "api"
        and len(seed_contents) == 10
        and all(item.get("workspaceId") == WORKSPACE for item in seed_contents)
    )
    content_id = snapshot["contents"][0]["id"]
    person_id = snapshot["contents"][0]["creatorId"]
    source_id = snapshot["sources"][0]["id"]
    project_id = snapshot["projects"][0]["id"]
    region_id = snapshot["regions"][0]["id"]

    request("GET", "/api/community/bootstrap", outsider)
    request("GET", "/api/community/bootstrap", reviewer)
    request("GET", "/api/community/bootstrap", admin)
    assertions["reaction_write"] = request(
        "PUT", f"/api/community/contents/{content_id}/reactions/bookmark", creator
    )[0] == 200
    assertions["follow_write"] = request(
        "PUT", f"/api/community/people/{person_id}/follow", creator
    )[0] == 200
    assertions["history_write"] = request(
        "PUT",
        f"/api/community/contents/{content_id}/history",
        creator,
        {"progress_seconds": 23},
    )[0] == 200
    _, restored = request("GET", "/api/community/bootstrap", creator)
    restored_content = next(
        item for item in restored["contents"] if item["id"] == content_id
    )
    assertions["interaction_reload"] = (
        "bookmark" in restored_content["viewer"]["reactions"]
        and restored_content["viewer"]["followedCreator"]
        and restored_content["viewer"]["watchProgressSeconds"] == 23
    )

    status, comment = request(
        "POST",
        f"/api/community/contents/{content_id}/comments",
        creator,
        {"body": "真实 Docker 环境评论"},
    )
    assertions["comment_created"] = status == 201
    assertions["comment_owner_boundary"] = request(
        "DELETE", f"/api/community/comments/{comment['id']}", outsider
    )[0] == 403
    assertions["comment_owner_delete"] = request(
        "DELETE", f"/api/community/comments/{comment['id']}", creator
    )[0] == 200
    status, annotation = request(
        "POST",
        f"/api/community/contents/{content_id}/annotations",
        creator,
        {
            "timestamp_seconds": 2,
            "body": "真实环境待核验注释",
            "kind": "source",
            "source_ids": [source_id],
        },
    )
    assertions["annotation_pending"] = (
        status == 201 and annotation["verificationStatus"] == "pending"
    )

    assertions["viewer_cannot_submit"] = request(
        "POST",
        "/api/community/submissions",
        creator,
        {"submission_type": "article", "title": "未授权"},
    )[0] == 403
    assertions["creator_activated"] = request(
        "POST", "/api/identity/roles/creator/activate", creator
    )[0] == 200
    assertions["creator_context"] = request(
        "POST", "/api/identity/context", creator, {"role": "creator"}
    )[0] == 200
    status, draft = request(
        "POST",
        "/api/community/submissions",
        creator,
        {"submission_type": "article", "title": "真实环境投稿"},
    )
    assertions["draft_created"] = status == 201 and draft["version"] == 1
    submission_id = draft["id"]
    status, draft = request(
        "PATCH",
        f"/api/community/submissions/{submission_id}",
        creator,
        {
            "expected_version": 1,
            "title": "真实环境投稿",
            "summary": "验证服务端版本、权限、审核和发布回流。",
            "categoryId": "刺绣",
            "regionId": region_id,
            "projectIds": [project_id],
            "personIds": [],
            "sourceIds": [source_id],
            "tags": ["C2", "真实环境"],
            "assets": [{
                "id": "c2-e2e-metadata",
                "name": "not-uploaded.mp4",
                "kind": "video",
                "mimeType": "video/mp4",
                "sizeBytes": 1024,
                "localOnly": True,
            }],
            "aiDisclosure": "assisted",
        },
    )
    assertions["draft_versioned"] = status == 200 and draft["version"] == 2
    assertions["stale_version_conflict"] = request(
        "PATCH",
        f"/api/community/submissions/{submission_id}",
        creator,
        {"expected_version": 1, "title": "旧版本覆盖"},
    )[0] == 409
    status, draft = request(
        "POST",
        f"/api/community/submissions/{submission_id}/transition",
        creator,
        {"expected_version": 2, "status": "checking"},
    )
    status, draft = request(
        "POST",
        f"/api/community/submissions/{submission_id}/transition",
        creator,
        {"expected_version": draft["version"], "status": "submitted"},
    )
    assertions["creator_submitted"] = status == 200 and draft["status"] == "submitted"

    repository = SQLAlchemyCreatorRepository(POSTGRES_URL)
    grant_controlled_role(repository, creator, "reviewer")
    assertions["self_review_blocked"] = request(
        "POST",
        f"/api/community/submissions/{submission_id}/transition",
        creator,
        {"expected_version": draft["version"], "status": "reviewing"},
    )[0] == 403
    grant_controlled_role(repository, reviewer, "reviewer")
    status, draft = request(
        "POST",
        f"/api/community/submissions/{submission_id}/transition",
        reviewer,
        {"expected_version": draft["version"], "status": "reviewing"},
    )
    status, draft = request(
        "POST",
        f"/api/community/submissions/{submission_id}/transition",
        reviewer,
        {
            "expected_version": draft["version"],
            "status": "approved",
            "reviewer_note": "真实环境来源与披露检查通过。",
        },
    )
    assertions["reviewer_approved"] = status == 200 and draft["status"] == "approved"
    assertions["reviewer_cannot_publish"] = request(
        "POST",
        f"/api/community/submissions/{submission_id}/transition",
        reviewer,
        {"expected_version": draft["version"], "status": "published"},
    )[0] == 409
    grant_controlled_role(repository, admin, "admin")
    status, draft = request(
        "POST",
        f"/api/community/submissions/{submission_id}/transition",
        admin,
        {"expected_version": draft["version"], "status": "published"},
    )
    assertions["admin_published"] = status == 200 and draft["status"] == "published"
    _, after_publish = request("GET", "/api/community/bootstrap", creator)
    assertions["published_in_feed"] = any(
        item["id"] == f"content-{submission_id}"
        for item in after_publish["contents"]
    )
    assertions["review_notification_returned"] = any(
        item["kind"] == "review" for item in after_publish["notifications"]
    )
    _, audited = request(
        "GET", f"/api/community/submissions/{submission_id}", admin
    )
    assertions["immutable_audit_events"] = (
        len(audited["events"]) == 7
        and audited["events"][-1]["to_status"] == "published"
    )

    report = {
        "status": "PASS" if all(assertions.values()) else "FAIL",
        "environment": {
            "api": API_URL,
            "workspace": WORKSPACE,
            "database": "PostgreSQL via Docker loopback",
            "auth": "explicit development opt-in",
        },
        "assertions": assertions,
        "submission_id": submission_id,
        "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (ARTIFACTS / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
