"""
Next Best Action Agent
=======================
Analyzes enriched company + contacts and generates:
  - Priority Score (urgency of opportunity)
  - Recommended Contact (best decision maker to reach)
  - Recommended Channel (email / LinkedIn / phone / referral)
  - Recommended Timing (within 48h / this week / next month)
  - Personalized Talking Points (3-5 bullet points)
  - Business Opportunity Summary
  - Risk Factors
  - Confidence Score

Uses historical decisions from ChromaDB to improve recommendations.
"""

from runtime.agents.base_agent import BaseAgent


class NextBestActionAgent(BaseAgent):
    agent_name = "next_best_action"

    async def run(self, state: dict) -> dict:
        icp_config = self.icp_config
        enriched_companies = state.get("enriched_companies", [])
        all_contacts = state.get("discovered_contacts", [])

        print(f"[{self.agent_name}] Generating NBA for {len(enriched_companies)} companies")

        nba_recommendations = []

        for company in enriched_companies:
            company_name = company.get("name", "")

            # Find contacts for this company
            company_contacts = [
                c for c in all_contacts
                if c.get("company_name") == company_name or c.get("company_domain") == company.get("domain")
            ]

            # Find similar historical decisions from ChromaDB
            historical_context = ""
            try:
                from memory.chromadb_client import chroma_query, COLLECTION_HISTORICAL_DECISIONS
                hist_results = chroma_query(
                    collection_name=COLLECTION_HISTORICAL_DECISIONS,
                    query_text=f"{company_name} {company.get('industry', '')}",
                    n_results=2,
                )
                if hist_results:
                    historical_context = "Previous similar decisions:\n" + "\n".join(
                        r["document"][:300] for r in hist_results
                    )
            except Exception:
                pass

            # Build company context for LLM
            context = f"""Company: {company_name}
Industry: {company.get('industry', 'Unknown')}
Employees: {company.get('employee_count', 'Unknown')}
Headquarters: {company.get('headquarters', 'Unknown')}
Revenue: {company.get('revenue_estimate', 'Unknown')}
Recent Funding: {company.get('funding_total', 'None')}
ICP Match Score: {company.get('icp_match_score', 0.0):.0%}
Trigger: {company.get('trigger_source', 'unknown')} — {company.get('trigger_detail', '')}
Growth Signals: {company.get('growth_signals', {})}
Recent News Headlines: {', '.join(n.get('title', '') for n in (company.get('recent_news') or [])[:3])}
Tech Stack: {', '.join(company.get('tech_stack') or [])}
Available Contacts: {len(company_contacts)} discovered

ICP Personas: {', '.join(p.get('title', '') for p in (icp_config.get('personas') or [])[:3])}
{historical_context}"""

            prompt = f"""You are a B2B sales intelligence expert. Generate a Next Best Action recommendation.

{context}

Return ONLY valid JSON:
{{
  "priority_score": float 0.0-1.0 (urgency of opportunity),
  "recommended_contact_index": integer (0-based index into contacts list, or -1 if none),
  "recommended_channel": "email" or "linkedin" or "phone" or "referral",
  "recommended_timing": "string e.g. Within 48 hours — trigger is fresh",
  "talking_points": ["string", "string", "string"],
  "business_opportunity_summary": "string (1 paragraph)",
  "risk_factors": ["string"],
  "confidence_score": float 0.0-1.0,
  "confidence_breakdown": {{"data_quality": float, "icp_match": float, "trigger_strength": float}}
}}"""

            try:
                nba_data = await self.ask_llm_for_json(prompt)

                # Resolve recommended contact
                contact_idx = nba_data.get("recommended_contact_index", -1)
                recommended_contact = None
                if 0 <= contact_idx < len(company_contacts):
                    recommended_contact = company_contacts[contact_idx]

                nba = {
                    "company_name": company_name,
                    "company_domain": company.get("domain", ""),
                    "priority_score": nba_data.get("priority_score", 0.5),
                    "recommended_contact": recommended_contact,
                    "recommended_channel": nba_data.get("recommended_channel", "email"),
                    "recommended_timing": nba_data.get("recommended_timing", "This week"),
                    "talking_points": nba_data.get("talking_points", []),
                    "business_opportunity_summary": nba_data.get("business_opportunity_summary", ""),
                    "risk_factors": nba_data.get("risk_factors", []),
                    "confidence_score": nba_data.get("confidence_score", 0.5),
                    "confidence_breakdown": nba_data.get("confidence_breakdown", {}),
                }
                nba_recommendations.append(nba)
                print(f"[{self.agent_name}] NBA for {company_name}: priority={nba['priority_score']:.2f}")

            except Exception as e:
                print(f"[{self.agent_name}] Failed NBA for {company_name}: {e}")
                nba_recommendations.append({
                    "company_name": company_name,
                    "company_domain": company.get("domain", ""),
                    "priority_score": company.get("icp_match_score", 0.5),
                    "recommended_contact": company_contacts[0] if company_contacts else None,
                    "recommended_channel": "email",
                    "recommended_timing": "This week",
                    "talking_points": [],
                    "business_opportunity_summary": f"High-priority {company.get('industry', '')} company matching your ICP.",
                    "risk_factors": [],
                    "confidence_score": 0.5,
                })

        print(f"[{self.agent_name}] Generated {len(nba_recommendations)} NBA recommendations")

        return {
            "nba_recommendations": nba_recommendations,
            "agent_metrics": state.get("agent_metrics", []) + [
                self.build_metric(
                    status="success",
                    output_summary=f"Generated {len(nba_recommendations)} Next Best Action recommendations",
                )
            ],
        }
