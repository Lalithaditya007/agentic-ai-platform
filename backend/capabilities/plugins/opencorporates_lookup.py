"""
OpenCorporates Company Lookup Plugin
======================================
A real working CUSTOM plugin that demonstrates the Plugin SDK end-to-end.

This is a third-party plugin (lives in capabilities/plugins/, NOT builtin/).
It uses the OpenCorporates free public API — no API key required.

Plugin SDK proof:
  1. File placed in capabilities/plugins/
  2. Entry added to registry.yaml
  3. Auto-discovered on startup via CapabilityRegistry.load_from_yaml()
  4. Agent Architect can now select "business_intelligence.opencorporates_lookup"
  5. Runtime Agent Manager injects it into agent execution context

OpenCorporates API:
  - Endpoint: https://api.opencorporates.com/v0.4/companies/search
  - Free tier: 500 req/day, no key needed
  - Returns: company name, jurisdiction, registered address, status, incorporation date
"""

import httpx
from typing import Any

from capabilities.base import CapabilityPlugin


class OpenCorporatesLookupPlugin(CapabilityPlugin):
    """
    Custom plugin: looks up company registration data from OpenCorporates.
    Provides verified legal entity information for company validation.
    """

    BASE_URL = "https://api.opencorporates.com/v0.4"
    TIMEOUT_SECONDS = 10

    @property
    def capability_id(self) -> str:
        return "business_intelligence.opencorporates_lookup"

    @property
    def display_name(self) -> str:
        return "OpenCorporates Company Lookup"

    @property
    def description(self) -> str:
        return (
            "Looks up legal company registration data from the OpenCorporates public database. "
            "Returns verified company name, jurisdiction, registered address, incorporation date, "
            "and current active/inactive status. Free API — no key required. "
            "Use for: company existence verification, registered address confirmation, "
            "legal entity cross-referencing."
        )

    def health_check(self) -> bool:
        """Verify the OpenCorporates API is reachable."""
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self.BASE_URL}/companies/search?q=apple&per_page=1")
                return resp.status_code == 200
        except Exception as e:
            print(f"[OpenCorporates] Health check failed: {e}")
            return False

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Look up a company by name (and optionally jurisdiction).

        Input:
            company_name (str): Company name to search
            jurisdiction (str, optional): Country/state code e.g. "us_ca", "gb", "de"
            per_page (int, optional): Results to return (default 5, max 100)

        Returns:
            success (bool)
            data (list[dict]): Matching companies from OpenCorporates
            source (str): API endpoint used
            count (int): Number of matches found
        """
        company_name = input.get("company_name", "")
        jurisdiction = input.get("jurisdiction", "")
        per_page = min(input.get("per_page", 5), 20)

        if not company_name:
            return {
                "success": False,
                "data": [],
                "source": self.BASE_URL,
                "count": 0,
                "error": "company_name is required",
            }

        params = {
            "q": company_name,
            "per_page": per_page,
            "format": "json",
        }
        if jurisdiction:
            params["jurisdiction_code"] = jurisdiction

        try:
            with httpx.Client(timeout=self.TIMEOUT_SECONDS) as client:
                resp = client.get(f"{self.BASE_URL}/companies/search", params=params)
                resp.raise_for_status()
                raw = resp.json()

            companies_raw = (
                raw.get("results", {}).get("companies", [])
            )

            companies = []
            for item in companies_raw:
                c = item.get("company", {})
                companies.append({
                    "name": c.get("name", ""),
                    "company_number": c.get("company_number", ""),
                    "jurisdiction_code": c.get("jurisdiction_code", ""),
                    "incorporation_date": c.get("incorporation_date", ""),
                    "dissolution_date": c.get("dissolution_date", ""),
                    "company_type": c.get("company_type", ""),
                    "current_status": c.get("current_status", ""),
                    "registered_address": c.get("registered_address", {}).get("street_address", ""),
                    "opencorporates_url": c.get("opencorporates_url", ""),
                    "is_active": c.get("current_status", "").lower()
                    not in ["dissolved", "inactive", "struck off"],
                })

            return {
                "success": True,
                "data": companies,
                "source": f"{self.BASE_URL}/companies/search?q={company_name}",
                "count": len(companies),
            }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "data": [],
                "source": self.BASE_URL,
                "count": 0,
                "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            }
        except Exception as e:
            return {
                "success": False,
                "data": [],
                "source": self.BASE_URL,
                "count": 0,
                "error": str(e),
            }
