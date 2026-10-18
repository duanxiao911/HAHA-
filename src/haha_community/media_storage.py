"""Durable filesystem media adapter with path confinement and atomic commits."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class MediaStorageError(RuntimeError):
    pass


class FileSystemMediaStorage:
    def __init__(self, root: str | Path | None = None) -> None:
        configured = root or os.getenv("HAHA_MEDIA_ROOT", "data/community-media")
        self.root = Path(configured).resolve()
        self.staging_root = self.root / ".staging"
        self.root.mkdir(parents=True, exist_ok=True)
        self.staging_root.mkdir(parents=True, exist_ok=True)

    def create_staging_path(self) -> Path:
        descriptor, raw_path = tempfile.mkstemp(prefix="upload-", dir=self.staging_root)
        os.close(descriptor)
        return Path(raw_path)

    def commit(self, staged_path: Path, storage_key: str) -> Path:
        target = self._resolve(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            staged_path.replace(target)
        except OSError as exc:
            raise MediaStorageError("媒体文件写入失败") from exc
        return target

    def path_for(self, storage_key: str) -> Path:
        path = self._resolve(storage_key)
        if not path.is_file():
            raise MediaStorageError("媒体文件不存在")
        return path

    def delete(self, storage_key: str) -> None:
        path = self._resolve(storage_key)
        path.unlink(missing_ok=True)

    @staticmethod
    def discard(path: Path) -> None:
        path.unlink(missing_ok=True)

    def _resolve(self, storage_key: str) -> Path:
        if not storage_key or "\\" in storage_key:
            raise MediaStorageError("媒体存储键无效")
        candidate = (self.root / storage_key).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise MediaStorageError("媒体存储路径越界") from exc
        return candidate
