from pathlib import Path

from scripts.release_preflight import validate

ROOT = Path(__file__).resolve().parents[1]


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
        "HAHA_METRICS_TOKEN": "m" * 40,
        "HAHA_RELEASE_ID": "2026-10-09.c5.1",
        "HAHA_GIT_SHA": "a" * 40,
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
        "HAHA_METRICS_TOKEN": "short",
        "POSTGRES_PASSWORD": "replace-with-a-long-password-value",
        "HAHA_SECURITY_OWNER": "replace-with-security-owner",
        "HAHA_GIT_SHA": "short-sha",
    })

    errors = validate(values)

    assert "HAHA_API_IMAGE must use an immutable @sha256 digest" in errors
    assert "HAHA_PUBLIC_WEB_ORIGIN must be an HTTPS origin without a path" in errors
    assert "HAHA_ALLOWED_ORIGINS must not contain a wildcard" in errors
    assert "HAHA_API_BIND must bind a loopback host and explicit port" in errors
    assert "HAHA_JWT_SECRET must contain at least 32 characters" in errors
    assert "HAHA_METRICS_TOKEN must contain at least 32 characters" in errors
    assert "POSTGRES_PASSWORD still contains a placeholder" in errors
    assert "HAHA_SECURITY_OWNER still contains a placeholder" in errors
    assert "HAHA_GIT_SHA must be a full 40-character lowercase commit SHA" in errors


def test_release_preflight_rejects_shared_jwt_and_metrics_secret() -> None:
    values = _valid_values()
    values["HAHA_METRICS_TOKEN"] = values["HAHA_JWT_SECRET"]

    assert (
        "POSTGRES_PASSWORD, HAHA_JWT_SECRET, and HAHA_METRICS_TOKEN must be independent"
        in validate(values)
    )


def test_release_preflight_rejects_shared_database_and_auth_secret() -> None:
    values = _valid_values()
    values["POSTGRES_PASSWORD"] = values["HAHA_JWT_SECRET"]

    assert (
        "POSTGRES_PASSWORD, HAHA_JWT_SECRET, and HAHA_METRICS_TOKEN must be independent"
        in validate(values)
    )


def test_release_preflight_allows_local_image_ids_only_for_rehearsal() -> None:
    values = _valid_values()
    values["HAHA_API_IMAGE"] = f"sha256:{'f' * 64}"

    assert "HAHA_API_IMAGE must use an immutable @sha256 digest" in validate(values)
    assert validate(values, allow_local_image_ids=True) == []


def test_web_container_requires_explicit_api_url_and_defaults_to_jwt() -> None:
    dockerfile = (ROOT / "web" / "Dockerfile").read_text(encoding="utf-8")
    assert "ARG NEXT_PUBLIC_API_BASE_URL\n" in dockerfile
    assert "ARG NEXT_PUBLIC_AUTH_MODE=jwt" in dockerfile
    assert 'test -n "${NEXT_PUBLIC_API_BASE_URL}"' in dockerfile
    assert "io.haha.web.api-base-url" in dockerfile
    assert "io.haha.web.auth-mode" in dockerfile
    assert "org.opencontainers.image.revision" in dockerfile


def test_api_release_image_uses_reviewed_runtime_constraints() -> None:
    dockerfile = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    constraints = (ROOT / "constraints" / "runtime.txt").read_text(encoding="utf-8")

    assert "--constraint constraints/runtime.txt" in dockerfile
    assert "python -m pip check" in dockerfile
    assert "fastapi==" in constraints
    assert "sqlalchemy==" in constraints.lower()


def test_ci_web_image_is_built_with_jwt_contract() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_API_BASE_URL=https://api.staging.example.invalid" in workflow
    assert "NEXT_PUBLIC_AUTH_MODE=jwt" in workflow
    assert "VCS_REF=${{ github.sha }}" in workflow


def test_dynamic_web_shell_sets_baseline_security_headers() -> None:
    config = (ROOT / "web" / "next.config.ts").read_text(encoding="utf-8")
    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Strict-Transport-Security",
    ):
        assert header in config


def test_container_health_checks_cover_dependencies_and_readiness() -> None:
    api_dockerfile = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    local_compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    release_compose = (ROOT / "compose.release.yaml").read_text(encoding="utf-8")

    assert "http://127.0.0.1:8000/ready" in api_dockerfile
    assert "condition: service_healthy" in local_compose
    assert "Redis.from_url(os.environ['REDIS_URL']).ping()" in local_compose
    assert "Redis.from_url(os.environ['REDIS_URL']).ping()" in release_compose


def test_browser_session_gate_keeps_tokens_server_only_and_static_demo_separate() -> None:
    api_client = (ROOT / "web" / "lib" / "api.ts").read_text(encoding="utf-8")
    bff = (ROOT / "web" / "lib" / "bff-session.ts").read_text(encoding="utf-8")
    proxy = (ROOT / "web" / "app" / "api" / "backend" / "[...path]" / "route.ts").read_text(encoding="utf-8")
    dockerfile = (ROOT / "web" / "Dockerfile").read_text(encoding="utf-8")
    pages = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")

    assert "sessionStorage" not in api_client
    assert "localStorage" not in api_client
    assert "haha_access_token" not in api_client
    assert 'httpOnly,' in bff
    assert 'sameSite: "lax"' in bff
    assert "timingSafeEqual" in bff
    assert '"/api/auth/refresh"' in proxy
    assert "令牌端点只能通过安全会话接口访问" in proxy
    assert 'CMD ["node", "start-server.mjs"]' in dockerfile
    assert "pnpm build:demo" in pages
