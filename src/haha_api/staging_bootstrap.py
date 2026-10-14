"""Create a staging operator identity and optionally issue a short-lived access token."""

from __future__ import annotations

import argparse
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from haha_api.auth import issue_access_token
from haha_auth.domain import AuthSession
from haha_core.bootstrap import build_repository
from haha_core.repository import CreatorRepository


def issue_token(
    repository: CreatorRepository, user_id: str, workspace_id: str, ttl_seconds: int
) -> str:
    now = datetime.now(UTC)
    session_id = f"session_{uuid4().hex}"
    repository.save_auth_session(
        AuthSession(
            id=session_id, user_id=user_id, workspace_id=workspace_id,
            refresh_token_hash=secrets.token_hex(32),
            expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(),
            revoked_at="", created_at=now.isoformat(), last_used_at=now.isoformat(),
        )
    )
    return issue_access_token(
        user_id=user_id, workspace_id=workspace_id,
        session_id=session_id, expires_in=ttl_seconds,
    )


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
            repository, args.user_id, args.workspace_id, args.ttl_seconds
        )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
