"""
Email Lookup Capability — Hunter.io
=====================================
Discovers professional email addresses for decision makers using Hunter.io API.
Falls back to web-based pattern matching when quota exhausted.
"""

import httpx
from typing import Any
from capabilities.base import CapabilityPlugin
from config import settings


class HunterEmailLookupPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "contact_intelligence.email_lookup"

    @property
    def display_name(self) -> str:
        return "Email Lookup (Hunter.io)"

    @property
    def description(self) -> str:
        return "Find professional email addresses for contacts at a company using Hunter.io."

    def health_check(self) -> bool:
        return True  # Gracefully degrades without key

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {"domain": str, "first_name": str (optional), "last_name": str (optional)}
        Returns:
            {"success": bool, "data": {"email": str, "confidence": float}, "source": str}
        """
        domain = input.get("domain", "")
        first_name = input.get("first_name", "")
        last_name = input.get("last_name", "")

        if not settings.HUNTER_API_KEY or not domain:
            return {
                "success": False,
                "data": {"email": "unavailable", "confidence": 0.0},
                "source": "hunter",
                "error": "No Hunter API key or domain",
            }

        try:
            if first_name and last_name:
                # Find specific email
                url = "https://api.hunter.io/v2/email-finder"
                params = {
                    "domain": domain,
                    "first_name": first_name,
                    "last_name": last_name,
                    "api_key": settings.HUNTER_API_KEY,
                }
                resp = httpx.get(url, params=params, timeout=10)
                data = resp.json().get("data", {})
                email = data.get("email", "unavailable")
                confidence = (data.get("score", 0) or 0) / 100.0
                return {
                    "success": bool(email and email != "unavailable"),
                    "data": {"email": email or "unavailable", "confidence": confidence},
                    "source": "hunter.io",
                }
            else:
                # Domain search — get pattern
                url = "https://api.hunter.io/v2/domain-search"
                params = {"domain": domain, "limit": 3, "api_key": settings.HUNTER_API_KEY}
                resp = httpx.get(url, params=params, timeout=10)
                data = resp.json().get("data", {})
                pattern = data.get("pattern", "unavailable")
                emails = [e.get("value", "") for e in data.get("emails", [])[:3]]
                return {
                    "success": bool(emails),
                    "data": {"pattern": pattern, "sample_emails": emails},
                    "source": "hunter.io",
                }
        except Exception as e:
            return {
                "success": False,
                "data": {"email": "unavailable", "confidence": 0.0},
                "source": "hunter",
                "error": str(e),
            }
