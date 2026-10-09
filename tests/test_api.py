import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from haha_api.main import create_app
from haha_core.domain import RunStatus
from haha_core.repository import SQLiteCreatorRepository
from haha_core.service import CreatorService


def _client(repository: SQLiteCreatorRepository | None = None) -> TestClient:
    return TestClient(create_app(repository or SQLiteCreatorRepository(":memory:")))


def _jwt(secret: str, *, workspace_id: str = "ws_a", role: str = "owner") -> str:
    encode = lambda value: base64.urlsafe_b64encode(  # noqa: E731
        json.dumps(value, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    header = encode({"alg": "HS256", "typ": "JWT"})
    payload = encode({"sub": "user_a", "workspace_id": workspace_id, "role": role, "iss": "haha-auth", "aud": "haha-api", "exp": int(time.time()) + 300})
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.{signature}"


def test_health_endpoint() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"]


def test_sse_reconnect_header_is_allowed_by_cors() -> None:
    response = _client().options(
        "/api/runs/run-1/events",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,last-event-id",
        },
    )

    assert response.status_code == 200
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed
    assert "last-event-id" in allowed


def test_project_brief_run_http_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    # This unit-level HTTP contract intentionally exercises the local fallback.
    # The real Redis/Dramatiq boundary is covered by redis_worker_integration.py.
    monkeypatch.delenv("REDIS_URL", raising=False)
    client = _client()
    project_response = client.post(
        "/api/projects", json={"title": "剪纸专题"}
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    brief_response = client.post(
        f"/api/projects/{project_id}/briefs",
        json={
            "craft": "中国剪纸",
            "story_seed": "剪刀落下形成纹样",
            "audience": "传统文化初学者",
            "platform": "B站",
            "tone": "纪录片",
            "goal": "文化科普",
            "duration": "90秒",
            "aspect_ratio": "16:9",
        },
    )
    assert brief_response.status_code == 201
    brief_id = brief_response.json()["id"]
    run_response = client.post(
        f"/api/projects/{project_id}/runs",
        headers={"Idempotency-Key": "api-test-run-0001"},
        json={"brief_version_id": brief_id, "model_preference": "本地演示"},
    )
    assert run_response.status_code == 202
    run_id = run_response.json()["id"]
    result = client.get(f"/api/runs/{run_id}")
    assert result.status_code == 200
    assert result.json()["status"] == "PASSED"
    assert result.json()["script"]["payload"]["judgment"][3] == ["推荐平台", "B站"]

    events = client.get(f"/api/runs/{run_id}/events?timeout_seconds=1")
    assert events.status_code == 200
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "event: run.terminal" in events.text
    assert '"status":"PASSED"' in events.text
    assert '"terminal":true' in events.text


def test_run_event_stream_enforces_workspace_boundary(monkeypatch) -> None:
    secret = "test-secret-that-is-at-least-32-characters-long"
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", secret)
    repository = SQLiteCreatorRepository(":memory:")
    repository.ensure_identity("user_a", "ws_a", role="owner")
    repository.ensure_identity("user_a", "ws_b", role="owner")
    client = _client(repository)
    token_a = _jwt(secret, workspace_id="ws_a")
    project = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "流式状态项目"},
    ).json()
    denied = client.get(
        "/api/runs/run_missing/events",
        headers={"Authorization": f"Bearer {_jwt(secret, workspace_id='ws_b')}"},
    )
    assert denied.status_code == 404

    brief = client.post(
        f"/api/projects/{project['id']}/briefs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "craft": "中国剪纸",
            "audience": "文化爱好者",
            "platform": "B站",
            "tone": "纪录片",
            "duration": "30秒",
            "aspect_ratio": "16:9",
        },
    ).json()
    run = client.post(
        f"/api/projects/{project['id']}/runs",
        headers={
            "Authorization": f"Bearer {token_a}",
            "Idempotency-Key": "phase-c-events-run",
        },
        json={"brief_version_id": brief["id"], "model_preference": "本地演示"},
    ).json()
    cross_workspace = client.get(
        f"/api/runs/{run['id']}/events?timeout_seconds=1",
        headers={"Authorization": f"Bearer {_jwt(secret, workspace_id='ws_b')}"},
    )
    assert cross_workspace.status_code == 403


def test_run_cancellation_api_is_idempotent() -> None:
    repository = SQLiteCreatorRepository(":memory:")
    service = CreatorService(repository)
    project = service.create_project(title="取消接口", workspace_id="local")
    brief = service.create_brief(
        project.id,
        craft="中国剪纸",
        audience="文化爱好者",
        platform="B站",
        tone="纪录片",
        duration="30秒",
        aspect_ratio="16:9",
    )
    run, _ = service.create_run(
        workspace_id="local",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="本地演示",
        idempotency_key="api-cancel-run",
    )
    client = _client(repository)

    first = client.post(f"/api/runs/{run.id}/cancel")
    second = client.post(f"/api/runs/{run.id}/cancel")

    assert first.status_code == 200
    assert first.json()["status"] == "CANCELLED"
    assert second.status_code == 200
    assert second.json()["status"] == "CANCELLED"


def test_viewer_cannot_cancel_run(monkeypatch) -> None:
    secret = "test-secret-that-is-at-least-32-characters-long"
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", secret)
    repository = SQLiteCreatorRepository(":memory:")
    repository.ensure_identity("user_a", "ws_a", role="viewer")
    service = CreatorService(repository)
    project = service.create_project(title="只读工作区", workspace_id="ws_a")
    brief = service.create_brief(
        project.id,
        craft="中国剪纸",
        audience="文化爱好者",
        platform="B站",
        tone="纪录片",
        duration="30秒",
        aspect_ratio="16:9",
    )
    run, _ = service.create_run(
        workspace_id="ws_a",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="本地演示",
        idempotency_key="viewer-cancel-run",
    )
    client = _client(repository)

    response = client.post(
        f"/api/runs/{run.id}/cancel",
        headers={"Authorization": f"Bearer {_jwt(secret)}"},
    )

    assert response.status_code == 403
    assert repository.get_run(run.id).status is RunStatus.PENDING


def test_health_and_readiness_have_distinct_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    client = _client()
    health = client.get("/health")
    ready = client.get("/ready")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "checks": {"database": "ok", "redis": "not_configured"},
    }


def test_run_creation_is_idempotent_over_http() -> None:
    client = _client()
    project_id = client.post(
        "/api/projects", json={"title": "扎染专题"}
    ).json()["id"]
    brief_id = client.post(
        f"/api/projects/{project_id}/briefs",
        json={
            "craft": "白族扎染",
            "audience": "文化爱好者",
            "platform": "抖音",
            "tone": "年轻轻快",
            "duration": "30秒",
            "aspect_ratio": "9:16",
        },
    ).json()["id"]
    request = {
        "headers": {"Idempotency-Key": "api-same-request"},
        "json": {"brief_version_id": brief_id, "model_preference": "本地演示"},
    }
    first = client.post(f"/api/projects/{project_id}/runs", **request)
    second = client.post(f"/api/projects/{project_id}/runs", **request)
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["created"] is True
    assert second.json()["created"] is False


def test_jwt_auth_and_workspace_boundary(monkeypatch) -> None:
    secret = "test-secret-that-is-at-least-32-characters-long"
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", secret)
    repository = SQLiteCreatorRepository(":memory:")
    repository.ensure_identity("user_a", "ws_a", role="owner")
    client = _client(repository)
    assert client.get("/health").status_code == 200
    denied = client.post(
        "/api/projects", json={"title": "项目"}
    )
    assert denied.status_code == 401
    invalid = client.post("/api/projects", headers={"Authorization": "Bearer invalid"}, json={"title": "项目"})
    assert invalid.status_code == 401
    allowed = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {_jwt(secret)}", "X-Workspace-ID": "spoofed"},
        json={"title": "项目"},
    )
    assert allowed.status_code == 201
    assert allowed.json()["workspace_id"] == "ws_a"
    cross_workspace = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {_jwt(secret, workspace_id='ws_b')}"},
        json={"title": "越权项目"},
    )
    assert cross_workspace.status_code == 403


def test_viewer_cannot_write(monkeypatch) -> None:
    secret = "test-secret-that-is-at-least-32-characters-long"
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", secret)
    repository = SQLiteCreatorRepository(":memory:")
    repository.ensure_identity("user_a", "ws_a", role="viewer")
    client = _client(repository)
    response = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {_jwt(secret, role='owner')}"},
        json={"title": "项目"},
    )
    assert response.status_code == 403


def test_production_authentication_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("HAHA_ENVIRONMENT", "production")
    monkeypatch.setenv("HAHA_AUTH_MODE", "dev")
    with pytest.raises(RuntimeError, match="必须启用"):
        create_app(SQLiteCreatorRepository(":memory:"))


def _record_failed_job(
    repository: SQLiteCreatorRepository,
    *,
    workspace_id: str,
    key: str,
) -> str:
    service = CreatorService(repository)
    project = service.create_project(title=key, workspace_id=workspace_id)
    brief = service.create_brief(
        project.id,
        craft="中国剪纸",
        audience="文化爱好者",
        platform="B站",
        tone="纪录片",
        duration="30秒",
        aspect_ratio="16:9",
    )
    run, _ = service.create_run(
        workspace_id=workspace_id,
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="不存在的模型",
        idempotency_key=key,
    )
    failed = service.execute_run(run.id)
    repository.record_failed_job(failed.id, failed.error_code)
    return repository.list_failed_jobs(workspace_id)[0].id


def test_failed_job_api_is_workspace_scoped_and_retry_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "test-secret-that-is-at-least-32-characters-long"
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", secret)
    monkeypatch.setattr("haha_api.main.enqueue_run", lambda *_: True)
    repository = SQLiteCreatorRepository(":memory:")
    repository.ensure_identity("user_a", "ws_a", role="owner")
    repository.ensure_identity("user_a", "ws_b", role="owner")
    job_a = _record_failed_job(repository, workspace_id="ws_a", key="api-failed-a")
    job_b = _record_failed_job(repository, workspace_id="ws_b", key="api-failed-b")
    client = _client(repository)
    auth_a = {"Authorization": f"Bearer {_jwt(secret, workspace_id='ws_a')}"}

    listed = client.get("/api/failed-jobs", headers=auth_a)
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["items"][0]["id"] == job_a
    assert listed.json()["items"][0]["run"]["workspace_id"] == "ws_a"
    denied = client.post(f"/api/failed-jobs/{job_b}/retry", headers=auth_a)
    assert denied.status_code == 404

    retried = client.post(f"/api/failed-jobs/{job_a}/retry", headers=auth_a)
    assert retried.status_code == 202
    assert retried.json()["execution"] == "worker"
    assert retried.json()["run"]["status"] == "RETRYING"
    assert retried.json()["run"]["attempt"] == 2
    repeated = client.post(f"/api/failed-jobs/{job_a}/retry", headers=auth_a)
    assert repeated.status_code == 409


def test_failed_job_api_allows_viewers_to_list_but_not_mutate(monkeypatch) -> None:
    secret = "test-secret-that-is-at-least-32-characters-long"
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", secret)
    repository = SQLiteCreatorRepository(":memory:")
    repository.ensure_identity("user_a", "ws_a", role="viewer")
    job_id = _record_failed_job(repository, workspace_id="ws_a", key="api-viewer-failed")
    client = _client(repository)
    auth = {"Authorization": f"Bearer {_jwt(secret, workspace_id='ws_a')}"}

    assert client.get("/api/failed-jobs", headers=auth).status_code == 200
    assert client.post(f"/api/failed-jobs/{job_id}/retry", headers=auth).status_code == 403
    assert client.post(f"/api/failed-jobs/{job_id}/resolve", headers=auth).status_code == 403


def test_failed_job_resolve_api_is_idempotent(monkeypatch) -> None:
    secret = "test-secret-that-is-at-least-32-characters-long"
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", secret)
    repository = SQLiteCreatorRepository(":memory:")
    repository.ensure_identity("user_a", "ws_a", role="owner")
    job_id = _record_failed_job(repository, workspace_id="ws_a", key="api-resolve-failed")
    client = _client(repository)
    auth = {"Authorization": f"Bearer {_jwt(secret, workspace_id='ws_a')}"}

    first = client.post(f"/api/failed-jobs/{job_id}/resolve", headers=auth)
    second = client.post(f"/api/failed-jobs/{job_id}/resolve", headers=auth)
    assert first.status_code == 200
    assert first.json()["resolved_at"]
    assert second.status_code == 200
    assert second.json()["resolved_at"] == first.json()["resolved_at"]
    assert client.get("/api/failed-jobs", headers=auth).json()["count"] == 0
    with_resolved = client.get(
        "/api/failed-jobs?include_resolved=true", headers=auth
    ).json()
    assert with_resolved["count"] == 1
