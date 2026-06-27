"""
Business Understanding AI Service
==================================
Takes a free-form business description and outputs a structured ICP configuration
using a Gemini LLM chain. This is Phase 2.1 of the implementation plan.

Input:  business_description (string)
Output: Structured ICP dict (matches ICPConfiguration model fields)
"""

import json
import re
import os
from pathlib import Path
from typing import Optional

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

from config import settings


# ── Load prompt template ──────────────────────────────────────────────────────
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def _get_llm():
    """Return the configured LLM client."""
    if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            groq_api_key=settings.GROQ_API_KEY,
        )
    elif settings.LLM_PROVIDER == "google" and settings.GOOGLE_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.2,
            google_api_key=settings.GOOGLE_API_KEY,
        )
    elif settings.OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.2,
            openai_api_key=settings.OPENAI_API_KEY,
        )
    else:
        raise RuntimeError(
            "No LLM configured. Set GOOGLE_API_KEY or OPENAI_API_KEY in .env"
        )


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

    llm = _get_llm()
    result = await llm.ainvoke([HumanMessage(content=filled)])

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
