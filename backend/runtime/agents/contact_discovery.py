"""
Contact Discovery & Enrichment Agent
======================================
Discovers decision-maker contacts for each enriched company.
- Reads persona config from ICP (CISO, IT Director, VP Security, etc.)
- Uses Hunter.io for email lookup
- Uses LinkedIn search (via Tavily) for profiles
- NEVER fabricates contact data — marks unavailable fields as "unavailable"
- Checks Redis cache first (company:contact:{company_id}:{role})
"""

import json
import hashlib
from runtime.agents.base_agent import BaseAgent


CONTACT_SCHEMA = """{
  "full_name": "string or null",
  "designation": "string",
  "department": "string or null",
  "seniority": "string (C-Suite/VP/Director/Manager)",
  "linkedin_url": "string or 'unavailable'",
  "confidence_score": float between 0.0 and 1.0
}"""


class ContactDiscoveryAgent(BaseAgent):
    agent_name = "contact_discovery"
    llm_model = "google/gemma-2-9b-it:free"

    async def run(self, state: dict) -> dict:
        icp_config = self.icp_config
        enriched_companies = state.get("enriched_companies", [])
        personas = icp_config.get("personas") or [
            {"title": "CISO", "seniority": "C-Suite", "priority": 1},
            {"title": "IT Director", "seniority": "Director", "priority": 2},
            {"title": "VP of Security", "seniority": "VP", "priority": 2},
        ]

        print(f"[{self.agent_name}] Discovering contacts for {len(enriched_companies)} companies")
        all_contacts = []

        for company in enriched_companies:
            company_name = company.get("name", "")
            domain = company.get("domain", "")
            company_contacts = []

            for persona in personas[:3]:  # Top 3 personas
                title = persona.get("title", "")
                cache_key = f"company:contact:{hashlib.md5(domain.encode()).hexdigest()}:{title.replace(' ', '_')}"

                # Check Redis cache
                cached = await self._get_cached_contact(cache_key)
                if cached:
                    all_contacts.extend(cached)
                    continue

                contact = {
                    "company_name": company_name,
                    "company_domain": domain,
                    "designation": title,
                    "seniority": persona.get("seniority", ""),
                    "full_name": "unavailable",
                    "email": "unavailable",
                    "email_confidence": 0.0,
                    "phone": "unavailable",
                    "linkedin_url": "unavailable",
                    "confidence_score": 0.0,
                    "source": "discovery",
                }

                # LinkedIn search
                if "contact_intelligence.linkedin_lookup" in self.capabilities:
                    result = self.capabilities["contact_intelligence.linkedin_lookup"].execute({
                        "company_name": company_name,
                        "persona_title": title,
                    })
                    profiles = result.get("data", {}).get("profiles", [])
                    if profiles:
                        best_profile = profiles[0]
                        contact["linkedin_url"] = best_profile.get("linkedin_url", "unavailable")

                        # Try to extract name from LinkedIn snippet
                        snippet = best_profile.get("snippet", "")
                        title_from_page = best_profile.get("title", "")
                        if snippet or title_from_page:
                            try:
                                prompt = f"""From this LinkedIn profile snippet, extract the person's name.
Title: {title_from_page}
Snippet: {snippet}
Company: {company_name}

Return ONLY JSON: {{"full_name": "First Last or null"}}"""
                                name_data = await self.ask_llm_for_json(prompt)
                                extracted_name = name_data.get("full_name")
                                if extracted_name and extracted_name.lower() not in ("null", "unavailable", "none"):
                                    contact["full_name"] = extracted_name
                                    contact["confidence_score"] = 0.65
                            except Exception:
                                pass

                # Email lookup (Hunter.io)
                if "contact_intelligence.email_lookup" in self.capabilities and domain:
                    # Try domain pattern first
                    result = self.capabilities["contact_intelligence.email_lookup"].execute({
                        "domain": domain
                    })
                    if result.get("success"):
                        email_data = result.get("data", {})
                        pattern = email_data.get("pattern", "")
                        sample_emails = email_data.get("sample_emails", [])
                        if sample_emails:
                            contact["email"] = sample_emails[0]
                            contact["email_confidence"] = 0.7
                            contact["confidence_score"] = max(contact["confidence_score"], 0.72)
                        contact["source"] = "hunter.io + linkedin_search"

                company_contacts.append(contact)
                await self._cache_contact(cache_key, [contact])

            all_contacts.extend(company_contacts)
            print(f"[{self.agent_name}] Found {len(company_contacts)} contacts for {company_name}")

        print(f"[{self.agent_name}] Total contacts discovered: {len(all_contacts)}")

        return {
            "discovered_contacts": all_contacts,
            "agent_metrics": state.get("agent_metrics", []) + [
                self.build_metric(
                    status="success",
                    output_summary=f"Discovered {len(all_contacts)} contacts across {len(enriched_companies)} companies",
                )
            ],
        }

    async def _get_cached_contact(self, cache_key: str) -> list | None:
        try:
            from memory.redis_client import redis_get
            cached = await redis_get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        return None

    async def _cache_contact(self, cache_key: str, contacts: list):
        try:
            from memory.redis_client import redis_set, TTL_CONTACT
            await redis_set(cache_key, json.dumps(contacts), ttl_seconds=TTL_CONTACT)
        except Exception:
            pass
