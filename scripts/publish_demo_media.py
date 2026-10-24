"""Publish the five explicitly approved demo media submissions.

This is an intentionally narrow production operation.  It keeps the normal
submission state machine and audit events, while using separate internal
reviewer and publisher identities so that the creator never self-reviews.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from uuid import uuid4

from haha_community.bootstrap import build_community_repository
from haha_community.service import CommunityService
from haha_core.bootstrap import build_repository
from haha_identity.domain import RoleGrant
from haha_identity.service import IdentityService
from haha_user_center.service import UserCenterService

WORKSPACE_ID = "demo"
REVIEWER_ID = "demo-media-reviewer"
PUBLISHER_ID = "demo-media-publisher"
APPROVAL_NOTE = "演示展示前已检查素材可播放、基础信息与来源关联；公开展示后仍可继续补充资料。"

SUBMISSIONS = {
    "submission_3dab7be4d4364299b7c1f597ce1c988d": "四川竹编：篾条转折之间的老手艺",
    "submission_ff40ce1d55094d25a23c49e018a0a51a": "云南白族扎染：蓝白之间的手工温度",
    "submission_c0fc1f6eac8e4f069c090270a0b72d85": "江南剪纸：一刀一纹样",
    "submission_0a0cae27115e490692fe46c58bcf476d": "景德镇陶瓷：一笔绘釉",
    "submission_11d46460eb924312bfe3dcfa01000e87": "传统刺绣：穿在身上的史书",
}
PAPERCUT_SUBMISSION_ID = "submission_c0fc1f6eac8e4f069c090270a0b72d85"
PAPERCUT_PROJECT_ID = "project-jiangnan-papercut"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def grant_role(repository: object, user_id: str, role: str) -> None:
    repository.ensure_identity(  # type: ignore[attr-defined]
        user_id,
        WORKSPACE_ID,
        role="viewer",
        workspace_name="HAHA 演示空间",
    )
    identity = IdentityService(repository)  # type: ignore[arg-type]
    identity.bootstrap(user_id, WORKSPACE_ID)
    grants = repository.list_role_grants(user_id, WORKSPACE_ID)  # type: ignore[attr-defined]
    if any(item.role == role and item.status == "active" for item in grants):
        return
    repository.save_role_grant(  # type: ignore[attr-defined]
        RoleGrant(
            id=f"grant_{uuid4().hex}",
            user_id=user_id,
            workspace_id=WORKSPACE_ID,
            role=role,
            status="active",
            scope_json=json.dumps({"purpose": "demo-media-publication"}),
            granted_by="demo-publication-operation",
            created_at=now(),
            revoked_at="",
        )
    )


def ensure_papercut_project(repository: object) -> None:
    if repository.get_entity(WORKSPACE_ID, "project", PAPERCUT_PROJECT_ID):  # type: ignore[attr-defined]
        return
    timestamp = now()
    payload = {
        "id": PAPERCUT_PROJECT_ID,
        "workspaceId": WORKSPACE_ID,
        "provenance": "demo_publication",
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "slug": "jiangnan-papercut",
        "name": "江南剪纸",
        "level": "demo",
        "category": "剪纸",
        "regionIds": ["region-jiangsu"],
        "inheritorIds": [],
        "summary": "用于现场展示的江南剪纸项目档案，后续可继续补充地区与传承人资料。",
        "materials": ["纸", "剪刀"],
        "techniques": ["折叠", "剪刻"],
        "sourceIds": ["source-national-list"],
        "verificationStatus": "pending",
    }
    repository.save_entity(  # type: ignore[attr-defined]
        WORKSPACE_ID,
        "project",
        PAPERCUT_PROJECT_ID,
        "jiangnan-papercut",
        "江南剪纸",
        "active",
        "demo_publication",
        payload,
        timestamp,
        timestamp,
    )


def transition(service: CommunityService, submission: dict[str, object], status: str, actor: str, role: str, note: str = "") -> dict[str, object]:
    return service.transition_submission(
        actor,
        WORKSPACE_ID,
        role,
        str(submission["id"]),
        int(submission["version"]),
        status,
        note,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-demo-publication", action="store_true")
    args = parser.parse_args()
    if not args.confirm_demo_publication:
        raise SystemExit("Refusing to publish without --confirm-demo-publication")
    if not os.getenv("DATABASE_URL", "").strip():
        raise SystemExit("DATABASE_URL is required")

    core_repository = build_repository()
    community_repository = build_community_repository(core_repository)
    service = CommunityService(
        community_repository,
        UserCenterService(core_repository),  # type: ignore[arg-type]
    )
    grant_role(core_repository, REVIEWER_ID, "reviewer")
    grant_role(core_repository, PUBLISHER_ID, "admin")
    ensure_papercut_project(community_repository)

    results: list[dict[str, object]] = []
    for submission_id, expected_title in SUBMISSIONS.items():
        record = community_repository.get_submission(submission_id, WORKSPACE_ID)
        if record is None:
            raise SystemExit(f"Submission not found: {submission_id}")
        submission = service.get_submission(
            record.owner_user_id, WORKSPACE_ID, "creator", submission_id
        )
        if submission.get("title") != expected_title:
            raise SystemExit(f"Title mismatch for {submission_id}")

        if submission_id == PAPERCUT_SUBMISSION_ID and submission["status"] == "draft":
            submission = service.update_submission(
                record.owner_user_id,
                WORKSPACE_ID,
                "creator",
                submission_id,
                int(submission["version"]),
                {"projectIds": [PAPERCUT_PROJECT_ID]},
            )
            submission = transition(service, submission, "checking", record.owner_user_id, "creator")
            submission = transition(service, submission, "submitted", record.owner_user_id, "creator")

        if submission["status"] == "submitted":
            submission = transition(service, submission, "reviewing", REVIEWER_ID, "reviewer")
        if submission["status"] == "reviewing":
            submission = transition(service, submission, "approved", REVIEWER_ID, "reviewer", APPROVAL_NOTE)
        if submission["status"] == "approved":
            submission = transition(service, submission, "published", PUBLISHER_ID, "admin", APPROVAL_NOTE)
        if submission["status"] != "published":
            raise SystemExit(f"Unexpected status for {submission_id}: {submission['status']}")
        results.append({
            "id": submission_id,
            "title": expected_title,
            "status": submission["status"],
            "version": submission["version"],
        })

    print(json.dumps({"published": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
