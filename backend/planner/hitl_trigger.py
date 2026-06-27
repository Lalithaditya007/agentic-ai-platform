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
CONFIDENCE_THRESHOLD = 0.5
ICP_MATCH_THRESHOLD = 0.4
HIGH_VALUE_EMPLOYEE_THRESHOLD = 10_000
CALIBRATION_BRIEF_COUNT = 3   # First N briefs always go to HITL


def evaluate_hitl_conditions(
    brief: dict,
    company: dict,
    contacts: list[dict],
    brief_count_in_run: int,
) -> tuple[bool, str, str]:
    """
    Evaluate whether this brief should trigger HITL review.

    Args:
        brief: The generated business brief dict
        company: The enriched company dict
        contacts: List of discovered contacts for this company
        brief_count_in_run: How many briefs have been generated in this workflow run

    Returns:
        (requires_hitl: bool, reason: str, severity: str)
        severity: "high" | "medium" | "low"
    """
    reasons = []
    severity = "low"

    # Condition 1: Low confidence
    confidence = brief.get("overall_confidence", 1.0)
    if confidence < CONFIDENCE_THRESHOLD:
        reasons.append(f"Overall confidence is low ({confidence:.0%})")
        severity = "high"

    # Condition 2: Poor ICP match
    icp_match = company.get("icp_match_score", 1.0)
    if icp_match < ICP_MATCH_THRESHOLD:
        reasons.append(f"ICP match score is below threshold ({icp_match:.0%})")
        severity = "high"

    # Condition 3: Conflicting signals
    growth_signals = company.get("growth_signals", {})
    recent_news = company.get("recent_news", [])
    has_positive_signal = bool(growth_signals.get("hiring_growth") or growth_signals.get("funding_recent"))
    has_negative_signal = any(
        any(word in str(news).lower() for word in ["layoff", "lawsuit", "bankrupt", "scandal", "breach"])
        for news in recent_news
    )
    if has_positive_signal and has_negative_signal:
        reasons.append("Conflicting signals: positive growth + negative news events detected")
        if severity != "high":
            severity = "medium"

    # Condition 4: Missing critical contact info
    if contacts:
        all_missing_contact = all(
            not c.get("email") and not c.get("phone") and not c.get("linkedin_url")
            for c in contacts
        )
        if all_missing_contact:
            reasons.append("No reachable contact information found for any persona")
            if severity != "high":
                severity = "medium"

    # Condition 5: High-value company (always review)
    employee_count = company.get("employee_count", 0) or 0
    if employee_count >= HIGH_VALUE_EMPLOYEE_THRESHOLD:
        reasons.append(f"High-value enterprise account ({employee_count:,} employees) — mandatory review")
        if severity == "low":
            severity = "medium"

    # Condition 6: Calibration (first N briefs)
    if brief_count_in_run <= CALIBRATION_BRIEF_COUNT:
        reasons.append(
            f"Calibration review: brief #{brief_count_in_run} "
            f"(first {CALIBRATION_BRIEF_COUNT} always reviewed)"
        )
        if severity == "low":
            severity = "low"  # Low severity for calibration

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
