"""Runtime assembly kept separate from HTTP and worker entry points."""

from __future__ import annotations

import os
from pathlib import Path

from haha_core.repository import CreatorRepository, SQLiteCreatorRepository
from haha_core.sqlalchemy_repository import SQLAlchemyCreatorRepository


def build_repository() -> CreatorRepository:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return SQLAlchemyCreatorRepository(database_url)
    return SQLiteCreatorRepository(Path(os.getenv("HAHA_CORE_DB", "data/haha_core.db")))


def enqueue_run(run_id: str, request_id: str = "") -> bool:
    """Return True when a durable broker accepted the run."""
    if not os.getenv("REDIS_URL", "").strip():
        return False
    from haha_worker.tasks import execute_creator_run

    execute_creator_run.send(run_id, request_id)
    return True
