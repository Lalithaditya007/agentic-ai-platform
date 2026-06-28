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

    result = await invoke_with_retry([HumanMessage(content=filled)], temperature=0.2)

    raw_content = result.content if hasattr(result, "content") else str(result)
    cleaned = _clean_json_response(raw_content)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM returned non-JSON response. Parse error: {e}\n"
            f"Raw response (first 500 chars): {cleaned[:500]}"
        )

    return parsed


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
