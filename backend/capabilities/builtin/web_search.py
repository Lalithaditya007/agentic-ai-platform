"""
Web Search Capability — Tavily
================================
Provides web search results via Tavily API.
Falls back to empty results if API key is not set.
"""

from typing import Any
from capabilities.base import CapabilityPlugin
from config import settings


class TavilyWebSearchPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "search.web_search"

    @property
    def display_name(self) -> str:
        return "Tavily Web Search"

    @property
    def description(self) -> str:
        return "Search the web for company information, news, and business intelligence using Tavily."

    def health_check(self) -> bool:
        return bool(settings.TAVILY_API_KEY)

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {"query": str, "max_results": int (default 5)}
        Returns:
            {"success": bool, "data": list[dict], "source": "tavily"}
        """
        query = input.get("query", "")
        max_results = input.get("max_results", 5)

        if not settings.TAVILY_API_KEY:
            return {"success": False, "data": [], "source": "tavily", "error": "No API key"}

        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=settings.TAVILY_API_KEY)
            response = client.search(query=query, max_results=max_results)
            results = response.get("results", [])
            return {"success": True, "data": results, "source": "tavily"}
        except Exception as e:
            return {"success": False, "data": [], "source": "tavily", "error": str(e)}
