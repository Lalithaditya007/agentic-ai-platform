"""
SEC EDGAR Company Search Capability  (v3 — Correct JSON Endpoint)
==================================================================
Uses SEC EDGAR's EFTS (full-text search) JSON API which returns
actual company names from 10-K filers. 100% free, no auth required.

Endpoint: https://efts.sec.gov/LATEST/search-index
- Returns `display_names` field with company name + ticker
- Returns `biz_locations` for headquarters city/state
- Returns `sics` for industry SIC code
"""

import re
from typing import Any
from capabilities.base import CapabilityPlugin

# SIC code prefix → industry label
_SIC_LABELS = {
    "80": "Healthcare",
    "81": "Legal Services",
    "82": "Educational Services",
    "73": "Technology / IT Services",
    "72": "R&D / Scientific",
    "67": "Financial Services",
    "64": "Insurance",
    "63": "Financial Services",
    "62": "Finance",
    "60": "Banking",
    "61": "Credit Services",
    "70": "Management Consulting",
    "50": "Wholesale Trade",
    "51": "Wholesale Trade",
    "52": "Retail",
    "59": "Retail",
    "35": "Industrial Machinery",
    "36": "Electronics",
    "28": "Chemicals / Pharma",
    "26": "Manufacturing",
    "48": "Telecom",
    "49": "Utilities",
    "45": "Airlines",
    "40": "Transportation",
}


def _sic_to_industry(sic_codes: list) -> str:
    for sic in sic_codes:
        prefix = str(sic)[:2]
        label = _SIC_LABELS.get(prefix)
        if label:
            return label
    return ""


def _extract_company_name(display_name: str) -> str:
    """Extract clean company name from 'Company Name (TICKER) (CIK 000...)' format."""
    m = re.match(r"^(.+?)\s+\([A-Z]+\)\s+\(CIK", display_name)
    if m:
        return m.group(1).strip()
    m2 = re.match(r"^(.+?)\s+\(CIK", display_name)
    if m2:
        return m2.group(1).strip()
    return display_name.strip()


class SecEdgarSearchPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "company_data.sec_edgar_search"

    @property
    def display_name(self) -> str:
        return "SEC EDGAR Company Search (US)"

    @property
    def description(self) -> str:
        return "Search all US public companies via SEC EDGAR 10-K filers. Free, no API key. Returns company name, ticker, location, and industry SIC code."

    def health_check(self) -> bool:
        return True

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {
                "query": str — industry keyword (e.g. "hospital", "software"),
                "limit": int (default 20)
            }
        Returns:
            {"success": bool, "data": list[dict], "source": "sec_edgar"}
        """
        query = input.get("query", "")
        limit = min(input.get("limit", 20), 100)

        if not query:
            return {"success": False, "data": [], "source": "sec_edgar", "error": "No query provided"}

        try:
            import requests

            headers = {"User-Agent": "XLVenture contact@xlventure.com"}

            resp = requests.get(
                "https://efts.sec.gov/LATEST/search-index",
                params={
                    "q": query,           # no quotes — broader match
                    "dateRange": "custom",
                    "startdt": "2022-01-01",
                    "forms": "10-K",
                },
                headers=headers,
                timeout=15,
            )

            companies = []

            if resp.status_code == 200:
                hits = resp.json().get("hits", {}).get("hits", []) or []
                seen_names: set[str] = set()

                for hit in hits[:limit]:
                    src = hit.get("_source", {})
                    display_names = src.get("display_names", []) or []
                    sics = src.get("sics", []) or []
                    locations = src.get("biz_locations", []) or []
                    ciks = src.get("ciks", []) or []

                    for dn in display_names:
                        name = _extract_company_name(dn)
                        if not name or name in seen_names:
                            continue
                        seen_names.add(name)

                        location = locations[0] if locations else "United States"
                        if location and "United States" not in location:
                            location = f"{location}, United States"

                        cik = ciks[0] if ciks else ""

                        companies.append({
                            "name": name,
                            "domain": "",
                            "industry": _sic_to_industry(sics),
                            "headquarters": location,
                            "employee_count": None,
                            "cik": cik,
                            "source": "sec_edgar",
                            "trigger_source": "sec_filing",
                            "trigger_confidence": 0.72,
                            "trigger_detail": f"Active SEC 10-K filer — {_sic_to_industry(sics) or 'US public company'}",
                        })

            return {"success": True, "data": companies, "source": "sec_edgar"}

        except Exception as e:
            return {"success": False, "data": [], "source": "sec_edgar", "error": str(e)}
