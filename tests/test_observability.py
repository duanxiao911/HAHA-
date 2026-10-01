from __future__ import annotations

import json
import logging

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
