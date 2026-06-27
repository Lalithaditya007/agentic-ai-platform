"""
Capability Plugin Base Class
=============================
All capability plugins must inherit from CapabilityPlugin.
New capabilities added via Plugin SDK — no core code changes needed.
"""

from abc import ABC, abstractmethod
from typing import Any


class CapabilityPlugin(ABC):

    @property
    @abstractmethod
    def capability_id(self) -> str:
        """Unique dot-notation identifier: category.name"""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name"""

    @property
    @abstractmethod
    def description(self) -> str:
        """What this capability does. Used by Agent Architect for selection."""

    @abstractmethod
    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the capability.
        Must return:
          - "success": bool
          - "data": Any
          - "source": str
        """

    def health_check(self) -> bool:
        return True
