from __future__ import annotations

import base64
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from haha_api.main import create_app
from haha_auth.service import (
    AccountLockedError,
    AuthService,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from haha_core.repository import SQLiteCreatorRepository


@pytest.fixture()
def service(monkeypatch: pytest.MonkeyPatch) -> AuthService:
    monkeypatch.setenv("HAHA_JWT_SECRET", "g2-test-jwt-secret-that-is-long-enough-2026")
    monkeypatch.setenv("HAHA_PASSWORD_PBKDF2_ITERATIONS", "1000")
    repository = SQLiteCreatorRepository(":memory:")
    auth = AuthService(repository)
    auth.bootstrap_account(user_id="auth-user", workspace_id="auth-workspace", email="tester@haha.local", password="Strong-Test-Password-2026", role="owner")
    return auth


def test_login_issues_verifiable_short_lived_access_token(service: AuthService) -> None:
    result = service.login(email="TESTER@HAHA.LOCAL", password="Strong-Test-Password-2026", workspace_id="auth-workspace")
    payload_part = str(result["access_token"]).split(".")[1]
    payload = json.loads(base64.urlsafe_b64decode(payload_part + "=" * (-len(payload_part) % 4)))
    assert payload["sub"] == "auth-user"
    assert payload["workspace_id"] == "auth-workspace"
    assert str(payload["sid"]).startswith("session_")
    assert payload["aud"] == "haha-api"
    assert payload["exp"] - payload["iat"] == 900
    assert "jti" in payload


def test_refresh_rotates_and_logout_revokes_session(service: AuthService) -> None:
    initial = service.login(email="tester@haha.local", password="Strong-Test-Password-2026", workspace_id="auth-workspace")
    rotated = service.refresh(str(initial["refresh_token"]))
    assert rotated["refresh_token"] != initial["refresh_token"]
    with pytest.raises(InvalidRefreshTokenError):
        service.refresh(str(initial["refresh_token"]))
    service.logout(str(rotated["refresh_token"]))
    service.logout(str(rotated["refresh_token"]))
    with pytest.raises(InvalidRefreshTokenError):
        service.refresh(str(rotated["refresh_token"]))


def test_concurrent_refresh_consumes_old_token_exactly_once(service: AuthService) -> None:
    initial = service.login(email="tester@haha.local", password="Strong-Test-Password-2026", workspace_id="auth-workspace")

    def refresh_once() -> str:
        try:
            service.refresh(str(initial["refresh_token"]))
        except InvalidRefreshTokenError:
            return "rejected"
        return "rotated"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: refresh_once(), range(2)))
    assert sorted(outcomes) == ["rejected", "rotated"]


def test_repeated_bad_password_temporarily_locks_account(service: AuthService) -> None:
    for _ in range(4):
        with pytest.raises(InvalidCredentialsError):
            service.login(email="tester@haha.local", password="wrong", workspace_id="auth-workspace")
    with pytest.raises(AccountLockedError):
        service.login(email="tester@haha.local", password="wrong", workspace_id="auth-workspace")
    with pytest.raises(AccountLockedError):
        service.login(email="tester@haha.local", password="Strong-Test-Password-2026", workspace_id="auth-workspace")


def test_auth_api_login_refresh_logout_and_database_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAHA_ENVIRONMENT", "development")
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", "g2-test-jwt-secret-that-is-long-enough-2026")
    monkeypatch.setenv("HAHA_PASSWORD_PBKDF2_ITERATIONS", "1000")
    repository = SQLiteCreatorRepository(":memory:")
    AuthService(repository).bootstrap_account(user_id="auth-user", workspace_id="auth-workspace", email="tester@haha.local", password="Strong-Test-Password-2026", role="viewer")
    client = TestClient(create_app(repository))
    login = client.post("/api/auth/login", json={"email": "tester@haha.local", "password": "Strong-Test-Password-2026", "workspace_id": "auth-workspace"})
    assert login.status_code == 200
    tokens = login.json()
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "viewer"
    refreshed = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    assert client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    assert client.post("/api/auth/logout", json={"refresh_token": refreshed.json()["refresh_token"]}).status_code == 204
    assert client.post("/api/auth/refresh", json={"refresh_token": refreshed.json()["refresh_token"]}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"}).status_code == 401


def test_session_inventory_revoke_one_and_revoke_all_are_owner_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAHA_ENVIRONMENT", "development")
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", "g3-test-jwt-secret-that-is-long-enough-2026")
    monkeypatch.setenv("HAHA_PASSWORD_PBKDF2_ITERATIONS", "1000")
    repository = SQLiteCreatorRepository(":memory:")
    auth = AuthService(repository)
    auth.bootstrap_account(user_id="auth-user", workspace_id="auth-workspace", email="tester@haha.local", password="Strong-Test-Password-2026", role="owner")
    auth.bootstrap_account(user_id="other-user", workspace_id="auth-workspace", email="other@haha.local", password="Other-Strong-Password-2026", role="viewer")
    client = TestClient(create_app(repository))
    first = client.post("/api/auth/login", json={"email": "tester@haha.local", "password": "Strong-Test-Password-2026", "workspace_id": "auth-workspace"}).json()
    second = client.post("/api/auth/login", json={"email": "tester@haha.local", "password": "Strong-Test-Password-2026", "workspace_id": "auth-workspace"}).json()
    other = client.post("/api/auth/login", json={"email": "other@haha.local", "password": "Other-Strong-Password-2026", "workspace_id": "auth-workspace"}).json()
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    sessions = client.get("/api/auth/sessions", headers=first_headers)
    assert sessions.status_code == 200
    assert sessions.json()["count"] == 2
    current = next(item for item in sessions.json()["items"] if item["is_current"])
    second_session = next(item for item in sessions.json()["items"] if item["id"] != current["id"])
    other_session_id = str(other["refresh_token"]).split(".", 1)[0]
    assert client.delete(f"/api/auth/sessions/{other_session_id}", headers=first_headers).status_code == 404
    assert client.delete(f"/api/auth/sessions/{second_session['id']}", headers=first_headers).status_code == 200
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {second['access_token']}"}).status_code == 401
    revoked_all = client.delete("/api/auth/sessions", headers=first_headers)
    assert revoked_all.status_code == 200
    assert revoked_all.json()["revoked"] == 1
    assert client.get("/api/auth/me", headers=first_headers).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {other['access_token']}"}).status_code == 200


def test_login_error_does_not_reveal_account_existence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAHA_ENVIRONMENT", "development")
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", "g2-test-jwt-secret-that-is-long-enough-2026")
    monkeypatch.setenv("HAHA_PASSWORD_PBKDF2_ITERATIONS", "1000")
    repository = SQLiteCreatorRepository(":memory:")
    AuthService(repository).bootstrap_account(user_id="auth-user", workspace_id="auth-workspace", email="tester@haha.local", password="Strong-Test-Password-2026")
    client = TestClient(create_app(repository))
    wrong_password = client.post("/api/auth/login", json={"email": "tester@haha.local", "password": "wrong", "workspace_id": "auth-workspace"})
    missing_account = client.post("/api/auth/login", json={"email": "missing@haha.local", "password": "wrong", "workspace_id": "auth-workspace"})
    assert wrong_password.status_code == missing_account.status_code == 401
    assert wrong_password.json()["detail"] == missing_account.json()["detail"]


def test_password_change_verifies_current_password_and_revokes_every_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HAHA_ENVIRONMENT", "development")
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", "password-change-test-secret-long-enough-2026")
    monkeypatch.setenv("HAHA_PASSWORD_PBKDF2_ITERATIONS", "1000")
    repository = SQLiteCreatorRepository(":memory:")
    auth = AuthService(repository)
    auth.bootstrap_account(
        user_id="password-user",
        workspace_id="password-workspace",
        email="password@haha.local",
        password="Original-Password-2026",
        role="owner",
    )
    client = TestClient(create_app(repository))
    first = client.post(
        "/api/auth/login",
        json={"email": "password@haha.local", "password": "Original-Password-2026"},
    ).json()
    second = client.post(
        "/api/auth/login",
        json={"email": "password@haha.local", "password": "Original-Password-2026"},
    ).json()
    headers = {"Authorization": f"Bearer {first['access_token']}"}

    rejected = client.post(
        "/api/auth/password/change",
        headers=headers,
        json={"current_password": "wrong", "new_password": "Replacement-Password-2026"},
    )
    assert rejected.status_code == 401
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    changed = client.post(
        "/api/auth/password/change",
        headers=headers,
        json={
            "current_password": "Original-Password-2026",
            "new_password": "Replacement-Password-2026",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["revoked_sessions"] == 2
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {second['access_token']}"},
    ).status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"email": "password@haha.local", "password": "Original-Password-2026"},
    ).status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"email": "password@haha.local", "password": "Replacement-Password-2026"},
    ).status_code == 200


def test_account_export_is_owner_scoped_and_excludes_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HAHA_ENVIRONMENT", "development")
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_JWT_SECRET", "account-export-test-secret-long-enough-2026")
    monkeypatch.setenv("HAHA_PASSWORD_PBKDF2_ITERATIONS", "1000")
    repository = SQLiteCreatorRepository(":memory:")
    AuthService(repository).bootstrap_account(
        user_id="export-user",
        workspace_id="export-workspace",
        email="export@haha.local",
        password="Export-Password-2026",
        role="owner",
    )
    client = TestClient(create_app(repository))
    session = client.post(
        "/api/auth/login",
        json={"email": "export@haha.local", "password": "Export-Password-2026"},
    ).json()
    exported = client.get(
        "/api/user-center/export",
        headers={"Authorization": f"Bearer {session['access_token']}"},
    )
    assert exported.status_code == 200
    payload = exported.json()
    assert payload["schema_version"] == "haha-account-export.v1"
    assert payload["account"]["email"] == "export@haha.local"
    assert payload["account"]["user_id"] == "export-user"
    encoded = json.dumps(payload)
    assert '"password_hash":' not in encoded
    assert "password_salt" not in encoded
    assert "password_iterations" not in encoded
    assert str(session["refresh_token"]) not in encoded
    assert payload["security"]["password_hashes_included"] is False


def test_public_registration_creates_one_personal_account_and_logs_in_without_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HAHA_ENVIRONMENT", "development")
    monkeypatch.setenv("HAHA_AUTH_MODE", "jwt")
    monkeypatch.setenv("HAHA_SELF_REGISTRATION_ENABLED", "true")
    monkeypatch.setenv("HAHA_JWT_SECRET", "registration-test-jwt-secret-long-enough-2026")
    monkeypatch.setenv("HAHA_PASSWORD_PBKDF2_ITERATIONS", "1000")
    repository = SQLiteCreatorRepository(":memory:")
    client = TestClient(create_app(repository))

    registered = client.post(
        "/api/auth/register",
        json={
            "display_name": "新成员",
            "email": "New.Member@HAHA.local",
            "password": "Strong-Register-Password-2026",
        },
    )
    assert registered.status_code == 201
    account = registered.json()["account"]
    assert account["user_id"].startswith("user_")
    assert account["workspace_id"].startswith("personal_")
    assert account["role"] == "owner"

    identity = client.get(
        "/api/identity/me",
        headers={"Authorization": f"Bearer {registered.json()['access_token']}"},
    )
    assert identity.status_code == 200
    assert identity.json()["profile"]["display_name"] == "新成员"
    assert {item["role"] for item in identity.json()["roles"]} == {
        "viewer", "buyer", "learner"
    }

    login = client.post(
        "/api/auth/login",
        json={"email": "new.member@haha.local", "password": "Strong-Register-Password-2026"},
    )
    assert login.status_code == 200
    assert login.json()["account"] == account

    duplicate = client.post(
        "/api/auth/register",
        json={
            "display_name": "重复成员",
            "email": "NEW.MEMBER@HAHA.LOCAL",
            "password": "Another-Strong-Password-2026",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "暂时无法使用该邮箱创建账户"


def test_public_registration_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HAHA_SELF_REGISTRATION_ENABLED", raising=False)
    monkeypatch.setenv("HAHA_JWT_SECRET", "registration-disabled-secret-long-enough-2026")
    repository = SQLiteCreatorRepository(":memory:")
    client = TestClient(create_app(repository))

    response = client.post(
        "/api/auth/register",
        json={
            "display_name": "未开放成员",
            "email": "member@haha.local",
            "password": "Strong-Register-Password-2026",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "自助注册当前未开放"
