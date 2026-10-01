"""Server-verified identity and role-based authorization boundary."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from enum import StrEnum

from fastapi import Header, HTTPException, status


class Role(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    workspace_id: str
    role: Role
    auth_mode: str


def validate_security_configuration() -> None:
    environment = os.getenv("HAHA_ENVIRONMENT", "development").strip().lower()
    mode = os.getenv("HAHA_AUTH_MODE", "dev").strip().lower()
    if environment in {"staging", "production"} and mode != "jwt":
        raise RuntimeError("staging/production 必须启用 HAHA_AUTH_MODE=jwt")
    if mode == "jwt" and len(os.getenv("HAHA_JWT_SECRET", "")) < 32:
        raise RuntimeError("HAHA_JWT_SECRET 至少需要 32 个字符")
    if mode not in {"dev", "jwt"}:
        raise RuntimeError(f"不支持的认证模式：{mode}")


def _decode_segment(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _decode_and_verify_jwt(token: str) -> dict[str, object]:
    try:
        header_part, payload_part, signature_part = token.split(".")
        header = json.loads(_decode_segment(header_part))
        payload = json.loads(_decode_segment(payload_part))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="无效的访问令牌") from exc
    if header.get("alg") != "HS256":
        raise HTTPException(status_code=401, detail="不允许的 JWT 算法")
    secret = os.environ["HAHA_JWT_SECRET"].encode()
    expected = hmac.new(secret, f"{header_part}.{payload_part}".encode(), hashlib.sha256).digest()
    try:
        supplied = _decode_segment(signature_part)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="无效的访问令牌") from exc
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=401, detail="访问令牌签名无效")
    now = int(time.time())
    if int(payload.get("exp", 0)) <= now:
        raise HTTPException(status_code=401, detail="访问令牌已过期")
    if payload.get("iss") != os.getenv("HAHA_JWT_ISSUER", "haha-auth"):
        raise HTTPException(status_code=401, detail="访问令牌签发方无效")
    if payload.get("aud") != os.getenv("HAHA_JWT_AUDIENCE", "haha-api"):
        raise HTTPException(status_code=401, detail="访问令牌受众无效")
    return payload


def authenticate(
    authorization: str = Header(default="", alias="Authorization"),
    dev_user_id: str = Header(default="local-user", alias="X-User-ID"),
    dev_workspace_id: str = Header(default="local", alias="X-Workspace-ID"),
) -> Principal:
    mode = os.getenv("HAHA_AUTH_MODE", "dev").strip().lower()
    if mode == "dev":
        if os.getenv("HAHA_ENVIRONMENT", "development").lower() != "development":
            raise HTTPException(status_code=500, detail="非开发环境禁止 dev 认证")
        return Principal(dev_user_id.strip(), dev_workspace_id.strip(), Role.OWNER, "dev")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not supplied:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 Bearer 访问令牌", headers={"WWW-Authenticate": "Bearer"})
    payload = _decode_and_verify_jwt(supplied)
    try:
        return Principal(
            str(payload["sub"]), str(payload["workspace_id"]), Role.VIEWER, "jwt"
        )
    except KeyError as exc:
        raise HTTPException(status_code=401, detail="访问令牌缺少身份声明") from exc


def require_project_access(principal: Principal, project_workspace_id: str) -> None:
    if principal.workspace_id != project_workspace_id:
        raise HTTPException(status_code=403, detail="无权访问该工作空间项目")


def require_write_access(principal: Principal) -> None:
    if principal.role not in {Role.OWNER, Role.EDITOR}:
        raise HTTPException(status_code=403, detail="当前角色没有写入权限")
