"""
OpenCorporates Company Search Capability
==========================================
Queries OpenCorporates — the world's largest open database of companies
with 200M+ company registrations from 140+ jurisdictions.

Free: 500 requests/day with no API key (basic search).
Paid key extends limits — register at: https://opencorporates.com/api_accounts/new

Best for: finding officially registered companies in any country.
"""

from typing import Any
from capabilities.base import CapabilityPlugin
from config import settings


# Map of common geography strings to OpenCorporates jurisdiction codes
# Full list: https://api.opencorporates.com/v0.4/jurisdictions
_GEO_TO_JURISDICTION = {
    "us": "us",            "united states": "us",
    "uk": "gb",            "united kingdom": "gb",     "england": "gb",
    "germany": "de",       "de": "de",
    "france": "fr",        "fr": "fr",
    "india": "in",         "in": "in",
    "canada": "ca",        "ca": "ca",
    "australia": "au",     "au": "au",
    "singapore": "sg",     "sg": "sg",
    "uae": "ae",           "dubai": "ae",
    "netherlands": "nl",   "nl": "nl",
    "sweden": "se",        "se": "se",
    "eu": "gb",            "europe": None,             # EU → no specific jurisdiction, search broadly
}


def _geo_to_code(geo_list: list[str]) -> str | None:
    """Return the first matching OpenCorporates jurisdiction code."""
    for g in geo_list:
        code = _GEO_TO_JURISDICTION.get(g.lower().strip())
        if code:
            return code
    return None


class OpenCorporatesSearchPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "company_data.opencorporates_search"

    @property
    def display_name(self) -> str:
        return "OpenCorporates Company Registry Search"

    @property
    def description(self) -> str:
        return "Search OpenCorporates — 200M+ company registrations across 140 jurisdictions. Free 500 req/day. Best for finding officially registered companies globally."

    def health_check(self) -> bool:
        return True  # Free without key, better with key

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {
                "query": str — industry/company type keywords,
                "geography": list[str] — target geographies,
                "limit": int (default 10)
            }
        Returns:
            {"success": bool, "data": list[dict], "source": "opencorporates"}
        """
        query = input.get("query", "")
        geography = input.get("geography", [])
        limit = min(input.get("limit", 10), 30)

        if not query:
            return {"success": False, "data": [], "source": "opencorporates", "error": "No query provided"}

        try:
            import requests

            params: dict[str, Any] = {
                "q": query,
                "per_page": limit,
                "current_status": "Active",
                "sparse": "false",
            }

            # Add API key if available for higher rate limits
            if settings.OPENCORPORATES_API_KEY:
                params["api_token"] = settings.OPENCORPORATES_API_KEY

            # Scope to jurisdiction if we can map the geography
            jurisdiction = _geo_to_code(geography) if geography else None
            url = "https://api.opencorporates.com/v0.4/companies/search"
            if jurisdiction:
                params["jurisdiction_code"] = jurisdiction

            resp = requests.get(url, params=params, timeout=15)

            if resp.status_code == 429:
                return {
                    "success": False, "data": [], "source": "opencorporates",
                    "error": "Rate limited (500 free req/day). Add OPENCORPORATES_API_KEY for more."
                }
            if resp.status_code != 200:
                return {
                    "success": False, "data": [], "source": "opencorporates",
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}"
                }

            data = resp.json()
            raw_companies = (
                data.get("results", {}).get("companies", [])
                or []
            )

            companies = []
            for item in raw_companies[:limit]:
                c = item.get("company", {})
                name = c.get("name", "")
                if not name:
                    continue

                # Build domain guess from name if not provided
                domain_guess = c.get("registered_address", {}).get("country", "") or ""

                companies.append({
                    "name": name,
                    "domain": "",            # OpenCorporates doesn't provide domains
                    "industry": c.get("industry_codes", [{}])[0].get("description", "") if c.get("industry_codes") else "",
                    "headquarters": ", ".join(filter(None, [
                        c.get("registered_address", {}).get("locality", ""),
                        c.get("registered_address", {}).get("country", ""),
                    ])) if c.get("registered_address") else "",
                    "employee_count": None,  # Not available in OpenCorporates
                    "jurisdiction": c.get("jurisdiction_code", ""),
                    "company_number": c.get("company_number", ""),
                    "opencorporates_url": c.get("opencorporates_url", ""),
                    "source": "opencorporates",
                })

            return {"success": True, "data": companies, "source": "opencorporates"}

        except Exception as e:
            return {"success": False, "data": [], "source": "opencorporates", "error": str(e)}
