from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from haha_api.auth import issue_access_token
from haha_auth.domain import AuthAuditEvent, AuthCredential, AuthSession
from haha_auth.repository import AuthRepository


class InvalidCredentialsError(RuntimeError):
    pass


class AccountLockedError(RuntimeError):
    pass


class InvalidRefreshTokenError(RuntimeError):
    pass


class RegistrationDisabledError(RuntimeError):
    pass


class AccountRegistrationError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds")


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


class AuthService:
    def __init__(self, repository: AuthRepository) -> None:
        self.repository = repository
        self.iterations = int(os.getenv("HAHA_PASSWORD_PBKDF2_ITERATIONS", "600000"))
        self.access_ttl = int(os.getenv("HAHA_ACCESS_TOKEN_TTL_SECONDS", "900"))
        self.refresh_ttl = int(os.getenv("HAHA_REFRESH_TOKEN_TTL_SECONDS", "604800"))
        self.lock_threshold = int(os.getenv("HAHA_AUTH_LOCK_THRESHOLD", "5"))
        self.lock_seconds = int(os.getenv("HAHA_AUTH_LOCK_SECONDS", "900"))
        self.registration_enabled = (
            os.getenv("HAHA_SELF_REGISTRATION_ENABLED", "false").lower() == "true"
        )

    def bootstrap_account(self, *, user_id: str, workspace_id: str, email: str, password: str, role: str = "owner") -> None:
        clean_email = self._validate_email(email)
        self._validate_password(password)
        self.repository.ensure_identity(user_id, workspace_id, role=role, email=clean_email, workspace_name=workspace_id)
        existing = self.repository.get_auth_credential(clean_email, workspace_id)
        now = _iso(_now())
        self.repository.save_auth_credential(self._credential(
            user_id=user_id, workspace_id=workspace_id, email=clean_email,
            password=password, created_at=existing.created_at if existing else now,
        ))
        self._audit(user_id, workspace_id, "auth.account.bootstrapped", {})

    def register(
        self, *, email: str, password: str, display_name: str
    ) -> dict[str, object]:
        if not self.registration_enabled:
            raise RegistrationDisabledError("自助注册当前未开放")
        clean_email = self._validate_email(email)
        self._validate_password(password)
        clean_display_name = self._validate_display_name(display_name)
        account_id = uuid4().hex
        user_id = f"user_{account_id}"
        workspace_id = f"personal_{account_id}"
        now = _iso(_now())
        credential = self._credential(
            user_id=user_id,
            workspace_id=workspace_id,
            email=clean_email,
            password=password,
            created_at=now,
        )
        if not self.repository.create_personal_account(
            credential,
            workspace_name="个人空间",
            display_name=clean_display_name,
        ):
            # Keep the public message deliberately generic so registration cannot
            # be used as a reliable account-enumeration endpoint.
            raise AccountRegistrationError("暂时无法使用该邮箱创建账户")
        self._audit(user_id, workspace_id, "auth.account.registered", {})
        return self._new_session(user_id, workspace_id, "owner")

    def login(
        self, *, email: str, password: str, workspace_id: str = ""
    ) -> dict[str, object]:
        clean_email = email.strip().lower()
        credential = (
            self.repository.get_auth_credential(clean_email, workspace_id.strip())
            if workspace_id.strip()
            else self.repository.get_auth_credential_by_email(clean_email)
        )
        if not credential or credential.status != "active":
            hashlib.pbkdf2_hmac(
                "sha256", password.encode(), b"HAHA-auth-missing-account-salt", self.iterations
            )
            raise InvalidCredentialsError("邮箱或密码不正确")
        now = _now()
        if credential.locked_until and datetime.fromisoformat(credential.locked_until) > now:
            self._audit(credential.user_id, credential.workspace_id, "auth.login.locked", {})
            raise AccountLockedError("登录尝试过多，请稍后再试")
        salt = base64.urlsafe_b64decode(credential.password_salt)
        expected = base64.urlsafe_b64decode(credential.password_hash)
        supplied = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, credential.password_iterations)
        if not hmac.compare_digest(expected, supplied):
            attempts = credential.failed_attempts + 1
            locked_until = _iso(now + timedelta(seconds=self.lock_seconds)) if attempts >= self.lock_threshold else ""
            self.repository.save_auth_credential(replace(credential, failed_attempts=attempts, locked_until=locked_until, updated_at=_iso(now)))
            self._audit(credential.user_id, credential.workspace_id, "auth.login.failed", {"failed_attempts": attempts})
            if locked_until:
                raise AccountLockedError("登录尝试过多，请稍后再试")
            raise InvalidCredentialsError("邮箱或密码不正确")
        role = self.repository.get_membership_role(credential.user_id, credential.workspace_id)
        if not role:
            raise InvalidCredentialsError("邮箱或密码不正确")
        self.repository.save_auth_credential(replace(credential, failed_attempts=0, locked_until="", updated_at=_iso(now)))
        result = self._new_session(credential.user_id, credential.workspace_id, role)
        self._audit(credential.user_id, credential.workspace_id, "auth.login.succeeded", {})
        return result

    def refresh(self, refresh_token: str) -> dict[str, object]:
        session_id, secret = self._parse_refresh(refresh_token)
        session = self.repository.get_auth_session(session_id)
        now = _now()
        if not session or session.revoked_at or datetime.fromisoformat(session.expires_at) <= now or not hmac.compare_digest(session.refresh_token_hash, _hash_secret(secret)):
            raise InvalidRefreshTokenError("刷新会话无效或已过期")
        role = self.repository.get_membership_role(session.user_id, session.workspace_id)
        if not role:
            raise InvalidRefreshTokenError("刷新会话无效或已过期")
        new_secret = secrets.token_urlsafe(48)
        rotated = replace(session, refresh_token_hash=_hash_secret(new_secret), last_used_at=_iso(now))
        if not self.repository.rotate_auth_session(rotated, session.refresh_token_hash):
            raise InvalidRefreshTokenError("刷新会话无效或已过期")
        self._audit(session.user_id, session.workspace_id, "auth.session.refreshed", {"session_id": session.id})
        return self._token_payload(session.user_id, session.workspace_id, role, f"{session.id}.{new_secret}")

    def logout(self, refresh_token: str) -> None:
        try:
            session_id, secret = self._parse_refresh(refresh_token)
        except InvalidRefreshTokenError:
            return
        session = self.repository.get_auth_session(session_id)
        if not session or session.revoked_at or not hmac.compare_digest(session.refresh_token_hash, _hash_secret(secret)):
            return
        self.repository.save_auth_session(replace(session, revoked_at=_iso(_now()), last_used_at=_iso(_now())))
        self._audit(session.user_id, session.workspace_id, "auth.logout", {"session_id": session.id})

    def session_is_active(self, session_id: str, user_id: str, workspace_id: str) -> bool:
        session = self.repository.get_auth_session(session_id)
        return bool(
            session
            and session.user_id == user_id
            and session.workspace_id == workspace_id
            and not session.revoked_at
            and datetime.fromisoformat(session.expires_at) > _now()
        )

    def list_sessions(
        self, *, user_id: str, workspace_id: str, current_session_id: str
    ) -> list[dict[str, object]]:
        now = _now()
        return [
            {
                "id": session.id,
                "status": (
                    "revoked" if session.revoked_at else
                    "expired" if datetime.fromisoformat(session.expires_at) <= now else
                    "active"
                ),
                "is_current": session.id == current_session_id,
                "created_at": session.created_at,
                "last_used_at": session.last_used_at,
                "expires_at": session.expires_at,
                "revoked_at": session.revoked_at,
            }
            for session in self.repository.list_auth_sessions(user_id, workspace_id)
        ]

    def revoke_session(
        self, *, session_id: str, user_id: str, workspace_id: str
    ) -> bool:
        revoked = self.repository.revoke_auth_session(
            session_id, user_id, workspace_id, _iso(_now())
        )
        if revoked:
            self._audit(user_id, workspace_id, "auth.session.revoked", {"session_id": session_id})
        return revoked

    def revoke_all_sessions(self, *, user_id: str, workspace_id: str) -> int:
        count = self.repository.revoke_all_auth_sessions(
            user_id, workspace_id, _iso(_now())
        )
        self._audit(user_id, workspace_id, "auth.sessions.revoked_all", {"count": count})
        return count

    def _new_session(self, user_id: str, workspace_id: str, role: str) -> dict[str, object]:
        now = _now()
        secret = secrets.token_urlsafe(48)
        session = AuthSession(id=f"session_{uuid4().hex}", user_id=user_id, workspace_id=workspace_id, refresh_token_hash=_hash_secret(secret), expires_at=_iso(now + timedelta(seconds=self.refresh_ttl)), revoked_at="", created_at=_iso(now), last_used_at=_iso(now))
        self.repository.save_auth_session(session)
        return self._token_payload(user_id, workspace_id, role, f"{session.id}.{secret}")

    def _credential(
        self,
        *,
        user_id: str,
        workspace_id: str,
        email: str,
        password: str,
        created_at: str,
    ) -> AuthCredential:
        salt = secrets.token_bytes(32)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, self.iterations
        )
        return AuthCredential(
            user_id=user_id,
            workspace_id=workspace_id,
            email=email,
            password_salt=base64.urlsafe_b64encode(salt).decode(),
            password_hash=base64.urlsafe_b64encode(digest).decode(),
            password_iterations=self.iterations,
            status="active",
            failed_attempts=0,
            locked_until="",
            created_at=created_at,
            updated_at=_iso(_now()),
        )

    @staticmethod
    def _validate_email(email: str) -> str:
        clean_email = email.strip().lower()
        local, separator, domain = clean_email.partition("@")
        if (
            not separator
            or not local
            or "." not in domain
            or domain.startswith(".")
            or domain.endswith(".")
            or len(clean_email) > 320
        ):
            raise ValueError("邮箱格式无效")
        return clean_email

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < 12 or len(password) > 256:
            raise ValueError("密码长度必须为 12 到 256 个字符")

    @staticmethod
    def _validate_display_name(display_name: str) -> str:
        cleaned = display_name.strip()
        if len(cleaned) < 2 or len(cleaned) > 40:
            raise ValueError("昵称长度必须为 2 到 40 个字符")
        return cleaned

    def _token_payload(self, user_id: str, workspace_id: str, role: str, refresh_token: str) -> dict[str, object]:
        session_id, _ = self._parse_refresh(refresh_token)
        return {"access_token": issue_access_token(user_id=user_id, workspace_id=workspace_id, session_id=session_id, expires_in=self.access_ttl), "refresh_token": refresh_token, "token_type": "bearer", "expires_in": self.access_ttl, "account": {"user_id": user_id, "workspace_id": workspace_id, "role": role}}

    @staticmethod
    def _parse_refresh(token: str) -> tuple[str, str]:
        try:
            session_id, secret = token.strip().split(".", 1)
        except ValueError as exc:
            raise InvalidRefreshTokenError("刷新会话无效或已过期") from exc
        if not session_id.startswith("session_") or len(secret) < 32:
            raise InvalidRefreshTokenError("刷新会话无效或已过期")
        return session_id, secret

    def _audit(self, user_id: str, workspace_id: str, event_type: str, detail: dict[str, object]) -> None:
        self.repository.save_auth_audit_event(AuthAuditEvent(id=f"authaudit_{uuid4().hex}", user_id=user_id, workspace_id=workspace_id, event_type=event_type, detail_json=json.dumps(detail, ensure_ascii=False, sort_keys=True), created_at=_iso(_now())))
