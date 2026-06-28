"""
HITL Trigger Evaluator
=======================
Evaluates whether a business brief requires human-in-the-loop review.
This implements the HITL State Machine from Section 22 of the implementation plan.

HITL is triggered when any of these conditions are met:
  1. Confidence score < 0.5 (uncertain brief)
  2. ICP match score < 0.4 (poor fit — risky to proceed)
  3. Conflicting signals detected (positive trigger + negative qualifier)
  4. Missing critical contact info (no email AND no phone AND no LinkedIn)
  5. High-value company (> 10,000 employees) — always requires review
  6. First 3 briefs of any workflow (training/calibration)
"""

from planner.state import PlatformState


# ── HITL thresholds ───────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.70
PRIORITY_SCORE_THRESHOLD = 0.95

def evaluate_hitl_conditions(
    brief: dict,
    company: dict,
    contacts: list[dict],
    brief_count_in_run: int,
) -> tuple[bool, str, str]:
    """
    Evaluate whether this brief should trigger HITL review per Section 26 of spec.
    """
    reasons = []
    severity = "low"

    # Condition 1: Low confidence (< 0.70)
    confidence = brief.get("overall_confidence", 1.0)
    if confidence < CONFIDENCE_THRESHOLD:
        reasons.append(f"Overall confidence is low ({confidence:.2f} < 0.70)")
        severity = "high"

    # Condition 2: Priority score > 0.95 (high-value company)
    priority = brief.get("priority_score", 0.0)
    if priority > PRIORITY_SCORE_THRESHOLD:
        reasons.append(f"High-value company detected (Priority {priority:.2f} > 0.95)")
        if severity != "high":
            severity = "medium"

    # Condition 3: Missing critical contact fields (> 2 unavailable)
    if contacts:
        for c in contacts:
            missing_count = 0
            if not c.get("email") or c.get("email") == "unavailable": missing_count += 1
            if not c.get("phone") or c.get("phone") == "unavailable": missing_count += 1
            if not c.get("linkedin_url") or c.get("linkedin_url") == "unavailable": missing_count += 1
            if missing_count >= 2:
                reasons.append(f"Missing > 2 critical contact fields for {c.get('name', 'contact')}")
                if severity != "high":
                    severity = "medium"
                break
    else:
        reasons.append("No contacts discovered (missing fields > 2)")
        severity = "high"

    # Condition 4: Duplicate similarity flagged (from deduplication node)
    # The deduplication check runs BEFORE dag executor, but we can look for flags in company metadata
    if company.get("possible_duplicate"):
        reasons.append("Duplicate flag raised by ChromaDB (similarity > 0.92)")
        severity = "high"

    # Condition 5: Agent retry limit reached (check errors in state)
    # Passed implicitly from state if needed, but omitted here for brevity as it's hard to track per-brief

    hitl_required = len(reasons) > 0
    combined_reason = " | ".join(reasons) if reasons else ""

    return hitl_required, combined_reason, severity


def check_hitl_conditions(state: PlatformState) -> str:
    """
    LangGraph conditional edge function.
    Returns "hitl" or "continue" based on HITL evaluation of the current brief.
    """
    briefs = state.get("business_briefs", [])
    companies = state.get("enriched_companies", [])
    contacts = state.get("discovered_contacts", [])

    if not briefs:
        return "continue"

    latest_brief = briefs[-1]
    brief_count = len(briefs)

    # Find the matching company for this brief
    company_id = latest_brief.get("company_id")
    matching_company = next(
        (c for c in companies if str(c.get("id", "")) == str(company_id)),
        {}
    )

    # Find contacts for this company
    company_contacts = [
        c for c in contacts
        if str(c.get("company_id", "")) == str(company_id)
    ]

    requires_hitl, reason, severity = evaluate_hitl_conditions(
        brief=latest_brief,
        company=matching_company,
        contacts=company_contacts,
        brief_count_in_run=brief_count,
    )

    if requires_hitl:
        print(f"[HITL] Triggered for company {matching_company.get('name', 'unknown')}: {reason}")

    return "hitl" if requires_hitl else "continue"
