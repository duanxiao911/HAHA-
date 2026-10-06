"""Exercise SSE and cancellation against the full staging container stack."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts" / "e2e" / "phase-c-staging-operations.json"
API_URL = os.getenv("HAHA_E2E_API_URL", "http://127.0.0.1:18000")


def request(
    method: str,
    path: str,
    *,
    token: str = "",
    payload: dict[str, Any] | None = None,
    expected_status: int = 200,
) -> tuple[int, str]:
    headers = {"Content-Type": "application/json", "X-Request-ID": "phase-c-real-e2e"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if method == "POST" and path.endswith("/runs"):
        headers["Idempotency-Key"] = "phase-c-real-cancel-run"
    body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    call = urllib.request.Request(
        f"{API_URL}{path}", data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(call, timeout=40) as response:
            status = response.status
            content = response.read().decode()
    except urllib.error.HTTPError as exc:
        status = exc.code
        content = exc.read().decode()
    if status != expected_status:
        raise RuntimeError(f"{method} {path} returned {status}: {content}")
    return status, content


def request_json(
    method: str,
    path: str,
    *,
    token: str = "",
    payload: dict[str, Any] | None = None,
    expected_status: int = 200,
) -> dict[str, Any]:
    _, content = request(
        method,
        path,
        token=token,
        payload=payload,
        expected_status=expected_status,
    )
    return json.loads(content)


def prepare(token: str) -> None:
    anonymous_status, _ = request(
        "POST", "/api/projects", payload={"title": "anonymous"}, expected_status=401
    )
    readiness = request_json("GET", "/ready")
    project = request_json(
        "POST", "/api/projects", token=token, payload={"title": "Phase C 真实环境取消测试"},
        expected_status=201,
    )
    brief = request_json(
        "POST",
        f"/api/projects/{project['id']}/briefs",
        token=token,
        payload={
            "craft": "中国剪纸",
            "story_seed": "取消前保持待处理状态",
            "audience": "文化爱好者",
            "platform": "B站",
            "tone": "纪录片",
            "goal": "文化科普",
            "duration": "30秒",
            "aspect_ratio": "16:9",
        },
        expected_status=201,
    )
    run = request_json(
        "POST",
        f"/api/projects/{project['id']}/runs",
        token=token,
        payload={"brief_version_id": brief["id"], "model_preference": "本地演示"},
        expected_status=202,
    )
    _, pending_events = request(
        "GET", f"/api/runs/{run['id']}/events?timeout_seconds=1", token=token
    )
    cancelled = request_json(
        "POST", f"/api/runs/{run['id']}/cancel", token=token
    )
    _, terminal_events = request(
        "GET", f"/api/runs/{run['id']}/events?timeout_seconds=1", token=token
    )
    checks = {
        "anonymous_rejected": anonymous_status == 401,
        "database_ready": readiness.get("checks", {}).get("database") == "ok",
        "redis_ready": readiness.get("checks", {}).get("redis") == "ok",
        "queued_to_worker": run.get("execution") == "worker",
        "pending_sse": "event: run.status" in pending_events and '"status":"PENDING"' in pending_events,
        "bounded_sse": "event: run.timeout" in pending_events,
        "cancelled": cancelled.get("status") == "CANCELLED",
        "terminal_sse": "event: run.terminal" in terminal_events and '"status":"CANCELLED"' in terminal_events,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Phase C staging preparation failed: {checks}")
    report = {
        "status": "prepared",
        "api_url": API_URL,
        "run_id": run["id"],
        "checks": checks,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


def verify(token: str) -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    run_id = report["run_id"]
    current: dict[str, Any] = {}
    for _ in range(20):
        current = request_json("GET", f"/api/runs/{run_id}", token=token)
        if current.get("status") != "CANCELLED":
            break
        time.sleep(0.25)
    checks = {
        **report["checks"],
        "cancel_survived_worker_delivery": current.get("status") == "CANCELLED",
        "cancelled_run_has_no_script": current.get("script") is None,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Phase C staging verification failed: {checks}")
    report.update({"status": "passed", "checks": checks})
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "verify"))
    args = parser.parse_args()
    token = os.environ["HAHA_E2E_ACCESS_TOKEN"]
    if args.mode == "prepare":
        prepare(token)
    else:
        verify(token)


if __name__ == "__main__":
    main()
