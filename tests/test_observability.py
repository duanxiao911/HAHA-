from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from haha_api.main import create_app
from haha_api.observability import JsonFormatter, Metrics
from haha_core.repository import SQLiteCreatorRepository


def test_json_log_formatter_emits_correlation_fields_without_secrets() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="haha",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request.completed",
        args=(),
        exc_info=None,
    )
    record.event = "request.completed"
    record.component = "api"
    record.request_id = "req-observe-001"
    record.fields = {"status": 200, "route": "/health"}

    payload = json.loads(formatter.format(record))

    assert payload["event"] == "request.completed"
    assert payload["request_id"] == "req-observe-001"
    assert payload["status"] == 200
    assert "authorization" not in payload


def test_metrics_render_uses_prometheus_text_format() -> None:
    registry = Metrics()
    registry.add("haha_test_total", method="GET", status="200")
    registry.add("haha_test_total", 2, method="GET", status="200")

    assert 'haha_test_total{method="GET",status="200"} 3' in registry.render()


def test_http_middleware_correlates_request_and_exposes_metrics() -> None:
    client = TestClient(create_app(SQLiteCreatorRepository(":memory:")))

    response = client.get("/health", headers={"X-Request-ID": "req-observe-002"})
    metrics_response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-observe-002"
    assert metrics_response.status_code == 200
    assert "haha_http_requests_total" in metrics_response.text
    assert 'route="/health"' in metrics_response.text
    assert "haha_http_request_duration_seconds_sum" in metrics_response.text
    assert metrics_response.headers["cache-control"] == "no-store"
    assert metrics_response.headers["x-content-type-options"] == "nosniff"


def test_shared_environment_requires_a_dedicated_metrics_secret(monkeypatch) -> None:
    monkeypatch.setenv("HAHA_ENVIRONMENT", "staging")
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", "jwt-secret-with-at-least-thirty-two-characters")
    monkeypatch.delenv("HAHA_METRICS_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="HAHA_METRICS_TOKEN"):
        create_app(SQLiteCreatorRepository(":memory:"))


def test_shared_environment_protects_metrics_with_independent_bearer_token(
    monkeypatch,
) -> None:
    metrics_token = "metrics-secret-with-at-least-thirty-two-characters"
    monkeypatch.setenv("HAHA_ENVIRONMENT", "staging")
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", "jwt-secret-with-at-least-thirty-two-characters")
    monkeypatch.setenv("HAHA_METRICS_TOKEN", metrics_token)
    client = TestClient(create_app(SQLiteCreatorRepository(":memory:")))

    missing = client.get("/metrics")
    incorrect = client.get("/metrics", headers={"Authorization": "Bearer wrong"})
    authorized = client.get(
        "/metrics", headers={"Authorization": f"Bearer {metrics_token}"}
    )

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert incorrect.status_code == 401
    assert authorized.status_code == 200
    assert "haha_http_requests_total" in authorized.text


def test_shared_environment_rejects_reused_jwt_and_metrics_secret(monkeypatch) -> None:
    shared = "shared-secret-with-at-least-thirty-two-characters"
    monkeypatch.setenv("HAHA_ENVIRONMENT", "production")
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", shared)
    monkeypatch.setenv("HAHA_METRICS_TOKEN", shared)

    with pytest.raises(RuntimeError, match="不得与"):
        create_app(SQLiteCreatorRepository(":memory:"))
