"""Role-workbench state contracts independent of FastAPI and React."""

from __future__ import annotations

from enum import StrEnum


class CapabilityStatus(StrEnum):
    AVAILABLE = "available"
    LIMITED = "limited"
    BLOCKED = "blocked"


class WorkbenchMaturity(StrEnum):
    OPERATIONAL = "operational"
    PARTIAL = "partial"
    BLOCKED = "blocked"
