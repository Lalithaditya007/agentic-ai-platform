"""
Company Discovery Agent  (v2 — ICP-Grounded Search)
=====================================================
Finds REAL target companies by running multiple targeted Tavily search passes
that are grounded in the ICP: industry, geography, employee size, and personas.

Previous version problems fixed:
  - Was reusing trigger candidates verbatim (often from unrelated news articles)
  - Generic fallback query returned finance/regulatory bodies for any industry
  - LLM extraction had no ICP context to filter against

New approach:
  1. Run 3 targeted web searches using ICP industry + geography
  2. Run 1 news search for companies actively hiring / expanding in the sector
  3. LLM extracts companies from ALL results, validated against the full ICP JSON
  4. Deduplication by domain
"""

import uuid
from urllib.parse import urlparse
from runtime.agents.base_agent import BaseAgent
from config import get_llm_model


# ICP-aware query templates. {industry}, {geo}, {persona_role}, {size} are
# filled from the actual ICP config at runtime.
DISCOVERY_QUERY_TEMPLATES = [
    # Direct company list search — most likely to return actual company names
    "list of {industry} companies {geo} with {size} employees 2024 2025",
    # B2B vendor/provider angle
    "{industry} companies {geo} B2B solutions services provider vendor",
    # Hiring / growth signal — companies actively expanding
    "{industry} company {geo} hiring expanding growing 2025 site:linkedin.com OR site:crunchbase.com OR site:glassdoor.com",
]

NEWS_QUERY_TEMPLATE = (
    "{industry} company {geo} funding OR expansion OR hiring OR contract OR partnership 2025"
)


def _build_queries(icp_config: dict) -> tuple[list[str], str]:
    """Build targeted search queries from the ICP configuration."""
    industry = icp_config.get("industry") or []
    geography = icp_config.get("geography") or []
    personas = icp_config.get("personas") or []
    emp_min = icp_config.get("employee_count_min") or 50
    emp_max = icp_config.get("employee_count_max") or 5000

    # Collapse lists into readable strings
    ind_str = " OR ".join(f'"{i}"' for i in industry[:3]) if industry else "B2B technology"
    geo_str = " ".join(geography[:2]) if geography else "United States"

    # Use primary persona role if available
    persona_role = ""
    if personas:
        first_persona = personas[0]
        if isinstance(first_persona, dict):
            persona_role = first_persona.get("title", "") or first_persona.get("role", "")

    # Size label
    if emp_max <= 200:
        size_label = f"{emp_min}-{emp_max} employees small business"
    elif emp_max <= 1000:
        size_label = f"{emp_min}-{emp_max} employees mid-market"
    else:
        size_label = f"over {emp_min} employees enterprise"

    ctx = {
        "industry": ind_str,
        "geo": geo_str,
        "persona_role": persona_role,
        "size": size_label,
    }

    web_queries = [t.format(**ctx) for t in DISCOVERY_QUERY_TEMPLATES]
    news_query = NEWS_QUERY_TEMPLATE.format(**ctx)
    return web_queries, news_query


class CompanyDiscoveryAgent(BaseAgent):
    agent_name = "company_discovery"
    llm_model = get_llm_model()

    def _build_structured_fallback_candidates(
        self,
        structured_candidates: list[dict],
        trigger_candidates: list[dict],
    ) -> list[dict]:
        """
        Use structured search sources directly when LLM extraction is unavailable.
        Validation still runs after this, so this fallback should prefer recall.
        """
        merged = []
        seen: set[str] = set()

        for company in [*structured_candidates, *trigger_candidates]:
            if not isinstance(company, dict):
                continue

            name = (company.get("name") or "").strip()
            if not name:
                continue

            domain = (company.get("domain") or "").lower().strip()
            dedup_key = domain or name.lower()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            merged.append({
                "name": name,
                "domain": domain,
                "industry": company.get("industry"),
                "headquarters": company.get("headquarters"),
                "employee_count": company.get("employee_count"),
                "trigger_source": company.get("trigger_source") or company.get("source") or "structured_discovery",
                "trigger_confidence": company.get("trigger_confidence", 0.6),
                "trigger_detail": company.get("trigger_detail") or "Matched via structured company discovery source",
                "website": company.get("website"),
                "company_id": str(uuid.uuid4()),
            })

        return merged[:20]

    def _build_web_fallback_candidates(
        self,
        web_hits: list[dict],
        news_hits: list[dict],
        industry: list[str],
    ) -> list[dict]:
        """Recover company candidates directly from search result titles and domains."""
        target_industry = industry[0] if industry else ""
        candidates: list[dict] = []
        seen: set[str] = set()

        def add_candidate(name: str, domain: str, detail: str, confidence: float):
            clean_name = (name or "").strip()
            clean_domain = (domain or "").lower().strip()
            if not clean_name:
                return
            dedup_key = clean_domain or clean_name.lower()
            if dedup_key in seen:
                return
            seen.add(dedup_key)
            candidates.append({
                "name": clean_name,
                "domain": clean_domain,
                "industry": target_industry,
                "headquarters": None,
                "employee_count": None,
                "trigger_source": "web_discovery",
                "trigger_confidence": confidence,
                "trigger_detail": detail,
                "company_id": str(uuid.uuid4()),
            })

        def parse_name_from_title(title: str, fallback_domain: str) -> str:
            if title:
                primary = title.split(" | ")[0].split(" - ")[0].split(":")[0].strip()
                words = primary.split()
                if 1 <= len(words) <= 6:
                    return primary
            if fallback_domain:
                root = fallback_domain.split(".")[0].replace("-", " ").replace("_", " ")
                return " ".join(part.capitalize() for part in root.split())
            return ""

        for hit in web_hits:
            url = hit.get("url", "")
            host = (urlparse(url).hostname or "").lower()
            domain = host[4:] if host.startswith("www.") else host
            name = parse_name_from_title(hit.get("title", ""), domain)
            add_candidate(name, domain, "Recovered from ICP-targeted web search result", 0.5)

        for hit in news_hits:
            title = hit.get("title", "")
            if not title:
                continue
            name = parse_name_from_title(title, "")
            add_candidate(name, "", "Recovered from ICP-targeted news result", 0.35)

        return candidates[:20]

    async def run(self, state: dict) -> dict:
        icp_config = self.icp_config
        trigger_candidates = state.get("candidate_companies", [])
        industry = icp_config.get("industry") or []
        geography = icp_config.get("geography") or []

        print(f"[{self.agent_name}] Starting ICP-grounded discovery | "
              f"industry={industry} geo={geography}")

        # ── Step 1: Build ICP-grounded search queries ─────────────────────────
        web_queries, news_query = _build_queries(icp_config)
        print(f"[{self.agent_name}] Discovery queries: {web_queries}")

        # ── Step 2: Multi-pass Tavily web search ──────────────────────────────
        raw_content_parts: list[str] = []
        web_hits_for_fallback: list[dict] = []
        news_hits_for_fallback: list[dict] = []

        if "search.web_search" in self.capabilities:
            for i, query in enumerate(web_queries):
                try:
                    result = self.capabilities["search.web_search"].execute({
                        "query": query,
                        "max_results": 8,
                    })
                    hits = result.get("data", [])
                    if hits:
                        web_hits_for_fallback.extend(hits)
                        chunk = "\n".join(
                            f"[WEB-{i}] TITLE: {h.get('title','')}\nURL: {h.get('url','')}\nSNIPPET: {h.get('content','')[:300]}"
                            for h in hits
                        )
                        raw_content_parts.append(chunk)
                        print(f"[{self.agent_name}] Web pass {i+1}: {len(hits)} results")
                except Exception as e:
                    print(f"[{self.agent_name}] Web search pass {i+1} failed: {e}")
        else:
            print(f"[{self.agent_name}] WARN: web_search capability not available")

        # ── Step 3: News search for actively-growing companies ─────────────────
        if "search.news_search" in self.capabilities:
            try:
                result = self.capabilities["search.news_search"].execute({
                    "query": news_query,
                    "max_results": 8,
                })
                articles = result.get("data", [])
                if articles:
                    news_hits_for_fallback.extend(articles)
                    chunk = "\n".join(
                        f"[NEWS] TITLE: {a.get('title','')}\nSOURCE: {a.get('source','')}\nSNIPPET: {a.get('content','')[:300]}"
                        for a in articles
                    )
                    raw_content_parts.append(chunk)
                    print(f"[{self.agent_name}] News search: {len(articles)} articles")
            except Exception as e:
                print(f"[{self.agent_name}] News search failed: {e}")

        # ── Step 3b: Apollo.io company database search ────────────────────────
        structured_candidates: list[dict] = []

        if "company_data.apollo_search" in self.capabilities:
            try:
                result = self.capabilities["company_data.apollo_search"].execute({
                    "industry": industry,
                    "location": geography,
                    "employee_min": icp_config.get("employee_count_min") or 10,
                    "employee_max": icp_config.get("employee_count_max") or 100000,
                    "limit": 15,
                })
                apollo_companies = result.get("data", [])
                if apollo_companies:
                    structured_candidates.extend(apollo_companies)
                    print(f"[{self.agent_name}] Apollo: {len(apollo_companies)} companies")
            except Exception as e:
                print(f"[{self.agent_name}] Apollo search failed: {e}")

        # ── Step 3c: OpenCorporates registry search ────────────────────────────
        if "company_data.opencorporates_search" in self.capabilities:
            try:
                ind_query = " ".join(industry[:2]) if industry else "company"
                result = self.capabilities["company_data.opencorporates_search"].execute({
                    "query": ind_query,
                    "geography": geography,
                    "limit": 15,
                })
                oc_companies = result.get("data", [])
                if oc_companies:
                    structured_candidates.extend(oc_companies)
                    print(f"[{self.agent_name}] OpenCorporates: {len(oc_companies)} companies")
            except Exception as e:
                print(f"[{self.agent_name}] OpenCorporates search failed: {e}")

        # ── Step 3d: Companies House UK (if ICP targets UK) ───────────────────
        uk_geo = {"uk", "united kingdom", "gb", "england", "britain"}
        targets_uk = any(g.lower() in uk_geo for g in geography)
        # Also run Companies House if geography is Europe (UK is in Europe)
        targets_eu = any(g.lower() in {"europe", "eu", "emea"} for g in geography)

        if (targets_uk or targets_eu) and "company_data.companies_house_search" in self.capabilities:
            try:
                ch_query = " ".join(industry[:2]) if industry else "services"
                result = self.capabilities["company_data.companies_house_search"].execute({
                    "query": ch_query,
                    "limit": 15,
                })
                ch_companies = result.get("data", [])
                if ch_companies:
                    structured_candidates.extend(ch_companies)
                    print(f"[{self.agent_name}] Companies House: {len(ch_companies)} UK companies")
            except Exception as e:
                print(f"[{self.agent_name}] Companies House search failed: {e}")

        # ── Step 3e: SEC EDGAR (if ICP targets US) ────────────────────────────
        us_geo = {"us", "united states", "usa", "america", "north america"}
        targets_us = not geography or any(g.lower() in us_geo for g in geography)

        if targets_us and "company_data.sec_edgar_search" in self.capabilities:
            try:
                edgar_query = " ".join(industry[:2]) if industry else "company"
                result = self.capabilities["company_data.sec_edgar_search"].execute({
                    "query": edgar_query,
                    "industry": industry,
                    "limit": 15,
                })
                edgar_companies = result.get("data", [])
                if edgar_companies:
                    structured_candidates.extend(edgar_companies)
                    print(f"[{self.agent_name}] SEC EDGAR: {len(edgar_companies)} US companies")
            except Exception as e:
                print(f"[{self.agent_name}] SEC EDGAR search failed: {e}")

        # ── Step 3f: Wikidata SPARQL — always runs (global, no key) ──────────
        if "company_data.wikidata_search" in self.capabilities:
            try:
                result = self.capabilities["company_data.wikidata_search"].execute({
                    "industry": industry,
                    "geography": geography,
                    "employee_min": icp_config.get("employee_count_min") or 10,
                    "limit": 20,
                })
                wikidata_companies = result.get("data", [])
                if wikidata_companies:
                    structured_candidates.extend(wikidata_companies)
                    print(f"[{self.agent_name}] Wikidata: {len(wikidata_companies)} global companies")
                else:
                    print(f"[{self.agent_name}] Wikidata: 0 results — {result.get('error','')}")
            except Exception as e:
                print(f"[{self.agent_name}] Wikidata search failed: {e}")

        # Convert structured DB results into the raw_content_parts format so the
        # LLM can see them alongside web/news results for unified filtering
        if structured_candidates:
            db_chunk = "\n".join(
                f"[DB] COMPANY: {c.get('name','')} | INDUSTRY: {c.get('industry','')} | "
                f"LOCATION: {c.get('headquarters','')} | EMPLOYEES: {c.get('employee_count','?')} | "
                f"SOURCE: {c.get('source','')}"
                for c in structured_candidates
            )
            raw_content_parts.append(db_chunk)
            print(f"[{self.agent_name}] Total structured DB candidates: {len(structured_candidates)}")


        # ── Step 4: Also pass along any trigger candidates ────────────────────
        if trigger_candidates:
            trigger_chunk = "\n".join(
                f"[TRIGGER] COMPANY: {c.get('name','')} | DOMAIN: {c.get('domain','')} | "
                f"INDUSTRY: {c.get('industry','')} | SIGNAL: {c.get('trigger_detail','')}"
                for c in trigger_candidates[:8]
            )
            raw_content_parts.append(trigger_chunk)
            print(f"[{self.agent_name}] Including {len(trigger_candidates)} trigger candidates")

        if not raw_content_parts:
            print(f"[{self.agent_name}] ERROR: No search results at all — no capabilities or API failures")
            return {
                "candidate_companies": [],
                "agent_metrics": state.get("agent_metrics", []) + [
                    self.build_metric(status="failure", output_summary="No search results — check capabilities")
                ],
            }

        combined = "\n\n".join(raw_content_parts)[:8000]  # Increased from 5000 for more sources


        # ── Step 5: ICP-grounded LLM extraction ───────────────────────────────
        # Pass the FULL ICP so LLM can filter intelligently, not just by keyword
        icp_summary = (
            f"Target Industry: {industry}\n"
            f"Geography: {geography}\n"
            f"Employee range: {icp_config.get('employee_count_min',0)}-{icp_config.get('employee_count_max',99999)}\n"
            f"Qualification rules: {[r.get('description','') for r in (icp_config.get('qualification_rules') or [])[:3]]}\n"
            f"Disqualifiers: {[d.get('description','') for d in (icp_config.get('disqualifiers') or [])[:3]]}"
        )

        prompt = f"""You are a B2B sales intelligence analyst. Extract REAL companies from search results that genuinely match this ICP.

ICP (Ideal Customer Profile):
{icp_summary}

STRICT RULES:
1. Only return companies that ACTUALLY operate in the target industry — not regulators, NGOs, government bodies, or companies from completely different industries.
2. Do NOT include companies just because they appear in news articles as observers or sources. They must BE a company that would BUY from this business.
3. Return maximum 20 companies. Prefer companies with more complete information (domain, location, employees known).
4. Use null for any field you cannot confirm from the text.
5. Return ONLY valid JSON, no markdown.

Search results to analyze:
{combined}

Return JSON array:
[
  {{
    "name": "Exact Company Name",
    "domain": "domain.com",
    "industry": "their actual industry",
    "headquarters": "City, Country",
    "employee_count": integer or null,
    "trigger_source": "web_discovery",
    "trigger_confidence": 0.65,
    "trigger_detail": "Why this company matches the ICP"
  }}
]"""

        discovered = []
        try:
            result = await self.ask_llm_for_json(prompt)
            if isinstance(result, list):
                discovered = result
                print(f"[{self.agent_name}] LLM extracted {len(discovered)} ICP-matched companies")
            else:
                print(f"[{self.agent_name}] LLM returned non-list: {type(result)}")
        except Exception as e:
            print(f"[{self.agent_name}] LLM extraction failed: {e}")
            discovered = self._build_structured_fallback_candidates(structured_candidates, trigger_candidates)
            if not discovered:
                discovered = self._build_web_fallback_candidates(
                    web_hits=web_hits_for_fallback,
                    news_hits=news_hits_for_fallback,
                    industry=industry,
                )
            print(
                f"[{self.agent_name}] Fallback recovered "
                f"{len(discovered)} candidate companies"
            )

        # ── Step 6: Deduplicate by domain ─────────────────────────────────────
        seen_domains: set[str] = set()
        unique: list[dict] = []
        for c in discovered:
            if not isinstance(c, dict):
                continue
            domain = (c.get("domain") or "").lower().strip()
            name = (c.get("name") or "").strip()
            if not name:
                continue
            dedup_key = domain if domain else name.lower()
            if dedup_key in seen_domains:
                continue
            seen_domains.add(dedup_key)
            c["company_id"] = str(uuid.uuid4())
            unique.append(c)

        print(f"[{self.agent_name}] Final: {len(unique)} unique ICP-matched companies")

        return {
            "candidate_companies": unique,
            "agent_metrics": state.get("agent_metrics", []) + [
                self.build_metric(
                    status="success" if unique else "warning",
                    output_summary=f"ICP-grounded discovery: {len(unique)} unique companies from {len(raw_content_parts)} search passes",
                )
            ],
        }
