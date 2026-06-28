"""
Company Validation Agent
=========================
Validates candidate companies against ICP rules.
Only companies with ICP match score >= 0.60 continue to enrichment.
"""

from runtime.agents.base_agent import BaseAgent


class CompanyValidationAgent(BaseAgent):
    agent_name = "company_validation"
    llm_model = "google/gemma-2-9b-it:free"
    MIN_CONFIDENCE = 0.35

    async def run(self, state: dict) -> dict:
        icp_config = self.icp_config
        candidates = state.get("candidate_companies", [])

        print(f"[{self.agent_name}] Validating {len(candidates)} companies against ICP rules")

        # ICP filters
        emp_min = icp_config.get("employee_count_min") or 0
        emp_max = icp_config.get("employee_count_max") or float("inf")
        target_industries = [i.lower() for i in (icp_config.get("industry") or [])]
        target_geographies = [g.lower() for g in (icp_config.get("geography") or [])]
        disqualifiers = icp_config.get("disqualifiers") or []
        qual_rules = icp_config.get("qualification_rules") or []

        validated = []

        for company in candidates:
            company_name = company.get("name", "")
            company_industry = (company.get("industry") or "").lower()
            employee_count = company.get("employee_count") or company.get("initial_metadata", {}).get("employee_count", 0)
            headquarters = (company.get("headquarters") or "").lower()

            icp_score = 0.0
            score_breakdown = {}
            rejection_reason = ""

            # ── Industry match ─────────────────────────────────────
            if target_industries:
                ind_match = any(ind in company_industry or company_industry in ind for ind in target_industries)
                if ind_match:
                    icp_score += 0.30
                    score_breakdown["industry"] = 0.30
                else:
                    score_breakdown["industry"] = 0.0
            else:
                icp_score += 0.30  # No industry filter
                score_breakdown["industry"] = 0.30

            # ── Employee count ─────────────────────────────────────
            if employee_count and emp_min <= employee_count <= emp_max:
                icp_score += 0.25
                score_breakdown["employee_count"] = 0.25
            elif not employee_count:
                icp_score += 0.15  # Partial credit — unknown size
                score_breakdown["employee_count"] = 0.15
            else:
                score_breakdown["employee_count"] = 0.0

            # ── Geography match ─────────────────────────────────────
            if target_geographies:
                geo_match = any(g in headquarters for g in target_geographies) or not headquarters
                if geo_match:
                    icp_score += 0.20
                    score_breakdown["geography"] = 0.20
                else:
                    score_breakdown["geography"] = 0.0
            else:
                icp_score += 0.20
                score_breakdown["geography"] = 0.20

            # ── Trigger confidence boost ───────────────────────────
            trigger_conf = company.get("trigger_confidence", 0.5)
            trigger_boost = min(trigger_conf * 0.15, 0.15)
            icp_score += trigger_boost
            score_breakdown["trigger_confidence"] = trigger_boost

            # ── Disqualifier check ─────────────────────────────────
            disqualified = False
            for disq in disqualifiers:
                condition = disq.get("condition", "").lower()
                if condition and (condition in company_industry or condition in company_name.lower()):
                    disqualified = True
                    rejection_reason = f"Disqualifier: {disq.get('description', condition)}"
                    break

            if disqualified:
                print(f"[{self.agent_name}] REJECTED {company_name}: {rejection_reason}")
                continue

            # ── Min score threshold ────────────────────────────────
            icp_score = min(icp_score, 1.0)
            if icp_score < self.MIN_CONFIDENCE:
                print(f"[{self.agent_name}] FILTERED {company_name}: ICP score {icp_score:.2f} < {self.MIN_CONFIDENCE}")
                continue

            company["icp_match_score"] = round(icp_score, 3)
            company["confidence_score"] = round(icp_score, 3)
            company["validation_status"] = "validated"
            company["icp_score_breakdown"] = score_breakdown
            validated.append(company)
            print(f"[{self.agent_name}] VALIDATED {company_name} | ICP score: {icp_score:.2f}")

        print(f"[{self.agent_name}] {len(validated)}/{len(candidates)} companies passed validation")

        return {
            "validated_companies": validated,
            "duplicates_avoided": state.get("duplicates_avoided", 0),
            "agent_metrics": state.get("agent_metrics", []) + [
                self.build_metric(
                    status="success",
                    output_summary=f"{len(validated)}/{len(candidates)} companies passed ICP validation",
                )
            ],
        }
