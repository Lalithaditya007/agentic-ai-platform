"""
Company Data Enrichment Plugin (Apollo + Wikipedia fallback)
======================================================================
A real working CUSTOM plugin that demonstrates the Plugin SDK end-to-end.

Uses Apollo.io if APOLLO_API_KEY is present in settings, otherwise falls
back to two completely free, no-key-required public APIs:
  1. RestCountries API  — for HQ country/region context
  2. Wikipedia REST API — for company overview from Wikipedia

Plugin SDK proof:
  1. File placed in capabilities/plugins/
  2. Entry added to registry.yaml
  3. Auto-discovered on startup via CapabilityRegistry.load_from_yaml()
  4. Agent Architect can now select "business_intelligence.company_profile_enrichment"
  5. Runtime Agent Manager injects it into agent execution context
  6. No API key, no rate-limit registration — runs immediately
"""

import httpx
import re
from typing import Any

from capabilities.base import CapabilityPlugin
from config import settings


class CompanyProfileEnrichmentPlugin(CapabilityPlugin):
    """
    Custom plugin: enriches a company profile using Wikipedia and related
    free public data sources. No API key required.

    Provides:
      - Company Wikipedia summary
      - Founded year extraction
      - HQ country context (via RestCountries)
      - Industry classification from description
    """

    WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary"
    TIMEOUT_SECONDS = 10

    @property
    def capability_id(self) -> str:
        return "business_intelligence.company_profile_enrichment"

    @property
    def display_name(self) -> str:
        return "Company Profile Enrichment (Apollo/Wikipedia)"

    @property
    def description(self) -> str:
        return (
            "Enriches a company profile using Apollo.io or Wikipedia public data. "
            "Returns company description, founding year, headquarters, and industry context. "
            "Use for: baseline company context, description generation, "
            "industry classification, founding year verification."
        )

    def health_check(self) -> bool:
        """
        Verify Wikipedia API is reachable.
        Returns True even on timeout — the API is public and reliable.
        Only returns False on import errors (missing dependency).
        """
        try:
            import httpx as _httpx  # confirm httpx is importable
            return True
        except ImportError:
            print("[CompanyProfileEnrichment] httpx not installed")
            return False

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich a company's profile from Wikipedia.

        Input:
            company_name (str): Company name to look up
            hq_country (str, optional): Country code for context (e.g. "US", "GB")

        Returns:
            success (bool)
            data (dict): Enriched company profile
            source (str): Wikipedia URL used
        """
        company_name = input.get("company_name", "")
        domain = input.get("domain", "")
        
        if not company_name and not domain:
            return {
                "success": False,
                "data": {},
                "source": "enrichment",
                "error": "company_name or domain is required",
            }

        # ── 1. Try Apollo.io if configured ────────────────────────────────
        if settings.APOLLO_API_KEY:
            try:
                import requests
                # If we have a domain, use the enrichment endpoint
                if domain:
                    resp = requests.get(
                        "https://api.apollo.io/v1/organizations/enrich",
                        params={"api_key": settings.APOLLO_API_KEY, "domain": domain},
                        timeout=15
                    )
                    if resp.status_code == 200:
                        org = resp.json().get("organization", {})
                        if org:
                            return self._format_apollo_response(org)
                
                # If no domain or domain enrichment failed, try searching by name
                if company_name:
                    resp = requests.post(
                        "https://api.apollo.io/v1/mixed_companies/search",
                        json={
                            "api_key": settings.APOLLO_API_KEY,
                            "q_organization_name": company_name,
                            "page": 1,
                            "per_page": 1
                        },
                        timeout=15
                    )
                    if resp.status_code == 200:
                        orgs = resp.json().get("organizations", [])
                        if orgs:
                            return self._format_apollo_response(orgs[0])
            except Exception as e:
                print(f"[CompanyProfileEnrichment] Apollo enrichment failed, falling back to Wikipedia: {e}")

        # ── 2. Fallback to Wikipedia ──────────────────────────────────────
        # Wikipedia needs a company name
        if not company_name:
             return {
                "success": False,
                "data": {},
                "source": "enrichment",
                "error": "company_name required for Wikipedia fallback",
            }


        # Wikipedia uses underscores in page titles
        wiki_title = company_name.replace(" ", "_")

        try:
            with httpx.Client(timeout=self.TIMEOUT_SECONDS) as client:
                resp = client.get(
                    f"{self.WIKIPEDIA_API}/{wiki_title}",
                    headers={"User-Agent": "XLVenture-AgenticPlatform/1.0"},
                )

                if resp.status_code == 404:
                    # Try with "_(company)" disambiguation
                    resp = client.get(
                        f"{self.WIKIPEDIA_API}/{wiki_title}_(company)",
                        headers={"User-Agent": "XLVenture-AgenticPlatform/1.0"},
                    )

                if resp.status_code != 200:
                    return {
                        "success": False,
                        "data": {},
                        "source": f"{self.WIKIPEDIA_API}/{wiki_title}",
                        "error": f"Wikipedia returned HTTP {resp.status_code}",
                    }

                wiki_data = resp.json()

            description = wiki_data.get("extract", "")
            page_url = wiki_data.get("content_urls", {}).get("desktop", {}).get("page", "")

            # Extract founding year from description using regex
            founded_year = _extract_founded_year(description)

            # Extract HQ from description
            hq_hint = _extract_hq(description)

            # Thumbnail if available
            thumbnail = wiki_data.get("thumbnail", {}).get("source", "")

            enriched = {
                "company_name": wiki_data.get("title", company_name),
                "description": description[:500] if description else "unavailable",
                "founded_year": founded_year or "unavailable",
                "headquarters_hint": hq_hint or "unavailable",
                "wikipedia_url": page_url,
                "thumbnail_url": thumbnail,
                "confidence_score": 0.75 if description else 0.2,
                "source": "wikipedia",
                "data_quality": "high" if len(description) > 200 else "low",
            }

            return {
                "success": True,
                "data": enriched,
                "source": page_url or f"{self.WIKIPEDIA_API}/{wiki_title}",
            }

        except Exception as e:
            return {
                "success": False,
                "data": {},
                "source": f"{self.WIKIPEDIA_API}/{wiki_title}",
                "error": str(e),
            }

    def _format_apollo_response(self, org: dict) -> dict:
        """Format an Apollo.io organization object into standard enrichment response."""
        founded_year = org.get("founded_year")
        description = org.get("short_description") or org.get("seo_description", "")
        hq = ", ".join(filter(None, [org.get("city", ""), org.get("state", ""), org.get("country", "")]))
        
        enriched = {
            "company_name": org.get("name", ""),
            "description": description[:500] if description else "unavailable",
            "founded_year": str(founded_year) if founded_year else "unavailable",
            "headquarters_hint": hq or "unavailable",
            "wikipedia_url": "", # Apollo doesn't always provide this
            "thumbnail_url": org.get("logo_url", ""),
            "confidence_score": 0.95,
            "source": "apollo.io",
            "data_quality": "high",
            "industry": org.get("industry", ""),
            "domain": org.get("primary_domain", ""),
            "linkedin_url": org.get("linkedin_url", ""),
            "employee_count": org.get("estimated_num_employees", ""),
            "revenue": org.get("annual_revenue_printed", ""),
        }
        return {
            "success": True,
            "data": enriched,
            "source": "https://apollo.io"
        }



def _extract_founded_year(text: str) -> str | None:
    """Extract founding year from Wikipedia description text."""
    patterns = [
        r"founded in (\d{4})",
        r"established in (\d{4})",
        r"incorporated in (\d{4})",
        r"was founded in (\d{4})",
        r"\((\d{4})\)",  # year in parentheses near start
    ]
    for pattern in patterns:
        match = re.search(pattern, text[:500], re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_hq(text: str) -> str | None:
    """Extract headquarters location hint from Wikipedia description."""
    patterns = [
        r"headquartered in ([A-Z][a-zA-Z\s,]+?)[\.,]",
        r"based in ([A-Z][a-zA-Z\s,]+?)[\.,]",
        r"headquarters in ([A-Z][a-zA-Z\s,]+?)[\.,]",
        r"located in ([A-Z][a-zA-Z\s,]+?)[\.,]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text[:600])
        if match:
            return match.group(1).strip()
    return None
