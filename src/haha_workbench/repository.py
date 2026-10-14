"""Persistence contract needed by the workbench read model."""

from __future__ import annotations

from typing import Protocol

from haha_core.domain import Project
from haha_user_center.repository import UserCenterRepository


class WorkbenchRepository(UserCenterRepository, Protocol):
    def list_projects(self, workspace_id: str, *, limit: int = 20) -> list[Project]: ...
