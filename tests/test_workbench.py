from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from haha_api.main import create_app
from haha_core.domain import Project
from haha_core.repository import SQLiteCreatorRepository
from haha_identity.service import IdentityService
from haha_user_center.service import UserCenterService
from haha_workbench.service import WorkbenchPermissionError, WorkbenchService


def _repository() -> SQLiteCreatorRepository:
    repository = SQLiteCreatorRepository(":memory:")
    repository.ensure_identity("member-a", "workspace-a", role="owner")
    return repository


def test_workbench_projects_active_identity_and_capability_boundaries() -> None:
    repository = _repository()
    identity = IdentityService(repository)
    center = UserCenterService(repository)
    workbench = WorkbenchService(repository)

    center.bootstrap("member-a", "workspace-a")
    center.set_library_item(
        "member-a",
        "workspace-a",
        kind_value="want_to_learn",
        target_id="heritage-1",
        title="苗绣针法",
        target_href="/content/heritage-1",
        active=True,
    )
    center.record_history(
        "member-a",
        "workspace-a",
        content_id="video-1",
        title="银饰锻制",
        target_href="/content/video-1",
        progress_seconds=30,
        duration_seconds=120,
    )

    viewer = workbench.snapshot("member-a", "workspace-a")
    assert viewer["role"] == "viewer"
    assert {item["status"] for item in viewer["capabilities"]} == {
        "available",
        "limited",
    }
    assert any(item["title"] == "银饰锻制" for item in viewer["resources"])

    identity.activate_role("member-a", "workspace-a", "learner")
    identity.switch_context("member-a", "workspace-a", "learner")
    learner = workbench.snapshot("member-a", "workspace-a")
    assert learner["role"] == "learner"
    assert any(item["title"] == "苗绣针法" for item in learner["resources"])
    assert (
        next(item for item in learner["capabilities"] if item["key"] == "ai_tutor")["status"]
        == "blocked"
    )

    identity.activate_role("member-a", "workspace-a", "creator")
    identity.switch_context("member-a", "workspace-a", "creator")
    repository.save_project(Project.create("侗族大歌短片", "workspace-a"))
    creator = workbench.snapshot("member-a", "workspace-a")
    assert creator["role"] == "creator"
    assert creator["metrics"][0] == {
        "key": "projects",
        "label": "近期项目",
        "value": 1,
    }
    assert creator["resources"][0]["title"] == "侗族大歌短片"

    identity.switch_context("member-a", "workspace-a", "buyer")
    buyer = workbench.snapshot("member-a", "workspace-a")
    assert buyer["maturity"] == "partial"
    assert (
        next(item for item in buyer["capabilities"] if item["key"] == "orders")["status"]
        == "limited"
    )


def test_workbench_fails_closed_if_active_role_has_no_grant() -> None:
    repository = _repository()
    service = WorkbenchService(repository)
    service.user_center.bootstrap("member-a", "workspace-a")
    profile = repository.ensure_user_profile("member-a", "workspace-a")
    repository.save_user_profile(replace(profile, active_role="admin"))

    with pytest.raises(WorkbenchPermissionError, match="授权已失效"):
        service.snapshot("member-a", "workspace-a")


def test_workbench_api_uses_persisted_context_and_ignores_role_forgery() -> None:
    repository = _repository()
    client = TestClient(create_app(repository))
    headers = {"X-User-ID": "member-a", "X-Workspace-ID": "workspace-a"}

    forged = client.get("/api/identity/workbench?role=admin", headers=headers)
    assert forged.status_code == 200
    assert forged.json()["role"] == "viewer"

    assert (
        client.post("/api/identity/context", headers=headers, json={"role": "admin"}).status_code
        == 403
    )
    assert client.post("/api/identity/roles/creator/activate", headers=headers).status_code == 200
    assert (
        client.post("/api/identity/context", headers=headers, json={"role": "creator"}).status_code
        == 200
    )
    creator = client.get("/api/identity/workbench", headers=headers)
    assert creator.status_code == 200
    assert creator.json()["role"] == "creator"
    assert any(item["key"] == "creator_projects" for item in creator.json()["capabilities"])
