"""
Companies House (UK) API Capability
======================================
Queries the UK's official Companies House registry — 100% free, no API key
needed for basic search (though registration gives higher limits).

Register for a free key at: https://developer.company-information.service.gov.uk/

Best for: ICP targeting UK-based companies of any industry.
Returns: registered company name, number, status, address, SIC codes.
"""

from typing import Any
from capabilities.base import CapabilityPlugin
from config import settings

# SIC code → industry label mapping (partial — most common B2B categories)
_SIC_INDUSTRY_LABELS = {
    "62": "Software & IT Services",
    "63": "Information Services",
    "64": "Financial Services",
    "65": "Insurance",
    "66": "Financial Auxiliaries",
    "68": "Real Estate",
    "69": "Legal & Accounting",
    "70": "Management Consulting",
    "71": "Architecture & Engineering",
    "72": "Scientific Research & Development",
    "73": "Advertising & Marketing",
    "74": "Professional Services",
    "77": "Rental & Leasing",
    "78": "Employment Activities",
    "79": "Travel & Tourism",
    "80": "Security Services",
    "82": "Administrative Services",
    "85": "Education",
    "86": "Human Health Activities",
    "87": "Residential Care",
    "88": "Social Work",
    "26": "Manufacturing — Electronics",
    "27": "Electrical Equipment",
    "28": "Machinery & Equipment",
    "29": "Motor Vehicles",
    "30": "Other Transport Equipment",
    "32": "Manufacturing — Other",
    "45": "Wholesale & Retail — Motor",
    "46": "Wholesale Trade",
    "47": "Retail Trade",
}


def _sic_to_industry(sic_codes: list) -> str:
    for code in sic_codes:
        code_str = str(code).strip()[:2]
        label = _SIC_INDUSTRY_LABELS.get(code_str)
        if label:
            return label
    return ""


class CompaniesHouseSearchPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "company_data.companies_house_search"

    @property
    def display_name(self) -> str:
        return "Companies House (UK) Registry Search"

    @property
    def description(self) -> str:
        return "Search all UK-registered companies via Companies House. Free, official, real-time. Best for ICP targeting UK companies."

    def health_check(self) -> bool:
        return True  # Free without key (rate limited); better with key

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {
                "query": str — company name / industry keywords,
                "limit": int (default 10)
            }
        Returns:
            {"success": bool, "data": list[dict], "source": "companies_house"}
        """
        query = input.get("query", "")
        limit = min(input.get("limit", 10), 40)

        if not query:
            return {"success": False, "data": [], "source": "companies_house", "error": "No query provided"}

        try:
            import requests

            headers = {"Accept": "application/json"}
            auth = None

            # Use API key if available (registered key gives higher rate limits)
            if settings.COMPANIES_HOUSE_API_KEY:
                auth = (settings.COMPANIES_HOUSE_API_KEY, "")

            params = {
                "q": query,
                "items_per_page": limit,
                "restrictions": "active-companies",
            }

            resp = requests.get(
                "https://api.company-information.service.gov.uk/search/companies",
                params=params,
                headers=headers,
                auth=auth,
                timeout=12,
            )

            if resp.status_code == 401:
                # Retry without auth (anonymous access is allowed but limited)
                resp = requests.get(
                    "https://api.company-information.service.gov.uk/search/companies",
                    params=params,
                    headers=headers,
                    timeout=12,
                )

            if resp.status_code != 200:
                return {
                    "success": False, "data": [], "source": "companies_house",
                    "error": f"HTTP {resp.status_code}"
                }

            data = resp.json()
            items = data.get("items", []) or []

            companies = []
            for item in items[:limit]:
                name = item.get("title", "")
                if not name:
                    continue
                address = item.get("address", {}) or {}
                sic_codes = item.get("sic_codes", []) or []
                companies.append({
                    "name": name,
                    "domain": "",  # Not in Companies House data
                    "industry": _sic_to_industry(sic_codes),
                    "headquarters": ", ".join(filter(None, [
                        address.get("locality", ""),
                        address.get("region", ""),
                        "United Kingdom",
                    ])),
                    "employee_count": None,
                    "company_number": item.get("company_number", ""),
                    "company_status": item.get("company_status", ""),
                    "companies_house_url": f"https://find-and-update.company-information.service.gov.uk/company/{item.get('company_number', '')}",
                    "source": "companies_house",
                })

            return {"success": True, "data": companies, "source": "companies_house"}

        except Exception as e:
            return {"success": False, "data": [], "source": "companies_house", "error": str(e)}
