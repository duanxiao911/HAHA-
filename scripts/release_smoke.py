"""Post-deploy smoke gate for an externally reachable HAHA staging release."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4


def call(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, str], Any]:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            response_headers = dict(response.headers.items())
            content = response.read().decode()
    except urllib.error.HTTPError as exc:
        status = exc.code
        response_headers = dict(exc.headers.items())
        content = exc.read().decode()
    try:
        parsed: Any = json.loads(content)
    except json.JSONDecodeError:
        parsed = content
    return status, response_headers, parsed


def main() -> None:
    api_url = os.environ["HAHA_PUBLIC_API_URL"].rstrip("/")
    web_origin = os.environ["HAHA_PUBLIC_WEB_ORIGIN"].rstrip("/")
    release_id = os.environ["HAHA_RELEASE_ID"]
    token = os.environ["HAHA_RELEASE_ACCESS_TOKEN"]
    request_id = f"release-smoke-{uuid4().hex}"

    health_status, _, health = call("GET", f"{api_url}/health")
    ready_status, _, ready = call("GET", f"{api_url}/ready")
    web_status, _, _ = call("GET", web_origin)
    anonymous_status, _, _ = call(
        "POST",
        f"{api_url}/api/projects",
        headers={"Content-Type": "application/json"},
        payload={"title": "release smoke anonymous"},
    )
    authorized_status, authorized_headers, project = call(
        "POST",
        f"{api_url}/api/projects",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Request-ID": request_id,
        },
        payload={"title": f"release smoke {release_id}"},
    )
    cors_status, cors_headers, _ = call(
        "OPTIONS",
        f"{api_url}/api/runs/release-smoke/events",
        headers={
            "Origin": web_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,last-event-id",
        },
    )

    allowed_headers = cors_headers.get("access-control-allow-headers", "").lower()
    checks = {
        "health": health_status == 200 and health.get("release_id") == release_id,
        "readiness": ready_status == 200 and ready.get("status") == "ready",
        "web": web_status == 200,
        "anonymous_rejected": anonymous_status == 401,
        "authorized_project": authorized_status == 201 and bool(project.get("id")),
        "request_id": authorized_headers.get("x-request-id") == request_id,
        "cors_origin": cors_status == 200
        and cors_headers.get("access-control-allow-origin") == web_origin,
        "cors_sse_reconnect": "authorization" in allowed_headers
        and "last-event-id" in allowed_headers,
    }
    result = {
        "status": "passed" if all(checks.values()) else "failed",
        "release_id": release_id,
        "checks": checks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
