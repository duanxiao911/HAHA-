from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthCredential:
    user_id: str
    workspace_id: str
    email: str
    password_salt: str
    password_hash: str
    password_iterations: int
    status: str
    failed_attempts: int
    locked_until: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class AuthSession:
    id: str
    user_id: str
    workspace_id: str
    refresh_token_hash: str
    expires_at: str
    revoked_at: str
    created_at: str
    last_used_at: str


@dataclass(frozen=True, slots=True)
class AuthAuditEvent:
    id: str
    user_id: str
    workspace_id: str
    event_type: str
    detail_json: str
    created_at: str
