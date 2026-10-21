"""Destructive test-database safety boundaries."""

from __future__ import annotations

import os
import re

from sqlalchemy.engine import make_url

_TEST_DATABASE_NAME = re.compile(r"(?:^|[-_])test(?:$|[-_])", re.IGNORECASE)


def assert_test_database_reset_safe(database_url: str) -> None:
    """Reject destructive fixture resets unless the target is explicitly a test DB."""

    if os.getenv("HAHA_ALLOW_TEST_DATABASE_RESET", "").lower() != "true":
        raise RuntimeError(
            "destructive database fixture reset requires "
            "HAHA_ALLOW_TEST_DATABASE_RESET=true"
        )
    database = (make_url(database_url).database or "").strip()
    if not database or not _TEST_DATABASE_NAME.search(database):
        raise RuntimeError(
            f"refusing destructive reset for non-test database: {database or '<empty>'}"
        )
