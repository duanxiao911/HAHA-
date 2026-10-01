"""Create a staging operator identity and optionally issue a short-lived access token."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import time

from haha_core.bootstrap import build_repository


def _encode(value: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(value, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()


def issue_token(user_id: str, workspace_id: str, ttl_seconds: int) -> str:
    secret = os.environ["HAHA_JWT_SECRET"]
    if len(secret) < 32:
        raise RuntimeError("HAHA_JWT_SECRET 至少需要 32 个字符")
    header = _encode({"alg": "HS256", "typ": "JWT"})
    payload = _encode(
        {
            "sub": user_id,
            "workspace_id": workspace_id,
            "iss": os.getenv("HAHA_JWT_ISSUER", "haha-auth"),
            "aud": os.getenv("HAHA_JWT_AUDIENCE", "haha-api"),
            "iat": int(time.time()),
            "exp": int(time.time()) + ttl_seconds,
        }
    )
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.{signature}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="staging-owner")
    parser.add_argument("--workspace-id", default="staging")
    parser.add_argument("--ttl-seconds", type=int, default=3600)
    parser.add_argument("--show-token", action="store_true")
    args = parser.parse_args()
    repository = build_repository()
    repository.ensure_identity(args.user_id, args.workspace_id, role="owner")
    result: dict[str, object] = {
        "user_id": args.user_id,
        "workspace_id": args.workspace_id,
        "role": "owner",
        "expires_in_seconds": args.ttl_seconds,
    }
    if args.show_token:
        result["access_token"] = issue_token(
            args.user_id, args.workspace_id, args.ttl_seconds
        )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
