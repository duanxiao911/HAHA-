from pathlib import Path

import pytest

from scripts.postgres_restore_drill import (
    VERIFIED_TABLES,
    compose_command,
    validate_restore_database_name,
    verification_sql,
)


def test_restore_database_name_allows_only_generated_isolated_targets() -> None:
    validate_restore_database_name("haha_restore_20261018_120000_a1b2c3d4", "haha")

    for unsafe in ("haha", "postgres", "haha_restore_manual", "haha_restore_../../haha"):
        with pytest.raises(ValueError):
            validate_restore_database_name(unsafe, "haha")


def test_restore_verification_covers_current_cross_module_state() -> None:
    sql = verification_sql()

    assert "alembic_version" in sql
    for table in VERIFIED_TABLES:
        assert f"SELECT count(*) FROM {table}" in sql


def test_restore_drill_can_target_an_isolated_compose_project() -> None:
    command = compose_command(
        Path("compose.release.yaml"), "ps", project_name="haha-gate-f-rehearsal"
    )
    assert command[:4] == ["docker", "compose", "-p", "haha-gate-f-rehearsal"]
