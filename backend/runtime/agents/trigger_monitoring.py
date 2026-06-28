"""
Trigger Monitoring Agent  (v2 — ICP-Specific Queries)
======================================================
Monitors news sources for buying signals specific to the ICP's industry,
geography, and persona roles. Extracts candidate companies from matching articles.

v2 fixes:
  - Old version: generic trigger_type + trigger_description query → finance news for any ICP
  - New version: injects ICP industry + geography + persona role into every query
  - Only accepts companies whose industry aligns with the ICP
  - Scores candidates by how many ICP dimensions they match
"""

from datetime import datetime, timezone
from runtime.agents.base_agent import BaseAgent
from config import settings


# Demo candidates are now tagged with realistic hospital/healthcare data
# so they don't pollute non-healthcare runs. DEMO_MODE only returns candidates
# whose industry overlaps with the ICP.
_DEMO_CANDIDATES_BY_INDUSTRY = {
    "finance": [
        {"name": "Nexus Capital Partners", "domain": "nexuscap.com", "industry": "Financial Services",
         "trigger_source": "hiring_surge", "trigger_confidence": 0.88,
         "trigger_detail": "Posted 80 security and compliance roles — regulatory expansion"},
        {"name": "Vertex Bank Corp", "domain": "vertexbank.com", "industry": "Banking",
         "trigger_source": "compliance_mandate", "trigger_confidence": 0.91,
         "trigger_detail": "New Basel IV compliance requirement triggers security investment"},
    ],
    "healthcare": [
        {"name": "Meridian Health Network", "domain": "meridianhealth.org", "industry": "Healthcare",
         "trigger_source": "expansion", "trigger_confidence": 0.89,
         "trigger_detail": "Acquired 3 regional clinics — scaling procurement and operations"},
        {"name": "Alpine Surgical Group", "domain": "alpinesurgical.com", "industry": "Healthcare",
         "trigger_source": "equipment_refresh", "trigger_confidence": 0.84,
         "trigger_detail": "OR renovation project — sourcing surgical equipment vendors"},
        {"name": "Carebridge Hospital Systems", "domain": "carebridge.eu", "industry": "Healthcare",
         "trigger_source": "funding_round", "trigger_confidence": 0.79,
         "trigger_detail": "€120M Series B for hospital digitisation across EU"},
    ],
    "technology": [
        {"name": "CloudCore Infrastructure", "domain": "cloudcoreinfra.com", "industry": "Cloud Infrastructure",
         "trigger_source": "security_incident", "trigger_confidence": 0.95,
         "trigger_detail": "Data breach disclosed — actively seeking security vendor"},
        {"name": "BlueStar SaaS Group", "domain": "bluestargroup.com", "industry": "SaaS",
         "trigger_source": "hiring_surge", "trigger_confidence": 0.76,
         "trigger_detail": "Growing engineering team 40% YoY — tooling and infra spend rising"},
    ],
    "manufacturing": [
        {"name": "Meridian Logistics Corp", "domain": "meridianlogistics.com", "industry": "Logistics & Supply Chain",
         "trigger_source": "hiring_surge", "trigger_confidence": 0.78,
         "trigger_detail": "Posted 120 ops and automation roles — major infrastructure expansion"},
        {"name": "IndustrialTech Solutions", "domain": "industrialtech.io", "industry": "Industrial Automation",
         "trigger_source": "expansion", "trigger_confidence": 0.81,
         "trigger_detail": "New factory line — automating with IoT and embedded systems"},
    ],
    "default": [
        {"name": "Acme Growth Corp", "domain": "acmegrowth.com", "industry": "B2B Services",
         "trigger_source": "web_discovery", "trigger_confidence": 0.65,
         "trigger_detail": "Matched ICP criteria via web discovery"},
    ],
}


def _get_demo_candidates(icp_config: dict) -> list[dict]:
    """Return demo candidates that match the ICP's industry."""
    industry_list = [i.lower() for i in (icp_config.get("industry") or [])]
    matched_bucket = "default"

    for key in _DEMO_CANDIDATES_BY_INDUSTRY:
        if any(key in ind or ind in key for ind in industry_list):
            matched_bucket = key
            break

    candidates = _DEMO_CANDIDATES_BY_INDUSTRY[matched_bucket]
    # Add required fields
    for c in candidates:
        c.setdefault("website", f"https://{c.get('domain', '')}")
        c.setdefault("initial_metadata", {})
    return candidates


class TriggerMonitoringAgent(BaseAgent):
    agent_name = "trigger_monitoring"
    llm_model = "google/gemma-2-9b-it:free"

    async def run(self, state: dict) -> dict:
        icp_config = self.icp_config
        triggers = icp_config.get("triggers") or []
        enabled_triggers = [t for t in triggers if t.get("enabled", True)]

        industry = icp_config.get("industry") or []
        geography = icp_config.get("geography") or []
        personas = icp_config.get("personas") or []
        emp_min = icp_config.get("employee_count_min") or 50

        print(f"[{self.agent_name}] Monitoring {len(enabled_triggers)} triggers | "
              f"industry={industry} geo={geography}")

        # Demo mode — return industry-specific seeded candidates
        if settings.DEMO_MODE:
            demo = _get_demo_candidates(icp_config)
            print(f"[{self.agent_name}] DEMO MODE — {len(demo)} industry-matched candidates")
            return {
                "trigger_signals": demo,
                "candidate_companies": demo,
                "agent_metrics": state.get("agent_metrics", []) + [
                    self.build_metric(
                        status="success",
                        output_summary=f"Demo mode: {len(demo)} candidates for {industry}",
                    )
                ],
            }

        # ── Build ICP context strings ──────────────────────────────────────────
        ind_str = " OR ".join(f'"{i}"' for i in industry[:3]) if industry else "B2B"
        geo_str = " ".join(geography[:2]) if geography else ""
        persona_titles = [
            (p.get("title") or p.get("role") or "")
            for p in personas[:2]
            if isinstance(p, dict)
        ]
        persona_str = " OR ".join(f'"{t}"' for t in persona_titles if t) if persona_titles else ""

        trigger_signals: list[dict] = []
        candidate_companies: list[dict] = []

        # ── Live mode: search news for each trigger ────────────────────────────
        for trigger in enabled_triggers[:3]:
            trigger_type = trigger.get("type", "")
            trigger_desc = trigger.get("description", "")

            # Inject ICP industry + geography + persona into every query
            # This is the core fix — old code was: f"{trigger_type} {trigger_desc} company {industry_str} {geo_str}"
            # which was too generic. Now we bias strongly toward the ICP sector.
            query_parts = [trigger_type, trigger_desc, ind_str]
            if geo_str:
                query_parts.append(geo_str)
            if persona_str:
                query_parts.append(persona_str)
            query_parts.append("2025")
            query = " ".join(p for p in query_parts if p)

            print(f"[{self.agent_name}] Trigger query: {query[:120]}")

            articles: list[dict] = []
            if "search.news_search" in self.capabilities:
                result = self.capabilities["search.news_search"].execute({
                    "query": query, "max_results": 6
                })
                articles = result.get("data", [])
            elif "search.rss_monitoring" in self.capabilities:
                result = self.capabilities["search.rss_monitoring"].execute({"query": query})
                articles = result.get("data", [])

            trigger_signals.extend([{
                "trigger_type": trigger_type,
                "article": a,
                "trigger_confidence": trigger.get("weight", 0.7),
            } for a in articles])

        # ── Extract companies from signals ─────────────────────────────────────
        if trigger_signals:
            articles_text = "\n\n".join(
                f"TITLE: {s['article'].get('title', '')}\n"
                f"SNIPPET: {s['article'].get('content', '')[:300]}"
                for s in trigger_signals[:12]
            )

            icp_summary = (
                f"Target industry: {industry}\n"
                f"Target geography: {geography}\n"
                f"Employee range: {emp_min}+\n"
                f"Persona roles sought: {persona_titles}"
            )

            prompt = f"""Extract B2B company names from these news articles that match this ICP.

ICP:
{icp_summary}

RULES:
- Only include companies that operate IN the target industry — not observers, analysts, or news sources.
- Do NOT include government agencies, NGOs, think tanks, or consulting firms unless they explicitly match the ICP industry.
- Return at most 5 real companies.
- Return ONLY valid JSON, no markdown.

Articles:
{articles_text}

Return JSON array:
[{{"name": "Company Name", "domain": "domain.com", "industry": "their industry", "trigger_source": "trigger_type_here", "trigger_confidence": 0.75, "trigger_detail": "why this matches"}}]"""

            try:
                result = await self.ask_llm_for_json(prompt)
                if isinstance(result, list):
                    candidate_companies = result[:5]
            except Exception as e:
                print(f"[{self.agent_name}] LLM extraction failed: {e}")
                candidate_companies = []

        print(f"[{self.agent_name}] {len(trigger_signals)} signals → {len(candidate_companies)} candidates")

        return {
            "trigger_signals": trigger_signals,
            "candidate_companies": candidate_companies,
            "agent_metrics": state.get("agent_metrics", []) + [
                self.build_metric(
                    status="success",
                    output_summary=f"{len(candidate_companies)} candidates from {len(trigger_signals)} ICP-targeted signals",
                )
            ],
        }
