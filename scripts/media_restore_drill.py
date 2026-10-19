"""Back up the community media volume and verify an isolated local restore."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

ARCHIVE_NAME = re.compile(r"^haha_media_\d{8}_\d{6}_[0-9a-f]{8}\.zip$")
CONTAINER_MEDIA_ROOT = "/var/lib/haha/community-media"


def validate_archive_name(name: str) -> None:
    if not ARCHIVE_NAME.fullmatch(name):
        raise ValueError("media archive must use the generated haha_media_* name")


def validate_member_name(name: str) -> PurePosixPath:
    member = PurePosixPath(name)
    if (
        not name
        or member.is_absolute()
        or ".." in member.parts
        or "\\" in name
        or member.parts[0] == ".staging"
    ):
        raise ValueError(f"unsafe media archive member: {name!r}")
    return member


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_manifest(root: Path) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        validate_member_name(relative)
        result[relative] = {"byte_size": path.stat().st_size, "sha256": digest_file(path)}
    return result


def manifest_digest(manifest: dict[str, dict[str, object]]) -> str:
    rendered = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(rendered.encode()).hexdigest()


def run(command: Sequence[str]) -> str:
    result = subprocess.run(list(command), capture_output=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{stderr}")
    return result.stdout.decode(errors="replace").strip()


def compose_command(
    compose_file: Path, *arguments: str, project_name: str = ""
) -> list[str]:
    prefix = ["docker", "compose"]
    if project_name:
        prefix.extend(("-p", project_name))
    return [*prefix, "-f", str(compose_file), *arguments]


def database_manifest(
    compose_file: Path, user: str, database: str, project_name: str = ""
) -> dict[str, dict[str, object]]:
    sql = (
        "SELECT COALESCE(json_agg(json_build_object("
        "'storage_key',storage_key,'byte_size',byte_size,'sha256',sha256) "
        "ORDER BY storage_key),'[]'::json)::text FROM community_media_assets;"
    )
    output = run(compose_command(
        compose_file, "exec", "-T", "postgres", "psql", "-U", user,
        "-d", database, "-At", "-c", sql, project_name=project_name,
    ))
    rows = json.loads(output.splitlines()[-1])
    return {
        str(row["storage_key"]): {
            "byte_size": int(row["byte_size"]),
            "sha256": str(row["sha256"]),
        }
        for row in rows
    }


def create_container_archive(
    compose_file: Path, archive_name: str, project_name: str = ""
) -> dict[str, dict[str, object]]:
    validate_archive_name(archive_name)
    code = f"""
import hashlib, json, zipfile
from pathlib import Path
root = Path({CONTAINER_MEDIA_ROOT!r})
archive = Path('/tmp') / {archive_name!r}
manifest = {{}}
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(item for item in root.rglob('*') if item.is_file()):
        relative = path.relative_to(root)
        if '.staging' in relative.parts:
            continue
        data = path.read_bytes()
        name = relative.as_posix()
        bundle.writestr(name, data)
        manifest[name] = {{'byte_size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}}
print(json.dumps(manifest, sort_keys=True))
"""
    output = run(compose_command(
        compose_file, "exec", "-T", "api", "python", "-c", code,
        project_name=project_name,
    ))
    return json.loads(output.splitlines()[-1])


def restore_archive(archive_path: Path, restore_root: Path) -> dict[str, dict[str, object]]:
    with zipfile.ZipFile(archive_path) as bundle:
        for info in bundle.infolist():
            member = validate_member_name(info.filename)
            target = (restore_root / Path(*member.parts)).resolve()
            target.relative_to(restore_root.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
    return directory_manifest(restore_root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compose-file", type=Path, default=Path("compose.yaml"))
    parser.add_argument("--database", default="haha")
    parser.add_argument("--database-user", default="haha")
    parser.add_argument("--project-name", default="")
    parser.add_argument("--backup-path", type=Path)
    parser.add_argument(
        "--report", type=Path, default=Path("artifacts/recovery/gate-f-media-restore.json")
    )
    parser.add_argument("--require-files", action="store_true")
    parser.add_argument("--delete-backup-after-verify", action="store_true")
    args = parser.parse_args()

    timestamp = datetime.now(UTC)
    archive_name = f"haha_media_{timestamp:%Y%m%d_%H%M%S}_{uuid4().hex[:8]}.zip"
    validate_archive_name(archive_name)
    backup_path = args.backup_path or Path(
        f"artifacts/backups/{timestamp:%Y-%m-%d_%H%M%S}_gate-f-media.zip"
    )
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    status = "failed"
    error = ""
    source_manifest: dict[str, dict[str, object]] = {}
    database_state: dict[str, dict[str, object]] = {}
    restored_manifest: dict[str, dict[str, object]] = {}
    try:
        database_state = database_manifest(
            args.compose_file, args.database_user, args.database, args.project_name
        )
        source_manifest = create_container_archive(
            args.compose_file, archive_name, args.project_name
        )
        if args.require_files and not source_manifest:
            raise RuntimeError("media recovery drill requires at least one durable media file")
        if source_manifest != database_state:
            raise RuntimeError("media volume and PostgreSQL media metadata differ")
        run(compose_command(
            args.compose_file, "cp", f"api:/tmp/{archive_name}", str(backup_path),
            project_name=args.project_name,
        ))
        with tempfile.TemporaryDirectory(prefix="haha-media-restore-") as temporary:
            restored_manifest = restore_archive(backup_path, Path(temporary))
        if restored_manifest != source_manifest:
            raise RuntimeError("restored media manifest differs from source volume")
        status = "passed"
    except Exception as exc:  # noqa: BLE001 - evidence must retain the drill failure
        error = str(exc)
    finally:
        try:
            run(compose_command(
                args.compose_file, "exec", "-T", "api", "python", "-c",
                f"from pathlib import Path; Path('/tmp/{archive_name}').unlink(missing_ok=True)",
                project_name=args.project_name,
            ))
        except Exception as cleanup_exc:  # noqa: BLE001
            error = f"{error}; container cleanup failed: {cleanup_exc}".strip("; ")
            status = "failed"

    backup_exists = backup_path.is_file()
    result = {
        "status": status,
        "files": len(source_manifest),
        "bytes": sum(int(item["byte_size"]) for item in source_manifest.values()),
        "manifest_sha256": manifest_digest(source_manifest),
        "archive_bytes": backup_path.stat().st_size if backup_exists else 0,
        "archive_sha256": digest_file(backup_path) if backup_exists else "",
        "database_records": len(database_state),
        "restored_files": len(restored_manifest),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "error": error,
    }
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if status == "passed" and args.delete_backup_after_verify and backup_exists:
        backup_path.unlink()
    if status != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
