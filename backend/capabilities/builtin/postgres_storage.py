"""
PostgreSQL Storage Capability
==============================
Provides raw read/write access to PostgreSQL for agents.
"""

from typing import Any
from capabilities.base import CapabilityPlugin


class PostgreSQLStoragePlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "storage.postgresql"

    @property
    def display_name(self) -> str:
        return "PostgreSQL Storage"

    @property
    def description(self) -> str:
        return "Read and write structured data to PostgreSQL database."

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        This plugin is a marker — actual DB operations are done via
        database.models (SQLAlchemy) directly in agents.
        The plugin exists to enforce allowlist capability scoping.
        """
        return {"success": True, "data": {"note": "PostgreSQL available"}, "source": "postgresql"}
