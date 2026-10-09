from scripts.release_preflight import validate


def _valid_values() -> dict[str, str]:
    digest = "a" * 64
    return {
        "POSTGRES_IMAGE": f"postgres:17-alpine@sha256:{digest}",
        "REDIS_IMAGE": f"redis:8-alpine@sha256:{digest}",
        "HAHA_API_IMAGE": f"ghcr.io/acme/haha-api@sha256:{digest}",
        "HAHA_WEB_IMAGE": f"ghcr.io/acme/haha-web@sha256:{digest}",
        "HAHA_PUBLIC_API_URL": "https://api.staging.haha.test",
        "HAHA_PUBLIC_WEB_ORIGIN": "https://staging.haha.test",
        "HAHA_ALLOWED_ORIGINS": "https://staging.haha.test",
        "HAHA_API_BIND": "127.0.0.1:18000",
        "HAHA_WEB_BIND": "127.0.0.1:13000",
        "POSTGRES_PASSWORD": "p" * 24,
        "HAHA_JWT_SECRET": "j" * 40,
        "HAHA_RELEASE_ID": "2026-10-09.c5.1",
        "HAHA_RELEASE_OWNER": "release-team",
        "HAHA_ROLLBACK_OWNER": "platform-oncall",
        "HAHA_SECURITY_OWNER": "security-team",
        "HAHA_DATA_OWNER": "data-team",
        "HAHA_ONCALL_CONTACT": "oncall-haha",
    }


def test_release_preflight_accepts_pinned_https_configuration() -> None:
    assert validate(_valid_values()) == []


def test_release_preflight_rejects_fail_open_inputs() -> None:
    values = _valid_values()
    values.update({
        "HAHA_API_IMAGE": "ghcr.io/acme/haha-api:latest",
        "HAHA_PUBLIC_WEB_ORIGIN": "http://staging.haha.test/path",
        "HAHA_ALLOWED_ORIGINS": "*",
        "HAHA_API_BIND": "0.0.0.0:18000",
        "HAHA_JWT_SECRET": "short",
        "POSTGRES_PASSWORD": "replace-with-a-long-password-value",
        "HAHA_SECURITY_OWNER": "replace-with-security-owner",
    })

    errors = validate(values)

    assert "HAHA_API_IMAGE must use an immutable @sha256 digest" in errors
    assert "HAHA_PUBLIC_WEB_ORIGIN must be an HTTPS origin without a path" in errors
    assert "HAHA_ALLOWED_ORIGINS must not contain a wildcard" in errors
    assert "HAHA_API_BIND must bind a loopback host and explicit port" in errors
    assert "HAHA_JWT_SECRET must contain at least 32 characters" in errors
    assert "POSTGRES_PASSWORD still contains a placeholder" in errors
    assert "HAHA_SECURITY_OWNER still contains a placeholder" in errors


def test_release_preflight_allows_local_image_ids_only_for_rehearsal() -> None:
    values = _valid_values()
    values["HAHA_API_IMAGE"] = f"sha256:{'f' * 64}"

    assert "HAHA_API_IMAGE must use an immutable @sha256 digest" in validate(values)
    assert validate(values, allow_local_image_ids=True) == []
