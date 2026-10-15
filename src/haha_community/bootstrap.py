"""Runtime assembly for the community persistence adapter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from haha_community.repository import CommunityRepository
from haha_community.sqlalchemy_repository import SQLAlchemyCommunityRepository


def build_community_repository(active_repository: Any = None) -> CommunityRepository:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return SQLAlchemyCommunityRepository(database_url)
    if active_repository is not None and hasattr(active_repository, "path"):
        path = getattr(active_repository, "path")
        return SQLAlchemyCommunityRepository.for_sqlite_path(path)
    path = Path(os.getenv("HAHA_COMMUNITY_DB", "data/haha_community.db"))
    return SQLAlchemyCommunityRepository.for_sqlite_path(path)
