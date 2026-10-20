from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from haha_api.main import create_app
from haha_core.repository import SQLiteCreatorRepository
from haha_identity.service import IdentityPermissionError, IdentityService


def _repository() -> SQLiteCreatorRepository:
    repository = SQLiteCreatorRepository(":memory:")
    repository.ensure_identity("member-a", "workspace-a", role="owner")
    return repository


def test_one_account_activates_and_switches_multiple_business_roles() -> None:
    repository = _repository()
    service = IdentityService(repository)

    initial = service.bootstrap("member-a", "workspace-a")
    assert {item["role"] for item in initial["roles"]} == {
        "viewer", "buyer", "learner"
    }
    assert initial["consumer_capabilities"] == ["buyer", "learner", "viewer"]
    assert initial["profile"]["active_role"] == "viewer"

    service.activate_role("member-a", "workspace-a", "creator")
    repeated = service.activate_role("member-a", "workspace-a", "creator")
    switched = service.switch_context("member-a", "workspace-a", "creator")

    assert {item["role"] for item in switched["roles"]} == {
        "viewer", "buyer", "learner", "creator"
    }
    assert switched["professional_roles"] == ["creator"]
    assert switched["profile"]["active_role"] == "creator"
    assert len([task for task in switched["tasks"] if task["status"] == "open"]) == 1
    assert len([task for task in repeated["tasks"] if task["status"] == "open"]) == 1


def test_business_role_context_cannot_be_forged() -> None:
    repository = _repository()
    service = IdentityService(repository)
    service.bootstrap("member-a", "workspace-a")

    try:
        service.switch_context("member-a", "workspace-a", "admin")
    except IdentityPermissionError as exc:
        assert "内部员工权限" in str(exc)
    else:
        raise AssertionError("ungranted admin context must be rejected")

    for role in ("viewer", "buyer", "learner"):
        with pytest.raises(IdentityPermissionError, match="默认能力"):
            service.switch_context("member-a", "workspace-a", role)

    for role in ("reviewer", "admin"):
        with pytest.raises(IdentityPermissionError, match="不能通过此申请入口"):
            service.apply_for_role("member-a", "workspace-a", role, "public request")


def test_role_application_requires_another_authorized_reviewer() -> None:
    repository = _repository()
    repository.ensure_identity("reviewer-b", "workspace-a", role="owner")
    service = IdentityService(repository)
    service.bootstrap("member-a", "workspace-a")
    service.bootstrap("reviewer-b", "workspace-a")
    application = service.apply_for_role(
        "member-a", "workspace-a", "seller", "计划经营经过授权的非遗作品"
    )

    try:
        service.decide_application(application.id, "member-a", "approved", "self")
    except IdentityPermissionError as exc:
        assert "自己的" in str(exc)
    else:
        raise AssertionError("self review must be rejected")

    approved = service.decide_application(
        application.id, "reviewer-b", "approved", "材料已核对"
    )
    assert approved.status == "approved"
    snapshot = service.switch_context("member-a", "workspace-a", "seller")
    assert snapshot["profile"]["active_role"] == "seller"


def test_identity_api_persists_roles_tasks_and_rejects_privilege_escalation() -> None:
    repository = _repository()
    client = TestClient(create_app(repository))
    headers = {"X-User-ID": "member-a", "X-Workspace-ID": "workspace-a"}

    initial = client.get("/api/identity/me", headers=headers)
    assert initial.status_code == 200
    assert {item["role"] for item in initial.json()["roles"]} == {
        "viewer", "buyer", "learner"
    }

    assert client.post("/api/identity/roles/creator/activate", headers=headers).status_code == 200
    switched = client.post(
        "/api/identity/context", headers=headers, json={"role": "creator"}
    )
    assert switched.status_code == 200
    assert switched.json()["profile"]["active_role"] == "creator"

    denied = client.post(
        "/api/identity/context", headers=headers, json={"role": "admin"}
    )
    assert denied.status_code == 403
    forbidden_application = client.post(
        "/api/identity/role-applications",
        headers=headers,
        json={"role": "admin", "reason": "尝试自行获得管理员身份"},
    )
    assert forbidden_application.status_code == 403

    restored = client.get("/api/identity/me", headers=headers)
    assert restored.json()["profile"]["active_role"] == "creator"


def test_identity_task_is_owner_scoped_and_completion_is_idempotent() -> None:
    repository = _repository()
    repository.ensure_identity("member-b", "workspace-a", role="viewer")
    client = TestClient(create_app(repository))
    headers_a = {"X-User-ID": "member-a", "X-Workspace-ID": "workspace-a"}
    headers_b = {"X-User-ID": "member-b", "X-Workspace-ID": "workspace-a"}
    activated = client.post("/api/identity/roles/creator/activate", headers=headers_a).json()
    task_id = activated["tasks"][0]["id"]

    assert client.post(f"/api/identity/tasks/{task_id}/complete", headers=headers_b).status_code == 404
    first = client.post(f"/api/identity/tasks/{task_id}/complete", headers=headers_a)
    second = client.post(f"/api/identity/tasks/{task_id}/complete", headers=headers_a)
    assert first.status_code == 200
    assert first.json()["status"] == "completed"
    assert second.status_code == 200
    assert second.json()["completed_at"] == first.json()["completed_at"]


def test_identity_application_api_blocks_self_review_and_supports_owner_review() -> None:
    repository = _repository()
    client = TestClient(create_app(repository))
    applicant = {"X-User-ID": "member-a", "X-Workspace-ID": "workspace-a"}
    reviewer = {"X-User-ID": "reviewer-b", "X-Workspace-ID": "workspace-a"}
    response = client.post(
        "/api/identity/role-applications",
        headers=applicant,
        json={"role": "seller", "reason": "申请经营经过授权的非遗作品"},
    )
    assert response.status_code == 201
    application_id = response.json()["id"]

    self_review = client.post(
        f"/api/identity/role-applications/{application_id}/decision",
        headers=applicant,
        json={"decision": "approved", "note": "自行通过"},
    )
    assert self_review.status_code == 403

    approved = client.post(
        f"/api/identity/role-applications/{application_id}/decision",
        headers=reviewer,
        json={"decision": "approved", "note": "演示审核通过"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert client.post(
        "/api/identity/context", headers=applicant, json={"role": "seller"}
    ).status_code == 200
