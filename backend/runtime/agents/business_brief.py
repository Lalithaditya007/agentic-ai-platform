"""
Business Brief Generator
=========================
Generates the complete business brief for each enriched company.
The brief is the final output that sales/BD teams receive.

Brief structure:
  - Company Summary
  - Trigger Summary
  - Qualification Summary (ICP match breakdown)
  - Company Insights
  - Decision Makers table
  - Next Best Actions
  - Confidence Score with breakdown
  - Sources

Stores brief in PostgreSQL business_briefs table.
Stores vector embedding in ChromaDB for future similarity.
"""

import uuid
from datetime import datetime, timezone
from runtime.agents.base_agent import BaseAgent


class BusinessBriefAgent(BaseAgent):
    agent_name = "business_brief"

    async def run(self, state: dict) -> dict:
        enriched_companies = state.get("enriched_companies", [])
        all_contacts = state.get("discovered_contacts", [])
        nba_recommendations = state.get("nba_recommendations", [])
        workflow_run_id = state.get("workflow_run_id", "")

        print(f"[{self.agent_name}] Generating briefs for {len(enriched_companies)} companies")

        business_briefs = []

        for company in enriched_companies:
            company_name = company.get("name", "")
            domain = company.get("domain", "")

            # Find contacts and NBA for this company
            company_contacts = [
                c for c in all_contacts
                if c.get("company_name") == company_name or c.get("company_domain") == domain
            ]
            nba = next(
                (n for n in nba_recommendations if n.get("company_name") == company_name),
                {}
            )

            # Build ICP qualification breakdown
            score_breakdown = company.get("icp_score_breakdown", {})
            icp_match = company.get("icp_match_score", 0.0)

            # Generate brief via LLM
            context = f"""Company: {company_name}
Domain: {domain}
Industry: {company.get('industry', 'Unknown')}
Headquarters: {company.get('headquarters', 'Unknown')}
Employees: {company.get('employee_count', 'Unknown')}
Revenue: {company.get('revenue_estimate', 'Unknown')}
Funding: {company.get('funding_total', 'None raised')}
Description: {company.get('company_description', '')[:400]}
ICP Match: {icp_match:.0%}
Trigger: {company.get('trigger_source', '')} — {company.get('trigger_detail', '')}
Recent News: {', '.join(n.get('title', '') for n in (company.get('recent_news') or [])[:3])}
Growth Signals: {company.get('growth_signals', {})}
Tech Stack: {', '.join((company.get('tech_stack') or [])[:5])}
Priority Score: {nba.get('priority_score', 0.5):.0%}
Recommended Channel: {nba.get('recommended_channel', 'email')}
Talking Points: {nba.get('talking_points', [])}"""

            brief_data = {}
            try:
                prompt = f"""You are a senior B2B sales intelligence analyst. Generate a comprehensive business brief.

{context}

Return ONLY valid JSON:
{{
  "company_summary": "string (2-3 sentences about the company, its business, and why it's a strong ICP match)",
  "trigger_summary": "string (explain what triggered this opportunity and why timing is important now)",
  "qualification_summary": "string (explain how this company matches the ICP with specific evidence)",
  "company_insights": {{
    "key_strengths": ["string"],
    "technology_footprint": "string",
    "growth_trajectory": "string",
    "competitive_landscape": "string"
  }},
  "talking_points": ["string", "string", "string", "string", "string"],
  "risk_factors": ["string"],
  "recommended_channel": "email or linkedin or phone",
  "recommended_timing": "string",
  "overall_confidence": float 0.0-1.0
}}"""

                brief_data = await self.ask_llm_for_json(prompt)
            except Exception as e:
                print(f"[{self.agent_name}] LLM brief generation failed for {company_name}: {e}")
                brief_data = {
                    "company_summary": f"{company_name} is a {company.get('industry', '')} company with {company.get('employee_count', 'unknown')} employees.",
                    "trigger_summary": f"Triggered by: {company.get('trigger_source', 'web discovery')}",
                    "qualification_summary": f"ICP match score: {icp_match:.0%}",
                    "company_insights": {},
                    "talking_points": nba.get("talking_points", []),
                    "risk_factors": nba.get("risk_factors", []),
                    "recommended_channel": nba.get("recommended_channel", "email"),
                    "recommended_timing": nba.get("recommended_timing", "This week"),
                    "overall_confidence": icp_match,
                }

            brief_id = str(uuid.uuid4())
            brief = {
                "id": brief_id,
                "workflow_run_id": workflow_run_id,
                "company_name": company_name,
                "company_domain": domain,
                "company_id": company.get("company_id", str(uuid.uuid4())),
                "company_summary": brief_data.get("company_summary", ""),
                "trigger_summary": brief_data.get("trigger_summary", ""),
                "qualification_summary": brief_data.get("qualification_summary", ""),
                "company_insights": brief_data.get("company_insights", {}),
                "decision_makers": [
                    {
                        "name": c.get("full_name", "unavailable"),
                        "title": c.get("designation", ""),
                        "email": c.get("email", "unavailable"),
                        "phone": c.get("phone", "unavailable"),
                        "linkedin_url": c.get("linkedin_url", "unavailable"),
                        "confidence": c.get("confidence_score", 0.0),
                    }
                    for c in company_contacts[:5]
                ],
                "next_best_actions": nba.get("talking_points", brief_data.get("talking_points", [])),
                "talking_points": brief_data.get("talking_points", []),
                "risk_factors": brief_data.get("risk_factors", nba.get("risk_factors", [])),
                "priority_score": nba.get("priority_score", icp_match),
                "recommended_channel": brief_data.get("recommended_channel", "email"),
                "recommended_timing": brief_data.get("recommended_timing", "This week"),
                "overall_confidence": brief_data.get("overall_confidence", icp_match),
                "icp_match_score": icp_match,
                "icp_score_breakdown": score_breakdown,
                "sources": {
                    "company_data": "Tavily web search",
                    "contacts": "Hunter.io + LinkedIn search",
                    "news": "Google News RSS + NewsAPI",
                },
                "hitl_status": "pending_review",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            business_briefs.append(brief)

            # Persist to PostgreSQL
            await self._save_to_db(brief, workflow_run_id)

            # Store in ChromaDB for future similarity
            await self._store_in_chromadb(brief)

            print(f"[{self.agent_name}] Brief generated for {company_name} | confidence={brief['overall_confidence']:.2f}")

        print(f"[{self.agent_name}] Generated {len(business_briefs)} business briefs")

        return {
            "business_briefs": business_briefs,
            "agent_metrics": state.get("agent_metrics", []) + [
                self.build_metric(
                    status="success",
                    output_summary=f"Generated {len(business_briefs)} business briefs",
                )
            ],
        }

    async def _save_to_db(self, brief: dict, workflow_run_id: str):
        """Persist brief to PostgreSQL business_briefs table."""
        try:
            from database.models import AsyncSessionLocal, BusinessBrief
            async with AsyncSessionLocal() as db:
                db_brief = BusinessBrief(
                    workflow_run_id=uuid.UUID(workflow_run_id) if workflow_run_id else None,
                    company_id=uuid.UUID(brief["company_id"]),
                    company_name=brief.get("company_name"),
                    company_domain=brief.get("company_domain"),
                    company_summary=brief.get("company_summary"),
                    trigger_summary=brief.get("trigger_summary"),
                    qualification_summary=brief.get("qualification_summary"),
                    company_insights=brief.get("company_insights"),
                    decision_makers=brief.get("decision_makers"),
                    next_best_actions=brief.get("next_best_actions"),
                    talking_points=brief.get("talking_points"),
                    risk_factors=brief.get("risk_factors"),
                    priority_score=brief.get("priority_score"),
                    recommended_channel=brief.get("recommended_channel"),
                    recommended_timing=brief.get("recommended_timing"),
                    overall_confidence=brief.get("overall_confidence"),
                    sources=brief.get("sources"),
                    hitl_status="pending_review",
                )
                db.add(db_brief)
                await db.commit()
        except Exception as e:
            print(f"[{self.agent_name}] DB save failed for {brief.get('company_name')}: {e}")

    async def _store_in_chromadb(self, brief: dict):
        """Store brief embedding in ChromaDB for similarity matching."""
        try:
            from memory.chromadb_client import chroma_upsert, COLLECTION_BUSINESS_BRIEFS
            doc_id = brief["id"]
            document = f"{brief['company_name']} {brief.get('company_summary', '')} {brief.get('trigger_summary', '')} {brief.get('qualification_summary', '')}"
            chroma_upsert(
                collection_name=COLLECTION_BUSINESS_BRIEFS,
                documents=[document],
                ids=[doc_id],
                metadatas=[{
                    "company_name": brief["company_name"],
                    "priority_score": str(brief.get("priority_score", 0.5)),
                }],
            )
        except Exception:
            pass
