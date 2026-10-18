"""Back up PostgreSQL and verify a restore in a uniquely named isolated database."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

RESTORE_DATABASE = re.compile(r"^haha_restore_\d{8}_\d{6}_[0-9a-f]{8}$")
VERIFIED_TABLES = (
    "users",
    "memberships",
    "projects",
    "learning_profiles",
    "quiz_attempts",
    "community_entities",
    "commerce_orders",
)


def validate_restore_database_name(name: str, source_database: str) -> None:
    if name == source_database or not RESTORE_DATABASE.fullmatch(name):
        raise ValueError("restore database must be a generated haha_restore_* database")


def verification_sql() -> str:
    fields = [
        "'alembic_version', (SELECT version_num FROM alembic_version LIMIT 1)",
        *(f"'{table}', (SELECT count(*) FROM {table})" for table in VERIFIED_TABLES),
    ]
    return "SELECT json_build_object(" + ",".join(fields) + ")::text;"


def run(
    command: Sequence[str], *, input_bytes: bytes | None = None,
    capture_bytes: bool = False,
) -> bytes | str:
    result = subprocess.run(
        list(command),
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{stderr}")
    if capture_bytes:
        return result.stdout
    return result.stdout.decode(errors="replace").strip()


def compose_command(compose_file: Path, *arguments: str) -> list[str]:
    return ["docker", "compose", "-f", str(compose_file), *arguments]


def database_snapshot(compose_file: Path, user: str, database: str) -> dict[str, object]:
    output = run(
        compose_command(
            compose_file,
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            user,
            "-d",
            database,
            "-At",
            "-c",
            verification_sql(),
        )
    )
    assert isinstance(output, str)
    return json.loads(output.splitlines()[-1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compose-file", type=Path, default=Path("compose.yaml"))
    parser.add_argument("--source-database", default="haha")
    parser.add_argument("--database-user", default="haha")
    parser.add_argument("--backup-path", type=Path)
    parser.add_argument("--report", type=Path, default=Path("artifacts/recovery/gate-f-restore.json"))
    parser.add_argument("--keep-restore-db", action="store_true")
    parser.add_argument("--delete-backup-after-verify", action="store_true")
    args = parser.parse_args()

    timestamp = datetime.now(UTC)
    restore_database = f"haha_restore_{timestamp:%Y%m%d_%H%M%S}_{uuid4().hex[:8]}"
    validate_restore_database_name(restore_database, args.source_database)
    backup_path = args.backup_path or Path(
        f"artifacts/backups/{timestamp:%Y-%m-%d_%H%M%S}_gate-f.dump"
    )
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    container_backup = f"/tmp/{restore_database}.dump"
    started = time.perf_counter()
    created_restore = False
    copied_backup = False
    status = "failed"
    source_snapshot: dict[str, object] = {}
    restored_snapshot: dict[str, object] = {}
    error = ""
    try:
        source_snapshot = database_snapshot(
            args.compose_file, args.database_user, args.source_database
        )
        dump = run(
            compose_command(
                args.compose_file,
                "exec",
                "-T",
                "postgres",
                "pg_dump",
                "-U",
                args.database_user,
                "-d",
                args.source_database,
                "-Fc",
            ),
            capture_bytes=True,
        )
        assert isinstance(dump, bytes)
        backup_path.write_bytes(dump)
        run(
            compose_command(
                args.compose_file,
                "cp",
                str(backup_path),
                f"postgres:{container_backup}",
            )
        )
        copied_backup = True
        run(
            compose_command(
                args.compose_file,
                "exec",
                "-T",
                "postgres",
                "pg_restore",
                "-l",
                container_backup,
            )
        )
        run(
            compose_command(
                args.compose_file,
                "exec",
                "-T",
                "postgres",
                "createdb",
                "-U",
                args.database_user,
                restore_database,
            )
        )
        created_restore = True
        run(
            compose_command(
                args.compose_file,
                "exec",
                "-T",
                "postgres",
                "pg_restore",
                "-U",
                args.database_user,
                "-d",
                restore_database,
                "--exit-on-error",
                container_backup,
            )
        )
        restored_snapshot = database_snapshot(
            args.compose_file, args.database_user, restore_database
        )
        if restored_snapshot != source_snapshot:
            raise RuntimeError("restored schema revision or verified table counts differ")
        status = "passed"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if created_restore and not args.keep_restore_db:
            try:
                run(
                    compose_command(
                        args.compose_file,
                        "exec",
                        "-T",
                        "postgres",
                        "dropdb",
                        "-U",
                        args.database_user,
                        "--force",
                        restore_database,
                    )
                )
                created_restore = False
            except Exception as cleanup_exc:
                error = f"{error}; cleanup: {cleanup_exc}".strip("; ")
                status = "failed"
        if copied_backup:
            try:
                run(
                    compose_command(
                        args.compose_file,
                        "exec",
                        "-T",
                        "postgres",
                        "rm",
                        "-f",
                        container_backup,
                    )
                )
            except Exception as cleanup_exc:
                error = f"{error}; container cleanup: {cleanup_exc}".strip("; ")
                status = "failed"

    backup_exists = backup_path.exists()
    result = {
        "status": status,
        "source_database": args.source_database,
        "restore_database": restore_database,
        "restore_database_retained": created_restore,
        "alembic_revision": source_snapshot.get("alembic_version", ""),
        "verified_tables": list(VERIFIED_TABLES),
        "source_snapshot": source_snapshot,
        "restored_snapshot": restored_snapshot,
        "backup_bytes": backup_path.stat().st_size if backup_exists else 0,
        "backup_sha256": hashlib.sha256(backup_path.read_bytes()).hexdigest()
        if backup_exists
        else "",
        "duration_seconds": round(time.perf_counter() - started, 3),
        "error": error,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if status == "passed" and args.delete_backup_after_verify and backup_exists:
        backup_path.unlink()
    if status != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
