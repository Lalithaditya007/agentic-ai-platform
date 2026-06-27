"""
Hiring Analysis Capability
===========================
Analyzes hiring trends from LinkedIn job postings via web search.
"""

from typing import Any
from capabilities.base import CapabilityPlugin
from config import settings


class HiringAnalysisPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "business_intelligence.hiring_analysis"

    @property
    def display_name(self) -> str:
        return "Hiring Trend Analysis"

    @property
    def description(self) -> str:
        return "Analyze hiring trends and open positions to identify growth signals and tech stack."

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {"company_name": str, "domain": str (optional)}
        """
        company_name = input.get("company_name", "")
        query = f"{company_name} jobs hiring 2024 2025 LinkedIn positions open roles technology"

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
                    "source": "tavily_linkedin",
                }
            except Exception as e:
                return {"success": False, "data": {}, "source": "hiring_analysis", "error": str(e)}

        return {"success": False, "data": {}, "source": "hiring_analysis", "error": "No Tavily API key"}
