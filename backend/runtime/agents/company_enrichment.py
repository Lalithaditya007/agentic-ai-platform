"""
Company Enrichment Agent
=========================
Deeply enriches validated companies with:
  - Employee count, revenue, headquarters
  - Funding information & recent rounds
  - Tech stack, hiring trends, growth signals
  - Recent news (last 90 days)
  - Social presence

Checks Redis cache first. Stores to PostgreSQL + ChromaDB.
"""

import json
from datetime import datetime, timezone
from runtime.agents.base_agent import BaseAgent


ENRICHMENT_SCHEMA = """{
  "employee_count": integer or null,
  "revenue_estimate": "string e.g. $10M-$50M or null",
  "headquarters": "City, Country or null",
  "funding_total": "string e.g. $120M or null",
  "recent_funding": [{"amount": "string", "round": "string", "date": "string", "investors": ["string"]}],
  "tech_stack": ["string"],
  "hiring_trends": {"active_roles": integer, "trending_skills": ["string"], "hiring_growth": "string"},
  "growth_signals": {"funding_recent": boolean, "hiring_growth": boolean, "product_launch": boolean, "expansion": boolean},
  "recent_news": [{"title": "string", "summary": "string", "date": "string", "url": "string"}],
  "company_description": "string",
  "social_presence": {"linkedin_url": "string or null", "twitter_url": "string or null"}
}"""


class CompanyEnrichmentAgent(BaseAgent):
    agent_name = "company_enrichment"

    async def run(self, state: dict) -> dict:
        validated = state.get("validated_companies", [])
        print(f"[{self.agent_name}] Enriching {len(validated)} companies")

        enriched = []

        for company in validated:
            company_name = company.get("name", "")
            domain = company.get("domain", "")

            print(f"[{self.agent_name}] Enriching: {company_name}")

            # Check Redis cache first
            cache_hit = await self._check_cache(domain)
            if cache_hit:
                print(f"[{self.agent_name}] Cache HIT for {company_name}")
                company.update(cache_hit)
                company["enriched_from_cache"] = True
                enriched.append(company)
                continue

            # Collect raw content from capabilities
            raw_content_parts = []

            # General company info
            if "business_intelligence.company_lookup" in self.capabilities:
                result = self.capabilities["business_intelligence.company_lookup"].execute({
                    "company_name": company_name, "domain": domain
                })
                if result.get("success"):
                    raw_content_parts.append(result["data"].get("raw_content", ""))

            # Funding info
            if "business_intelligence.funding_lookup" in self.capabilities:
                result = self.capabilities["business_intelligence.funding_lookup"].execute({
                    "company_name": company_name
                })
                if result.get("success"):
                    raw_content_parts.append(result["data"].get("raw_content", ""))

            # Hiring info
            if "business_intelligence.hiring_analysis" in self.capabilities:
                result = self.capabilities["business_intelligence.hiring_analysis"].execute({
                    "company_name": company_name
                })
                if result.get("success"):
                    raw_content_parts.append(result["data"].get("raw_content", ""))

            # Recent news
            if "search.news_search" in self.capabilities:
                result = self.capabilities["search.news_search"].execute({
                    "query": f"{company_name} news 2024 2025", "max_results": 5
                })
                if result.get("success"):
                    articles = result.get("data", [])
                    raw_content_parts.append(
                        "\n".join(f"{a.get('title', '')} - {a.get('content', '')[:200]}" for a in articles)
                    )

            combined_raw = "\n\n".join(p for p in raw_content_parts if p)[:4000]

            # LLM extraction
            enriched_data = {}
            if combined_raw:
                try:
                    prompt = f"""Extract structured company intelligence from this content.
Company: {company_name} | Domain: {domain}

Schema to extract (return ONLY valid JSON):
{ENRICHMENT_SCHEMA}

Content:
{combined_raw}

RULES:
- Never fabricate data. Use null if information is not available.
- Return ONLY valid JSON, no markdown."""

                    enriched_data = await self.ask_llm_for_json(prompt)
                except Exception as e:
                    print(f"[{self.agent_name}] LLM extraction failed for {company_name}: {e}")
                    enriched_data = {}

            # Merge enrichment into company profile
            company.update(enriched_data)
            company["enriched_from_cache"] = False
            company["validation_status"] = "enriched"
            enriched.append(company)

            # Cache in Redis
            await self._cache_company(domain, enriched_data)

            # Store in ChromaDB
            await self._store_in_chromadb(company_name, domain, enriched_data)

        print(f"[{self.agent_name}] Enriched {len(enriched)} companies")

        return {
            "enriched_companies": enriched,
            "memory_hits": state.get("memory_hits", 0) + sum(1 for c in enriched if c.get("enriched_from_cache")),
            "agent_metrics": state.get("agent_metrics", []) + [
                self.build_metric(
                    status="success",
                    output_summary=f"Enriched {len(enriched)} companies",
                )
            ],
        }

    async def _check_cache(self, domain: str) -> dict | None:
        if not domain:
            return None
        try:
            import hashlib
            from memory.redis_client import redis_get
            domain_hash = hashlib.md5(domain.lower().encode()).hexdigest()
            cached = await redis_get(f"company:enriched:{domain_hash}")
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        return None

    async def _cache_company(self, domain: str, enriched_data: dict):
        if not domain:
            return
        try:
            import hashlib
            from memory.redis_client import redis_set, TTL_COMPANY_DOMAIN
            domain_hash = hashlib.md5(domain.lower().encode()).hexdigest()
            await redis_set(f"company:enriched:{domain_hash}", json.dumps(enriched_data), TTL_COMPANY_DOMAIN)
        except Exception:
            pass

    async def _store_in_chromadb(self, company_name: str, domain: str, enriched_data: dict):
        try:
            from memory.chromadb_client import chroma_upsert, COLLECTION_COMPANY_KNOWLEDGE
            import hashlib
            doc_id = hashlib.md5(domain.lower().encode()).hexdigest() if domain else company_name[:32]
            document = f"{company_name} {domain} {enriched_data.get('company_description', '')} {enriched_data.get('headquarters', '')} {' '.join(enriched_data.get('tech_stack', []))}"
            chroma_upsert(
                collection_name=COLLECTION_COMPANY_KNOWLEDGE,
                documents=[document],
                ids=[doc_id],
                metadatas=[{"company_name": company_name, "domain": domain}],
            )
        except Exception:
            pass
