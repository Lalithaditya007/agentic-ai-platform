"""
Trigger Monitoring Agent
=========================
Monitors news sources for business trigger signals (funding, hiring, product launches).
Extracts candidate companies from articles matching ICP trigger config.

Demo mode: Returns pre-seeded candidates when DEMO_MODE=true.
"""

from datetime import datetime, timezone
from runtime.agents.base_agent import BaseAgent
from config import settings


DEMO_CANDIDATES = [
    {
        "name": "Nexus Financial Group",
        "domain": "nexusfinancial.com",
        "website": "https://nexusfinancial.com",
        "industry": "Financial Services",
        "trigger_source": "funding_round",
        "trigger_confidence": 0.91,
        "trigger_detail": "Series C $45M raised — rapid expansion phase",
    },
    {
        "name": "Vertex Healthcare Systems",
        "domain": "vertexhealthcare.io",
        "website": "https://vertexhealthcare.io",
        "industry": "Healthcare Technology",
        "trigger_source": "compliance_mandate",
        "trigger_confidence": 0.87,
        "trigger_detail": "New HIPAA compliance audit requirement triggers security investment",
    },
    {
        "name": "CloudCore Infrastructure",
        "domain": "cloudcoreinfra.com",
        "website": "https://cloudcoreinfra.com",
        "industry": "Cloud Infrastructure",
        "trigger_source": "security_incident",
        "trigger_confidence": 0.95,
        "trigger_detail": "Data breach disclosed — actively seeking security vendor",
    },
    {
        "name": "Meridian Logistics Corp",
        "domain": "meridianlogistics.com",
        "website": "https://meridianlogistics.com",
        "industry": "Logistics & Supply Chain",
        "trigger_source": "hiring_surge",
        "trigger_confidence": 0.78,
        "trigger_detail": "Posted 120 security and IT roles — major infrastructure expansion",
    },
    {
        "name": "BlueStar Retail Group",
        "domain": "bluestarretail.com",
        "website": "https://bluestarretail.com",
        "industry": "Retail",
        "trigger_source": "executive_change",
        "trigger_confidence": 0.72,
        "trigger_detail": "New CISO hired from Microsoft — digital transformation initiative",
    },
]


class TriggerMonitoringAgent(BaseAgent):
    agent_name = "trigger_monitoring"

    async def run(self, state: dict) -> dict:
        icp_config = self.icp_config
        triggers = icp_config.get("triggers", [])
        enabled_triggers = [t for t in triggers if t.get("enabled", True)]

        print(f"[{self.agent_name}] Monitoring {len(enabled_triggers)} trigger types")

        # Demo mode — return seeded candidates
        if settings.DEMO_MODE:
            print(f"[{self.agent_name}] DEMO MODE — returning {len(DEMO_CANDIDATES)} seeded candidates")
            return {
                "trigger_signals": DEMO_CANDIDATES,
                "candidate_companies": DEMO_CANDIDATES,
                "agent_metrics": state.get("agent_metrics", []) + [
                    self.build_metric(
                        status="success",
                        output_summary=f"Demo mode: {len(DEMO_CANDIDATES)} pre-seeded candidates",
                    )
                ],
            }

        # Live mode — search news for each trigger
        trigger_signals = []
        candidate_companies = []
        geography = icp_config.get("geography", [])
        industry = icp_config.get("industry", [])

        for trigger in enabled_triggers[:3]:  # Limit to 3 triggers to save API quota
            trigger_type = trigger.get("type", "")
            trigger_desc = trigger.get("description", "")

            # Build search query from ICP context
            industry_str = " OR ".join(industry[:3]) if industry else ""
            geo_str = " ".join(geography[:2]) if geography else ""
            query = f"{trigger_type} {trigger_desc} company {industry_str} {geo_str} 2024 2025"

            # Search news
            if "search.news_search" in self.capabilities:
                result = self.capabilities["search.news_search"].execute({
                    "query": query, "max_results": 5
                })
                articles = result.get("data", [])
            else:
                # Fallback RSS
                if "search.rss_monitoring" in self.capabilities:
                    result = self.capabilities["search.rss_monitoring"].execute({"query": query})
                    articles = result.get("data", [])
                else:
                    articles = []

            trigger_signals.extend([{
                "trigger_type": trigger_type,
                "article": a,
                "trigger_confidence": trigger.get("weight", 0.7),
            } for a in articles])

        # Use LLM to extract company candidates from articles
        if trigger_signals:
            try:
                articles_text = "\n\n".join(
                    f"Title: {s['article'].get('title', '')}\nContent: {s['article'].get('content', '')[:300]}"
                    for s in trigger_signals[:10]
                )
                prompt = f"""Extract B2B company names and domains from these news articles.
Return ONLY valid JSON array:
[{{"name": "Company Name", "domain": "domain.com", "trigger_source": "trigger_type", "trigger_confidence": 0.8}}]

Articles:
{articles_text}

Industries to focus on: {', '.join(industry[:5]) if industry else 'any'}
Return at most 5 companies. Return ONLY JSON, no markdown."""

                companies_data = await self.ask_llm_for_json(prompt)
                if isinstance(companies_data, list):
                    candidate_companies = companies_data[:5]
            except Exception as e:
                print(f"[{self.agent_name}] LLM extraction failed: {e}")
                candidate_companies = []

        print(f"[{self.agent_name}] Found {len(trigger_signals)} signals, {len(candidate_companies)} candidates")

        return {
            "trigger_signals": trigger_signals,
            "candidate_companies": candidate_companies,
            "agent_metrics": state.get("agent_metrics", []) + [
                self.build_metric(
                    status="success",
                    output_summary=f"{len(candidate_companies)} candidates from {len(trigger_signals)} signals",
                )
            ],
        }
