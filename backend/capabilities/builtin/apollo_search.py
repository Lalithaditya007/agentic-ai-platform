"""
Apollo.io Company Search Capability
=====================================
Uses Apollo.io's free People & Company Search API to find companies
matching a given industry, location, and employee size range.

Free tier: ~50 enrichments/month.
Sign up at: https://app.apollo.io/ → API Keys

Returns structured company records with domain, employee count, LinkedIn URL.
"""

from typing import Any
from capabilities.base import CapabilityPlugin
from config import settings


class ApolloCompanySearchPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "company_data.apollo_search"

    @property
    def display_name(self) -> str:
        return "Apollo.io Company Search"

    @property
    def description(self) -> str:
        return "Search Apollo.io's 275M company database by industry, location, and size. Returns verified company profiles with domains and employee counts."

    def health_check(self) -> bool:
        return bool(settings.APOLLO_API_KEY)

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {
                "industry": list[str] or str,
                "location": list[str] or str,
                "employee_min": int (optional),
                "employee_max": int (optional),
                "limit": int (default 10)
            }
        Returns:
            {"success": bool, "data": list[dict], "source": "apollo"}
        """
        if not settings.APOLLO_API_KEY:
            return {"success": False, "data": [], "source": "apollo", "error": "No APOLLO_API_KEY set"}

        industry = input.get("industry", [])
        location = input.get("location", [])
        employee_min = input.get("employee_min", 1)
        employee_max = input.get("employee_max", 100000)
        limit = min(input.get("limit", 10), 25)  # Apollo free tier limits

        if isinstance(industry, str):
            industry = [industry]
        if isinstance(location, str):
            location = [location]

        try:
            import requests

            # Apollo Organization Search endpoint
            payload = {
                "api_key": settings.APOLLO_API_KEY,
                "page": 1,
                "per_page": limit,
            }

            # Industry keywords
            if industry:
                payload["organization_industry_tag_ids"] = []
                payload["q_organization_keyword_tags"] = industry[:5]

            # Location
            if location:
                payload["organization_locations"] = location[:5]

            # Employee range bands Apollo uses: "1,10", "11,20", "21,50", "51,100",
            # "101,200", "201,500", "501,1000", "1001,2000", "2001,5000", "5001,10000", "10001,"
            def _emp_range(mn: int, mx: int) -> list[str]:
                bands = [
                    (1, 10), (11, 20), (21, 50), (51, 100),
                    (101, 200), (201, 500), (501, 1000),
                    (1001, 2000), (2001, 5000), (5001, 10000), (10001, 999999),
                ]
                return [
                    f"{lo},{hi if hi < 999999 else ''}"
                    for lo, hi in bands
                    if lo <= mx and hi >= mn
                ]

            num_ranges = _emp_range(employee_min, employee_max)
            if num_ranges:
                payload["organization_num_employees_ranges"] = num_ranges

            resp = requests.post(
                "https://api.apollo.io/v1/mixed_companies/search",
                json=payload,
                timeout=15,
            )

            if resp.status_code != 200:
                return {
                    "success": False, "data": [], "source": "apollo",
                    "error": f"Apollo API returned {resp.status_code}: {resp.text[:200]}"
                }

            data = resp.json()
            orgs = data.get("organizations", []) or []

            companies = []
            for org in orgs[:limit]:
                companies.append({
                    "name": org.get("name", ""),
                    "domain": org.get("primary_domain", "") or "",
                    "website": org.get("website_url", "") or "",
                    "industry": org.get("industry", ""),
                    "employee_count": org.get("estimated_num_employees"),
                    "headquarters": ", ".join(filter(None, [
                        org.get("city", ""), org.get("country", "")
                    ])),
                    "linkedin_url": org.get("linkedin_url", ""),
                    "description": org.get("short_description", ""),
                    "source": "apollo",
                })

            return {"success": True, "data": companies, "source": "apollo"}

        except Exception as e:
            return {"success": False, "data": [], "source": "apollo", "error": str(e)}
