"""Explicit test-only opt-in for the local development authentication mode."""

from __future__ import annotations

import os

os.environ.setdefault("HAHA_ENVIRONMENT", "development")
os.environ.setdefault("HAHA_AUTH_MODE", "dev")
os.environ.setdefault("HAHA_ALLOW_DEV_AUTH", "true")
