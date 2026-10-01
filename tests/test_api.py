import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from haha_api.main import create_app
from haha_core.repository import SQLiteCreatorRepository


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
