"""Runtime assembly for commerce persistence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from haha_commerce.repository import CommerceRepository
from haha_commerce.sqlalchemy_repository import SQLAlchemyCommerceRepository


def build_commerce_repository(active_repository: Any = None) -> CommerceRepository:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return SQLAlchemyCommerceRepository(database_url)
    if active_repository is not None and hasattr(active_repository, "path"):
        return SQLAlchemyCommerceRepository.for_sqlite_path(getattr(active_repository, "path"))
    return SQLAlchemyCommerceRepository.for_sqlite_path(
        Path(os.getenv("HAHA_COMMERCE_DB", "data/haha_commerce.db"))
    )
