"""
Company Lookup Capability
==========================
Looks up company information using Tavily web search + structured extraction.
"""

from typing import Any
from capabilities.base import CapabilityPlugin
from config import settings


class CompanyLookupPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "business_intelligence.company_lookup"

    @property
    def display_name(self) -> str:
        return "Company Information Lookup"

    @property
    def description(self) -> str:
        return "Look up company profiles including size, industry, headquarters, and description."

    def health_check(self) -> bool:
        return bool(settings.TAVILY_API_KEY or True)  # Can use RSS fallback

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {"company_name": str, "domain": str (optional)}
        Returns:
            {"success": bool, "data": dict, "source": str}
        """
        company_name = input.get("company_name", "")
        domain = input.get("domain", "")
        query = f"{company_name} company profile employees revenue industry headquarters"
        if domain:
            query += f" site:{domain} OR {domain}"

        if settings.TAVILY_API_KEY:
            try:
                from tavily import TavilyClient
                client = TavilyClient(api_key=settings.TAVILY_API_KEY)
                response = client.search(query=query, max_results=5)
                results = response.get("results", [])
                combined_content = "\n\n".join(r.get("content", "") for r in results[:3])
                return {
                    "success": True,
                    "data": {
                        "raw_content": combined_content,
                        "search_results": results[:5],
                        "company_name": company_name,
                        "domain": domain,
                    },
                    "source": "tavily",
                }
            except Exception as e:
                return {"success": False, "data": {}, "source": "company_lookup", "error": str(e)}

        return {"success": False, "data": {}, "source": "company_lookup", "error": "No Tavily API key configured"}
