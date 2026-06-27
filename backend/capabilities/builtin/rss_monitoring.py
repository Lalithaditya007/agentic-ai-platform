"""
RSS Monitoring Capability
==========================
Parses RSS feeds for trigger monitoring (Google News, company blogs, etc.)
"""

import feedparser
from typing import Any
from capabilities.base import CapabilityPlugin


class RSSMonitoringPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "search.rss_monitoring"

    @property
    def display_name(self) -> str:
        return "RSS Feed Monitor"

    @property
    def description(self) -> str:
        return "Parse RSS feeds for real-time trigger monitoring (Google News, industry blogs)."

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {"feed_url": str} OR {"query": str} for Google News RSS
        """
        feed_url = input.get("feed_url")
        query = input.get("query")
        max_results = input.get("max_results", 15)

        if not feed_url and query:
            feed_url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"

        if not feed_url:
            return {"success": False, "data": [], "source": "rss", "error": "No feed_url or query provided"}

        try:
            feed = feedparser.parse(feed_url)
            items = []
            for entry in feed.entries[:max_results]:
                items.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "summary": entry.get("summary", ""),
                    "published": entry.get("published", ""),
                    "source": feed.feed.get("title", "RSS Feed"),
                })
            return {"success": True, "data": items, "source": "rss"}
        except Exception as e:
            return {"success": False, "data": [], "source": "rss", "error": str(e)}
