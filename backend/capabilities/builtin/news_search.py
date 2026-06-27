"""
News Search Capability — NewsAPI + Google News RSS
====================================================
Fetches news articles for trigger monitoring and enrichment.
Uses NewsAPI.org as primary, Google News RSS as fallback.
"""

import feedparser
from typing import Any
from capabilities.base import CapabilityPlugin
from config import settings


class NewsSearchPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "search.news_search"

    @property
    def display_name(self) -> str:
        return "News Search (NewsAPI + RSS)"

    @property
    def description(self) -> str:
        return "Search for news articles about companies, triggers, and business events."

    def health_check(self) -> bool:
        return True  # Always available — RSS is free

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {"query": str, "max_results": int (default 10)}
        Returns:
            {"success": bool, "data": list[dict], "source": str}
        """
        query = input.get("query", "")
        max_results = input.get("max_results", 10)

        articles = []

        # Try NewsAPI first
        if settings.NEWS_API_KEY:
            try:
                from newsapi import NewsApiClient
                client = NewsApiClient(api_key=settings.NEWS_API_KEY)
                resp = client.get_everything(q=query, language="en", sort_by="publishedAt", page_size=max_results)
                for art in resp.get("articles", []):
                    articles.append({
                        "title": art.get("title", ""),
                        "url": art.get("url", ""),
                        "content": art.get("description", ""),
                        "published_at": art.get("publishedAt", ""),
                        "source": art.get("source", {}).get("name", ""),
                    })
                if articles:
                    return {"success": True, "data": articles[:max_results], "source": "newsapi"}
            except Exception:
                pass

        # Fallback: Google News RSS
        try:
            rss_url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:max_results]:
                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "content": entry.get("summary", ""),
                    "published_at": entry.get("published", ""),
                    "source": "Google News",
                })
            return {"success": True, "data": articles, "source": "google_news_rss"}
        except Exception as e:
            return {"success": False, "data": [], "source": "news_search", "error": str(e)}
