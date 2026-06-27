"""
Company Discovery Agent
========================
Finds and discovers target companies matching the ICP from trigger signals
or direct web searches. Produces structured company profiles.
"""

from runtime.agents.base_agent import BaseAgent


class CompanyDiscoveryAgent(BaseAgent):
    agent_name = "company_discovery"

    async def run(self, state: dict) -> dict:
        icp_config = self.icp_config
        trigger_candidates = state.get("candidate_companies", [])
        industry = icp_config.get("industry", [])
        geography = icp_config.get("geography", [])
        emp_min = icp_config.get("employee_count_min") or 100
        emp_max = icp_config.get("employee_count_max") or 10000

        print(f"[{self.agent_name}] Discovering from {len(trigger_candidates)} trigger candidates")

        discovered = []

        # If we already have trigger candidates, enrich their metadata
        if trigger_candidates:
            for candidate in trigger_candidates[:10]:
                company_name = candidate.get("name", "")
                domain = candidate.get("domain", "")

                if not company_name:
                    continue

                # Quick lookup to confirm company exists
                basic_info = {
                    "name": company_name,
                    "domain": domain,
                    "website": candidate.get("website", f"https://{domain}" if domain else ""),
                    "industry": candidate.get("industry", "Unknown"),
                    "trigger_source": candidate.get("trigger_source", "web_search"),
                    "trigger_confidence": candidate.get("trigger_confidence", 0.7),
                    "trigger_detail": candidate.get("trigger_detail", ""),
                    "initial_metadata": {},
                }
                discovered.append(basic_info)
        else:
            # No candidates from triggers — do direct industry search
            ind_str = " OR ".join(f'"{i}"' for i in industry[:3]) if industry else "technology"
            geo_str = " ".join(geography[:2]) if geography else "US"
            query = f"B2B companies {ind_str} {geo_str} {emp_min}-{emp_max} employees 2024 2025"

            if "search.web_search" in self.capabilities:
                result = self.capabilities["search.web_search"].execute({
                    "query": query, "max_results": 10
                })
                raw_results = result.get("data", [])

                if raw_results:
                    # Extract company names from search results
                    content = "\n".join(r.get("title", "") + " " + r.get("content", "")[:200] for r in raw_results[:5])
                    prompt = f"""Extract B2B company names from these search results.
Return ONLY JSON array:
[{{"name": "Company Name", "domain": "domain.com", "industry": "industry", "trigger_source": "web_discovery", "trigger_confidence": 0.6}}]

Content: {content[:2000]}
Return at most 5 companies. ONLY JSON."""

                    try:
                        companies_data = await self.ask_llm_for_json(prompt)
                        if isinstance(companies_data, list):
                            discovered = companies_data[:5]
                    except Exception as e:
                        print(f"[{self.agent_name}] LLM extraction failed: {e}")

        # Deduplicate by domain
        seen_domains = set()
        unique_discovered = []
        import uuid
        for c in discovered:
            d = c.get("domain", "").lower().strip()
            if d and d not in seen_domains:
                seen_domains.add(d)
                c["company_id"] = str(uuid.uuid4())
                unique_discovered.append(c)

        print(f"[{self.agent_name}] Discovered {len(unique_discovered)} unique companies")

        return {
            "candidate_companies": unique_discovered,
            "agent_metrics": state.get("agent_metrics", []) + [
                self.build_metric(
                    status="success",
                    output_summary=f"Discovered {len(unique_discovered)} unique candidate companies",
                )
            ],
        }
