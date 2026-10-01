"""Staging-equivalent smoke test against real PostgreSQL, Redis and JWT auth."""

from __future__ import annotations

import json
import os
from uuid import uuid4

from fastapi.testclient import TestClient

from haha_api.main import create_app
from haha_api.staging_bootstrap import issue_token
from haha_core.sqlalchemy_repository import SQLAlchemyCreatorRepository


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    repository = SQLAlchemyCreatorRepository(database_url)
    suffix = uuid4().hex
    user_id = f"staging-user-{suffix}"
    workspace_id = f"staging-workspace-{suffix}"
    repository.ensure_identity(user_id, workspace_id, role="owner")
    token = issue_token(user_id, workspace_id, 300)
    client = TestClient(create_app(repository))

    anonymous = client.post("/api/projects", json={"title": "unauthorized"})
    readiness = client.get("/ready")
    authorized = client.post(
        "/api/projects",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": f"staging-{suffix}",
        },
        json={"title": "staging smoke"},
    )

    result = {
        "anonymous_status": anonymous.status_code,
        "readiness_status": readiness.status_code,
        "readiness": readiness.json(),
        "authorized_status": authorized.status_code,
        "request_id": authorized.headers.get("X-Request-ID"),
        "project_workspace_id": authorized.json().get("workspace_id"),
    }
    print(json.dumps(result, ensure_ascii=False))
    assert result["anonymous_status"] == 401
    assert result["readiness_status"] == 200
    assert result["readiness"] == {
        "status": "ready",
        "checks": {"database": "ok", "redis": "ok"},
    }
    assert result["authorized_status"] == 201
    assert result["request_id"] == f"staging-{suffix}"
    assert result["project_workspace_id"] == workspace_id


if __name__ == "__main__":
    main()
