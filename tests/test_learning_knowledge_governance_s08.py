from __future__ import annotations

from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient

from haha_api.main import create_app
from haha_core.repository import SQLiteCreatorRepository
from haha_core.sqlalchemy_repository import SQLAlchemyCreatorRepository
from haha_identity.domain import RoleGrant
from haha_identity.service import IdentityService
from haha_learning.domain import LearningConflictError, LearningPermissionError
from haha_learning.service import LearningService


def _repository() -> SQLiteCreatorRepository:
    repository = SQLiteCreatorRepository(":memory:")
    for user_id in ("learner", "reviewer", "ordinary"):
        repository.ensure_identity(user_id, "s08-workspace", role="owner")
        IdentityService(repository).bootstrap(user_id, "s08-workspace")
    repository.save_role_grant(RoleGrant(
        id="grant-s08-reviewer", user_id="reviewer", workspace_id="s08-workspace",
        role="reviewer", status="active", scope_json="{}", granted_by="system",
        created_at="2026-10-22T00:00:00.000Z", revoked_at="",
    ))
    return repository


def test_unreviewed_contribution_is_isolated_idempotent_and_auditable() -> None:
    service = LearningService(_repository())
    payload = dict(
        topic="待核验的技艺说明",
        body="这是一条需要人工核对来源正文的贡献，不能直接进入可信知识。",
        source_title="来源页面标题",
        source_url="https://www.ihchina.cn/example",
        source_version="访问于 2026-10-22",
        idempotency_key="s08-contribution-0001",
    )
    first = service.submit_knowledge_contribution(
        "learner", "s08-workspace", **payload
    )
    assert first["knowledge_contributions"][0]["status"] == "submitted"
    assert len(service.review_queue("reviewer", "s08-workspace")) == 1

    repeated = service.submit_knowledge_contribution(
        "learner", "s08-workspace", **payload
    )
    assert len(repeated["knowledge_contributions"]) == 1
    with pytest.raises(LearningConflictError, match="幂等键"):
        service.submit_knowledge_contribution(
            "learner", "s08-workspace", **{**payload, "body": "不同正文"}
        )
    with pytest.raises(LearningPermissionError, match="审核权限"):
        service.review_queue("ordinary", "s08-workspace")

    contribution_id = first["knowledge_contributions"][0]["id"]
    reviewed = service.review_knowledge_contribution(
        "reviewer", "s08-workspace", contribution_id,
        decision="approved", reviewer_note="来源和表述已人工核对。", expected_version=1,
    )
    assert reviewed.status == "approved"
    assert reviewed.version == 2
    assert reviewed.reviewed_by == "reviewer"
    assert service.review_queue("reviewer", "s08-workspace") == []


def test_review_is_fail_closed_for_self_review_and_stale_version() -> None:
    repository = _repository()
    service = LearningService(repository)
    snapshot = service.submit_knowledge_contribution(
        "reviewer", "s08-workspace", topic="自审测试", body="不能自己审核自己的内容。",
        source_title="测试来源", source_url="https://example.com/source",
        source_version="v1", idempotency_key="s08-self-review-001",
    )
    contribution_id = snapshot["knowledge_contributions"][0]["id"]
    with pytest.raises(LearningPermissionError, match="不能审核自己"):
        service.review_knowledge_contribution(
            "reviewer", "s08-workspace", contribution_id,
            decision="approved", reviewer_note="不应成功", expected_version=1,
        )


def test_knowledge_governance_api_enforces_server_roles() -> None:
    repository = _repository()
    client = TestClient(create_app(repository))
    learner = {"X-User-ID": "learner", "X-Workspace-ID": "s08-workspace"}
    reviewer = {"X-User-ID": "reviewer", "X-Workspace-ID": "s08-workspace"}
    response = client.post(
        "/api/learning/contributions",
        headers={**learner, "Idempotency-Key": "s08-api-submit-001"},
        json={
            "topic": "API 贡献", "body": "附来源并等待审核。",
            "source_title": "来源", "source_url": "https://example.com/reference",
            "source_version": "2026-10-22",
        },
    )
    assert response.status_code == 200
    contribution = response.json()["knowledge_contributions"][0]
    assert client.get(
        "/api/learning/contributions/review-queue", headers=learner
    ).status_code == 403
    queue = client.get(
        "/api/learning/contributions/review-queue", headers=reviewer
    )
    assert queue.status_code == 200
    reviewed = client.post(
        f"/api/learning/contributions/{contribution['id']}/review",
        headers=reviewer,
        json={"decision": "rejected", "reviewer_note": "来源粒度不足。", "expected_version": 1},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "rejected"
    assert asdict(repository.get_knowledge_contribution(contribution["id"], "s08-workspace"))["reviewed_by"] == "reviewer"


def test_sqlalchemy_adapter_persists_contribution_across_service_rebuild() -> None:
    repository = SQLAlchemyCreatorRepository(
        "sqlite+pysqlite:///:memory:", create_schema=True
    )
    repository.ensure_identity("sa-learner", "sa-s08", role="owner")
    IdentityService(repository).bootstrap("sa-learner", "sa-s08")
    LearningService(repository).submit_knowledge_contribution(
        "sa-learner", "sa-s08", topic="持久化贡献", body="保持审核隔离。",
        source_title="来源", source_url="https://example.com/source",
        source_version="v1", idempotency_key="s08-sa-submit-001",
    )
    restored = LearningService(repository).bootstrap("sa-learner", "sa-s08")
    assert restored["knowledge_contributions"][0]["status"] == "submitted"
