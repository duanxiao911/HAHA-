from __future__ import annotations

import pytest

from haha_core.database_safety import assert_test_database_reset_safe


def test_database_reset_requires_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HAHA_ALLOW_TEST_DATABASE_RESET", raising=False)
    with pytest.raises(RuntimeError, match="requires"):
        assert_test_database_reset_safe("postgresql+psycopg://u:p@localhost/haha_test")


def test_database_reset_rejects_non_test_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAHA_ALLOW_TEST_DATABASE_RESET", "true")
    with pytest.raises(RuntimeError, match="non-test"):
        assert_test_database_reset_safe("postgresql+psycopg://u:p@localhost/haha")


def test_database_reset_accepts_explicit_test_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAHA_ALLOW_TEST_DATABASE_RESET", "true")
    assert_test_database_reset_safe("postgresql+psycopg://u:p@localhost/haha_test")
