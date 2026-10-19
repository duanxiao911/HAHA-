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
from urllib.parse import urlparse
from uuid import uuid4

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
    session_id: str = ""


def _environment() -> str:
    return os.getenv("HAHA_ENVIRONMENT", "production").strip().lower()


def _auth_mode() -> str:
    return os.getenv("HAHA_AUTH_MODE", "jwt").strip().lower()


def _dev_auth_enabled() -> bool:
    return os.getenv("HAHA_ALLOW_DEV_AUTH", "").strip().lower() == "true"


def _valid_shared_origin(value: str, *, allow_loopback: bool) -> bool:
    parsed = urlparse(value)
    secure = parsed.scheme == "https"
    loopback = (
        allow_loopback
        and parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
    )
    return (
        (secure or loopback)
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )


def validate_security_configuration() -> None:
    environment = _environment()
    mode = _auth_mode()
    if environment not in {"development", "staging", "production"}:
        raise RuntimeError(f"不支持的运行环境：{environment}")
    if mode not in {"dev", "jwt"}:
        raise RuntimeError(f"不支持的认证模式：{mode}")
    if environment in {"staging", "production"} and mode != "jwt":
        raise RuntimeError("staging/production 必须启用 HAHA_AUTH_MODE=jwt")
    if mode == "dev" and (
        environment != "development" or not _dev_auth_enabled()
    ):
        raise RuntimeError(
            "dev 认证仅允许在 development 环境显式设置 HAHA_ALLOW_DEV_AUTH=true 后启用"
        )
    if mode == "jwt" and len(os.getenv("HAHA_JWT_SECRET", "")) < 32:
        raise RuntimeError("HAHA_JWT_SECRET 至少需要 32 个字符")
    if environment in {"staging", "production"}:
        metrics_token = os.getenv("HAHA_METRICS_TOKEN", "")
        if len(metrics_token) < 32:
            raise RuntimeError("staging/production 的 HAHA_METRICS_TOKEN 至少需要 32 个字符")
        if metrics_token == os.getenv("HAHA_JWT_SECRET", ""):
            raise RuntimeError("HAHA_METRICS_TOKEN 不得与 HAHA_JWT_SECRET 共用")
        if not os.getenv("HAHA_JWT_ISSUER", "haha-auth").strip():
            raise RuntimeError("HAHA_JWT_ISSUER 不得为空")
        if not os.getenv("HAHA_JWT_AUDIENCE", "haha-api").strip():
            raise RuntimeError("HAHA_JWT_AUDIENCE 不得为空")
        origins = [
            item.strip().rstrip("/")
            for item in os.getenv("HAHA_ALLOWED_ORIGINS", "").split(",")
            if item.strip()
        ]
        if not origins or "*" in origins:
            raise RuntimeError("staging/production 必须配置非通配的 HAHA_ALLOWED_ORIGINS")
        allow_loopback = environment == "staging"
        if any(
            not _valid_shared_origin(origin, allow_loopback=allow_loopback)
            for origin in origins
        ):
            raise RuntimeError("共享环境的 HAHA_ALLOWED_ORIGINS 必须是安全 origin")


def authorize_metrics(
    authorization: str = Header(default="", alias="Authorization"),
) -> None:
    """Protect operational metrics outside the explicitly local development runtime."""
    if _environment() == "development":
        return
    expected = os.getenv("HAHA_METRICS_TOKEN", "")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少或无效的指标访问令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _decode_segment(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _encode_segment(value: dict[str, object]) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def issue_access_token(
    *, user_id: str, workspace_id: str, session_id: str, expires_in: int = 900
) -> str:
    """Issue a short-lived access JWT; authorization remains database-backed."""
    now = int(time.time())
    header = _encode_segment({"alg": "HS256", "typ": "JWT"})
    payload = _encode_segment({
        "sub": user_id,
        "workspace_id": workspace_id,
        "sid": session_id,
        "iss": os.getenv("HAHA_JWT_ISSUER", "haha-auth"),
        "aud": os.getenv("HAHA_JWT_AUDIENCE", "haha-api"),
        "iat": now,
        "exp": now + expires_in,
        "jti": uuid4().hex,
    })
    signature = hmac.new(
        os.environ["HAHA_JWT_SECRET"].encode(),
        f"{header}.{payload}".encode(), hashlib.sha256,
    ).digest()
    return f"{header}.{payload}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


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
    mode = _auth_mode()
    if mode == "dev":
        if _environment() != "development" or not _dev_auth_enabled():
            raise HTTPException(status_code=500, detail="dev 认证未显式启用")
        return Principal(dev_user_id.strip(), dev_workspace_id.strip(), Role.OWNER, "dev")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not supplied:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 Bearer 访问令牌", headers={"WWW-Authenticate": "Bearer"})
    payload = _decode_and_verify_jwt(supplied)
    try:
        session_id = str(payload["sid"])
        if not session_id.startswith("session_"):
            raise HTTPException(status_code=401, detail="访问令牌会话声明无效")
        return Principal(
            str(payload["sub"]), str(payload["workspace_id"]), Role.VIEWER, "jwt",
            session_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=401, detail="访问令牌缺少身份声明") from exc


def require_project_access(principal: Principal, project_workspace_id: str) -> None:
    if principal.workspace_id != project_workspace_id:
        raise HTTPException(status_code=403, detail="无权访问该工作空间项目")


def require_write_access(principal: Principal) -> None:
    if principal.role not in {Role.OWNER, Role.EDITOR}:
        raise HTTPException(status_code=403, detail="当前角色没有写入权限")
