"""Create or rotate one non-public internal HAHA account."""

from __future__ import annotations

import argparse
import os

from haha_auth.service import AuthService
from haha_core.bootstrap import build_repository


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=("owner", "editor", "viewer"), default="owner")
    args = parser.parse_args()
    password = os.getenv("HAHA_BOOTSTRAP_PASSWORD", "")
    if not password:
        raise SystemExit("HAHA_BOOTSTRAP_PASSWORD is required and is never accepted on the command line")
    AuthService(build_repository()).bootstrap_account(
        user_id=args.user_id, workspace_id=args.workspace_id,
        email=args.email, password=password, role=args.role,
    )
    print(f"Internal account ready: {args.email} @ {args.workspace_id}")


if __name__ == "__main__":
    main()
