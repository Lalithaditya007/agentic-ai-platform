"""
Planner Agent Node
===================
The Planner is the first node in the LangGraph pipeline.
It reads the ICP config and uses an LLM to build an execution strategy
that tells all subsequent nodes what to do, in what order, and with what models.

Responsibilities:
1. Read ICP config from state
2. Consult memory for any prior context on this project
3. Build execution strategy (which agents, parallel vs sequential)
4. Select LLM per task (cost optimization)
5. Determine upfront HITL intervention points
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage

from planner.state import PlatformState
from config import settings


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def _get_llm():
    """Get LLM for planning — always uses the most capable available model."""
    if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            groq_api_key=settings.GROQ_API_KEY,
        )
    elif settings.LLM_PROVIDER == "google" and settings.GOOGLE_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.1,
            google_api_key=settings.GOOGLE_API_KEY,
        )
    elif settings.OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
    else:
        return None


def _clean_json(raw: str) -> str:
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    return cleaned.strip()


def _build_default_strategy(icp_config: dict) -> dict:
    """
    Fallback strategy when LLM is unavailable.
    Runs all agents sequentially with sensible defaults.
    """
    triggers_enabled = any(
        t.get("enabled", False)
        for t in icp_config.get("triggers", [])
    )

    phases = []
    if triggers_enabled:
        phases.append({
            "phase": 1,
            "phase_name": "Signal Detection",
            "agents": ["trigger_monitoring"],
            "execution_mode": "sequential",
            "llm_model": "gemini-1.5-flash",
            "priority": 5,
            "timeout_seconds": 60,
            "retry_on_failure": True,
        })

    phases += [
        {
            "phase": 2,
            "phase_name": "Company Discovery",
            "agents": ["company_discovery"],
            "execution_mode": "sequential",
            "llm_model": "gemini-1.5-flash",
            "priority": 5,
            "timeout_seconds": 120,
            "retry_on_failure": True,
        },
        {
            "phase": 3,
            "phase_name": "Validation & Deduplication",
            "agents": ["company_validation"],
            "execution_mode": "sequential",
            "llm_model": "gemini-1.5-flash",
            "priority": 4,
            "timeout_seconds": 60,
            "retry_on_failure": False,
        },
        {
            "phase": 4,
            "phase_name": "Enrichment & Contact Discovery",
            "agents": ["company_enrichment", "contact_discovery"],
            "execution_mode": "parallel",
            "llm_model": "gemini-1.5-flash",
            "priority": 4,
            "timeout_seconds": 180,
            "retry_on_failure": True,
        },
        {
            "phase": 5,
            "phase_name": "Intelligence & Brief Generation",
            "agents": ["next_best_action", "business_brief"],
            "execution_mode": "sequential",
            "llm_model": "gemini-1.5-flash",
            "priority": 5,
            "timeout_seconds": 120,
            "retry_on_failure": True,
        },
    ]

    return {
        "strategy_name": "Standard Discovery Pipeline",
        "rationale": "Default sequential strategy — LLM planning unavailable",
        "execution_phases": phases,
        "targets": {
            "max_companies_to_discover": 20,
            "max_companies_to_process": 10,
            "min_icp_match_score": 0.6,
            "max_runtime_minutes": 30,
        },
        "hitl_triggers": [
            {
                "condition": "confidence_score < 0.5",
                "trigger_at": "business_brief",
                "reason": "Low confidence — human review required",
            },
            {
                "condition": "icp_match_score < 0.4",
                "trigger_at": "company_validation",
                "reason": "Poor ICP match — human validation needed",
            },
        ],
        "cost_estimate_usd": 0.05,
    }


async def planner_node(state: PlatformState) -> dict:
    """
    LangGraph node: Planner
    
    Reads ICP config, generates an execution strategy, and returns
    state updates with the strategy and initial agent specs.
    """
    print(f"[PLANNER] Building execution strategy for project {state['project_id']}")

    icp_config = state.get("icp_config", {})
    llm = _get_llm()

    strategy = None

    if llm:
        try:
            prompt_template = _load_prompt("planner.txt")
            business_context = (
                f"Industry: {icp_config.get('industry', [])}\n"
                f"Target Market: {icp_config.get('_target_market_description', 'Not specified')}\n"
                f"Geography: {icp_config.get('geography', [])}\n"
                f"Personas: {len(icp_config.get('personas', []))} defined\n"
                f"Triggers Enabled: {sum(1 for t in icp_config.get('triggers', []) if t.get('enabled'))}"
            )

            filled_prompt = prompt_template.replace(
                "{icp_config}", json.dumps(icp_config, indent=2)
            ).replace(
                "{business_context}", business_context
            )

            result = await llm.ainvoke([HumanMessage(content=filled_prompt)])
            raw = result.content if hasattr(result, "content") else str(result)
            strategy = json.loads(_clean_json(raw))
            print(f"[PLANNER] Strategy generated: {strategy.get('strategy_name', 'unnamed')}")

        except Exception as e:
            print(f"[PLANNER] LLM planning failed ({e}), using default strategy")
            strategy = _build_default_strategy(icp_config)
    else:
        print("[PLANNER] No LLM configured — using default strategy")
        strategy = _build_default_strategy(icp_config)

    return {
        "execution_strategy": strategy,
        "agent_specs": [],       # Agent Architect will populate this
        "trigger_signals": [],
        "candidate_companies": [],
        "validated_companies": [],
        "enriched_companies": [],
        "discovered_contacts": [],
        "nba_recommendations": [],
        "business_briefs": [],
        "hitl_required": False,
        "hitl_trigger_reason": "",
        "hitl_pending_brief_id": None,
        "hitl_action": None,
        "memory_hits": 0,
        "duplicates_avoided": 0,
        "agent_metrics": [],
        "total_cost_estimate": 0.0,
        "errors": [],
        "warnings": [],
        "current_company_index": 0,
    }
