from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.media_restore_drill import (
    directory_manifest,
    manifest_digest,
    restore_archive,
    validate_archive_name,
    validate_member_name,
)


def test_media_archive_names_and_members_are_confined() -> None:
    validate_archive_name("haha_media_20261019_120000_a1b2c3d4.zip")
    assert validate_member_name("workspace/submission/asset.mp4").as_posix().endswith(
        "asset.mp4"
    )
    for unsafe in ("../secret", "/absolute", ".staging/upload", "a\\b"):
        with pytest.raises(ValueError):
            validate_member_name(unsafe)


def test_media_archive_restores_the_exact_manifest(tmp_path: Path) -> None:
    archive = tmp_path / "media.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("workspace/submission/asset.mp4", b"real-media-bytes")
    restore_root = tmp_path / "restore"
    restore_root.mkdir()

    restored = restore_archive(archive, restore_root)

    assert restored == directory_manifest(restore_root)
    assert restored["workspace/submission/asset.mp4"]["byte_size"] == 16
    assert len(manifest_digest(restored)) == 64


def test_media_archive_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.txt", b"escape")

    with pytest.raises(ValueError, match="unsafe"):
        restore_archive(archive, tmp_path / "restore")
