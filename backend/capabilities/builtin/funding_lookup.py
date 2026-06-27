"""
Funding Lookup Capability
==========================
Searches for company funding information via Tavily (Crunchbase via web search).
"""

from typing import Any
from capabilities.base import CapabilityPlugin
from config import settings


class FundingLookupPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "business_intelligence.funding_lookup"

    @property
    def display_name(self) -> str:
        return "Funding Information Lookup"

    @property
    def description(self) -> str:
        return "Search for company funding rounds, investors, and total capital raised."

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {"company_name": str}
        """
        company_name = input.get("company_name", "")
        query = f"{company_name} funding round investors raised capital Crunchbase 2024 2025"

        if settings.TAVILY_API_KEY:
            try:
                from tavily import TavilyClient
                client = TavilyClient(api_key=settings.TAVILY_API_KEY)
                response = client.search(query=query, max_results=5)
                results = response.get("results", [])
                return {
                    "success": True,
                    "data": {
                        "raw_content": "\n\n".join(r.get("content", "") for r in results[:3]),
                        "search_results": results,
                    },
                    "source": "tavily_crunchbase",
                }
            except Exception as e:
                return {"success": False, "data": {}, "source": "funding_lookup", "error": str(e)}

        return {"success": False, "data": {}, "source": "funding_lookup", "error": "No Tavily API key"}
