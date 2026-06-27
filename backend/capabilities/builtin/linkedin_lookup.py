"""
LinkedIn Lookup Capability
===========================
Searches LinkedIn profiles via Tavily web search (no official API needed).
"""

from typing import Any
from capabilities.base import CapabilityPlugin
from config import settings


class LinkedInLookupPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "contact_intelligence.linkedin_lookup"

    @property
    def display_name(self) -> str:
        return "LinkedIn Profile Lookup"

    @property
    def description(self) -> str:
        return "Find LinkedIn profiles for decision makers at target companies via web search."

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {"company_name": str, "persona_title": str}
        """
        company_name = input.get("company_name", "")
        title = input.get("persona_title", "")
        query = f'site:linkedin.com/in "{title}" "{company_name}"'

        if settings.TAVILY_API_KEY:
            try:
                from tavily import TavilyClient
                client = TavilyClient(api_key=settings.TAVILY_API_KEY)
                response = client.search(query=query, max_results=5)
                results = response.get("results", [])
                profiles = []
                for r in results:
                    url = r.get("url", "")
                    if "linkedin.com/in/" in url:
                        profiles.append({
                            "linkedin_url": url,
                            "title": r.get("title", ""),
                            "snippet": r.get("content", "")[:200],
                        })
                return {
                    "success": bool(profiles),
                    "data": {"profiles": profiles},
                    "source": "tavily_linkedin",
                }
            except Exception as e:
                return {"success": False, "data": {"profiles": []}, "source": "linkedin_lookup", "error": str(e)}

        return {"success": False, "data": {"profiles": []}, "source": "linkedin_lookup", "error": "No Tavily API key"}
