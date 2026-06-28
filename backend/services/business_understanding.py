"""
Business Understanding AI Service
==================================
Takes a free-form business description and outputs a structured ICP configuration
using an LLM chain (Groq → Google Gemini → OpenAI fallback chain).

Input:  business_description (string)
Output: Structured ICP dict (matches ICPConfiguration model fields)
"""

import json
import re
import os
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage

from config import settings
from runtime.agents.base_agent import invoke_with_retry


# ── Load prompt template ──────────────────────────────────────────────────────
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def _clean_json_response(raw: str) -> str:
    """Strip markdown code fences if the LLM wraps response in them."""
    # Remove ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    return cleaned.strip()


def _heuristic_business_understanding(description: str) -> dict:
    """
    Free-tier fallback when no LLM provider is available.
    It uses lightweight keyword/rule extraction so the platform remains usable.
    """
    text = description.lower()

    industry_map = {
        "bank": "Banking",
        "financial": "Financial Services",
        "cyber": "Cybersecurity",
        "health": "Healthcare",
        "hospital": "Healthcare",
        "manufactur": "Manufacturing",
        "staff": "Staffing",
        "energy": "Energy",
        "saas": "SaaS",
        "software": "Software",
    }
    industry = []
    for key, value in industry_map.items():
        if key in text and value not in industry:
            industry.append(value)
    if not industry:
        industry = ["B2B Services"]

    geography = []
    geo_map = {
        "north america": "North America",
        "united states": "US",
        "usa": "US",
        "us ": "US",
        "uk": "UK",
        "europe": "EU",
        "eu": "EU",
        "apac": "APAC",
        "india": "India",
    }
    for key, value in geo_map.items():
        if key in text and value not in geography:
            geography.append(value)
    if not geography:
        geography = ["US"]

    emp_min = None
    emp_max = None
    gte_match = re.search(r"(?:more than|over|at least|minimum of)\s+(\d+)\s+employees", text)
    range_match = re.search(r"(\d+)\s*(?:to|-)\s*(\d+)\s+employees", text)
    if range_match:
        emp_min = int(range_match.group(1))
        emp_max = int(range_match.group(2))
    elif gte_match:
        emp_min = int(gte_match.group(1))

    personas = []
    if "cyber" in text or "security" in text:
        personas = [
            {"title": "Chief Information Security Officer", "seniority": "C-Suite", "department": "Security", "priority": 5},
            {"title": "Security Manager", "seniority": "Manager", "department": "Security", "priority": 4},
            {"title": "IT Director", "seniority": "Director", "department": "IT", "priority": 3},
        ]
    elif "health" in text or "hospital" in text:
        personas = [
            {"title": "Chief Operating Officer", "seniority": "C-Suite", "department": "Operations", "priority": 5},
            {"title": "Procurement Director", "seniority": "Director", "department": "Procurement", "priority": 4},
            {"title": "IT Director", "seniority": "Director", "department": "IT", "priority": 3},
        ]
    else:
        personas = [
            {"title": "VP Operations", "seniority": "VP", "department": "Operations", "priority": 5},
            {"title": "Director of IT", "seniority": "Director", "department": "IT", "priority": 4},
            {"title": "Procurement Manager", "seniority": "Manager", "department": "Procurement", "priority": 3},
        ]

    triggers = []
    if "expand" in text or "expansion" in text:
        triggers.append({"type": "expansion", "description": "Recent expansion activity", "weight": 0.8, "enabled": True})
    if "hiring" in text or "team" in text:
        triggers.append({"type": "hiring_surge", "description": "Growth in team hiring", "weight": 0.7, "enabled": True})
    if not triggers:
        triggers = [{"type": "web_discovery", "description": "General ICP-targeted market discovery", "weight": 0.6, "enabled": True}]

    qualification_rules = []
    if emp_min:
        qualification_rules.append({
            "field": "employee_count",
            "operator": "gte",
            "value": emp_min,
            "description": f"Employee count should be at least {emp_min}",
        })
    qualification_rules.append({
        "field": "industry",
        "operator": "in",
        "value": industry[0],
        "description": f"Target industry is {industry[0]}",
    })

    return {
        "industry": industry,
        "target_market_description": description[:240],
        "product_or_service": "Derived from business description",
        "value_proposition": "Heuristically extracted from business description",
        "icp": {
            "company_size": {"label": "Enterprise" if (emp_min or 0) >= 500 else "Mid-market"},
            "revenue_range": None,
            "geography": geography,
            "employee_count_min": emp_min,
            "employee_count_max": emp_max,
        },
        "personas": personas,
        "triggers": triggers,
        "qualification_rules": qualification_rules,
        "disqualifiers": [],
        "constraints": [],
        "confidence_indicator": 0.62,
        "confidence_notes": "Generated from heuristic fallback because LLM understanding was unavailable.",
    }


async def understand_business(description: str) -> dict:
    """
    Call the LLM to parse a business description into a structured ICP config.

    Args:
        description: Free-form text describing the business, product, and target market.

    Returns:
        dict: Structured ICP configuration ready to be saved to DB.
    """
    prompt_template_text = _load_prompt("business_understanding.txt")
    
    # Replace manually to avoid f-string parsing of JSON braces
    filled = prompt_template_text.replace("{business_description}", description)

    try:
        result = await invoke_with_retry([HumanMessage(content=filled)], temperature=0.2)
        raw_content = result.content if hasattr(result, "content") else str(result)
        cleaned = _clean_json_response(raw_content)
        return json.loads(cleaned)
    except Exception as e:
        print(f"[BUSINESS_UNDERSTANDING] Falling back to heuristic parser: {e}")
        return _heuristic_business_understanding(description)


def extract_icp_fields(parsed: dict) -> dict:
    """
    Extract only the fields needed for ICPConfiguration DB model from
    the full parsed LLM response.

    Args:
        parsed: Full structured output from understand_business()

    Returns:
        dict: Fields matching ICPConfiguration columns
    """
    icp_raw = parsed.get("icp", {})

    return {
        "industry": parsed.get("industry", []),
        "company_size": icp_raw.get("company_size"),
        "revenue_range": icp_raw.get("revenue_range"),
        "geography": icp_raw.get("geography", []),
        "employee_count_min": icp_raw.get("employee_count_min"),
        "employee_count_max": icp_raw.get("employee_count_max"),
        "personas": parsed.get("personas", []),
        "triggers": parsed.get("triggers", []),
        "qualification_rules": parsed.get("qualification_rules", []),
        "disqualifiers": parsed.get("disqualifiers", []),
        "constraints": parsed.get("constraints", []),
        "confidence_indicator": parsed.get("confidence_indicator", 0.5),
        # Extra context fields stored but not in model columns — included in full response
        "_target_market_description": parsed.get("target_market_description", ""),
        "_product_or_service": parsed.get("product_or_service", ""),
        "_value_proposition": parsed.get("value_proposition", ""),
        "_confidence_notes": parsed.get("confidence_notes", ""),
    }


async def generate_icp_from_description(description: str) -> tuple[dict, dict]:
    """
    Full pipeline: description → LLM → parsed → ICP fields.

    Returns:
        (full_parsed_response, icp_db_fields)
    """
    full_parsed = await understand_business(description)
    icp_fields = extract_icp_fields(full_parsed)
    return full_parsed, icp_fields
