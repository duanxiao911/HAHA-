"""Fail-closed validation for an external HAHA staging release environment."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

IMAGE_DIGEST = re.compile(r"^[^\s]+@sha256:[0-9a-f]{64}$")
LOCAL_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
PLACEHOLDER_MARKERS = ("replace-with", "example.com", "changeme", "todo")
ROLE_KEYS = (
    "HAHA_RELEASE_OWNER",
    "HAHA_ROLLBACK_OWNER",
    "HAHA_SECURITY_OWNER",
    "HAHA_DATA_OWNER",
    "HAHA_ONCALL_CONTACT",
)
REQUIRED_KEYS = (
    "POSTGRES_IMAGE",
    "REDIS_IMAGE",
    "HAHA_API_IMAGE",
    "HAHA_WEB_IMAGE",
    "HAHA_PUBLIC_API_URL",
    "HAHA_PUBLIC_WEB_ORIGIN",
    "HAHA_ALLOWED_ORIGINS",
    "HAHA_API_BIND",
    "HAHA_WEB_BIND",
    "POSTGRES_PASSWORD",
    "HAHA_JWT_SECRET",
    "HAHA_RELEASE_ID",
    *ROLE_KEYS,
)


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _is_https_origin(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )


def _is_loopback_http(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


def validate(
    values: dict[str, str], *, allow_loopback: bool = False,
    allow_local_image_ids: bool = False,
) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_KEYS:
        if not values.get(key, "").strip():
            errors.append(f"{key} is required")

    for key in ("POSTGRES_IMAGE", "REDIS_IMAGE", "HAHA_API_IMAGE", "HAHA_WEB_IMAGE"):
        value = values.get(key, "")
        valid_image = IMAGE_DIGEST.fullmatch(value) or (
            allow_local_image_ids and LOCAL_IMAGE_ID.fullmatch(value)
        )
        if value and not valid_image:
            errors.append(f"{key} must use an immutable @sha256 digest")

    for key, minimum in (("POSTGRES_PASSWORD", 20), ("HAHA_JWT_SECRET", 32)):
        value = values.get(key, "")
        if value and len(value) < minimum:
            errors.append(f"{key} must contain at least {minimum} characters")

    api_url = values.get("HAHA_PUBLIC_API_URL", "").rstrip("/")
    web_origin = values.get("HAHA_PUBLIC_WEB_ORIGIN", "").rstrip("/")
    for key, value in (("HAHA_PUBLIC_API_URL", api_url), ("HAHA_PUBLIC_WEB_ORIGIN", web_origin)):
        valid = _is_https_origin(value) or (allow_loopback and _is_loopback_http(value))
        if value and not valid:
            errors.append(f"{key} must be an HTTPS origin without a path")

    origins = [item.strip().rstrip("/") for item in values.get("HAHA_ALLOWED_ORIGINS", "").split(",") if item.strip()]
    if "*" in origins:
        errors.append("HAHA_ALLOWED_ORIGINS must not contain a wildcard")
    if web_origin and web_origin not in origins:
        errors.append("HAHA_ALLOWED_ORIGINS must include HAHA_PUBLIC_WEB_ORIGIN")
    for origin in origins:
        if not (_is_https_origin(origin) or (allow_loopback and _is_loopback_http(origin))):
            errors.append(f"invalid allowed origin: {origin}")

    for key in ("HAHA_API_BIND", "HAHA_WEB_BIND"):
        value = values.get(key, "")
        host, separator, port = value.rpartition(":")
        valid_bind = (
            separator == ":"
            and host in {"127.0.0.1", "localhost"}
            and port.isdigit()
            and 1 <= int(port) <= 65535
        )
        if value and not valid_bind:
            errors.append(f"{key} must bind a loopback host and explicit port")

    for key in (
        *ROLE_KEYS,
        "HAHA_RELEASE_ID",
        "POSTGRES_PASSWORD",
        "HAHA_JWT_SECRET",
        "HAHA_PUBLIC_API_URL",
        "HAHA_PUBLIC_WEB_ORIGIN",
    ):
        value = values.get(key, "").lower()
        if value and any(marker in value for marker in PLACEHOLDER_MARKERS):
            errors.append(f"{key} still contains a placeholder")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--allow-loopback", action="store_true")
    parser.add_argument("--allow-local-image-ids", action="store_true")
    args = parser.parse_args()
    values = load_env_file(args.env_file) if args.env_file else {}
    values.update({key: value for key, value in os.environ.items() if key in REQUIRED_KEYS})
    errors = validate(
        values,
        allow_loopback=args.allow_loopback,
        allow_local_image_ids=args.allow_local_image_ids,
    )
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    print(json.dumps({
        "status": "passed",
        "release_id": values["HAHA_RELEASE_ID"],
        "public_api_url": values["HAHA_PUBLIC_API_URL"],
        "public_web_origin": values["HAHA_PUBLIC_WEB_ORIGIN"],
        "images_pinned": True,
        "ownership_declared": True,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
