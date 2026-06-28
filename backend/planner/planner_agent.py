"""
Planner Agent Node  (Agentic Upgrade)
=======================================
The Planner is the brain of the platform. It reads the ICP config + the live
capability catalogue and uses an LLM to build a CUSTOM Directed Acyclic Graph
(DAG) of agent tasks for THIS specific business.

Key changes from the old static version:
  - No more _build_default_strategy() hardcoded 5-step pipeline
  - LLM receives the REAL capability catalogue (from registry) so it knows
    exactly what tools are available when designing the DAG
  - Output is a DAG {nodes, edges} — not a flat phase list
  - Fallback is a minimal 3-node DAG, not the same hardcoded pipeline
  - Every business gets a different graph
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage

from planner.state import PlatformState
from config import settings
from runtime.agents.base_agent import invoke_with_retry, get_primary_llm


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")



def _clean_json(raw: str) -> str:
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    return cleaned.strip()


def _build_minimal_fallback_dag(icp_config: dict) -> dict:
    """
    Minimal 3-node fallback DAG when LLM is unavailable.
    This is intentionally DIFFERENT from the old hardcoded 5-step pipeline —
    it's just enough to prove the system works, not a fixed workflow.
    The Planner should always use LLM when available.
    """
    industry = icp_config.get("industry", ["unknown"])[0] if icp_config.get("industry") else "unknown"
    return {
        "strategy_name": f"Minimal Fallback DAG ({industry})",
        "rationale": "LLM unavailable — minimal fallback. Run with LLM for business-specific planning.",
        "dag": {
            "nodes": [
                {
                    "task_id": "discovery_001",
                    "agent_template": "company_discovery",
                    "goal": f"Find companies matching this ICP in the {industry} sector using web search.",
                    "required_capabilities": [
                        "search.web_search",
                        "search.news_search",
                        "business_intelligence.company_lookup",
                    ],
                    "model": "gemini-1.5-flash",
                    "priority": 5,
                    "timeout_seconds": 120,
                    "retry_on_failure": True,
                },
                {
                    "task_id": "validation_001",
                    "agent_template": "company_validation",
                    "goal": "Validate discovered companies against ICP rules and deduplicate.",
                    "required_capabilities": [
                        "business_intelligence.company_lookup",
                        "storage.postgresql",
                    ],
                    "model": "gemini-1.5-flash",
                    "priority": 4,
                    "timeout_seconds": 60,
                    "retry_on_failure": False,
                },
                {
                    "task_id": "brief_001",
                    "agent_template": "business_brief",
                    "goal": "Generate intelligence brief for validated companies.",
                    "required_capabilities": ["storage.postgresql"],
                    "model": "gemini-1.5-flash",
                    "priority": 5,
                    "timeout_seconds": 120,
                    "retry_on_failure": True,
                },
            ],
            "edges": [
                {"from": "discovery_001", "to": "validation_001", "condition": "on_success"},
                {"from": "validation_001", "to": "brief_001", "condition": "on_data"},
            ],
        },
        "targets": {
            "max_companies_to_discover": 10,
            "max_companies_to_process": 5,
            "min_icp_match_score": 0.6,
            "max_runtime_minutes": 20,
        },
        "hitl_triggers": [
            {
                "condition": "confidence_score < 0.5",
                "trigger_at": "brief_001",
                "reason": "Low confidence — human review required",
            }
        ],
        "cost_estimate_usd": 0.03,
    }


async def planner_node(state: PlatformState) -> dict:
    """
    LangGraph node: Planner (Agentic Upgrade)

    1. Loads the live capability catalogue from registry
    2. Injects it into the LLM prompt so planning is grounded in real capabilities
    3. LLM generates a custom DAG for this specific business
    4. Falls back to minimal 3-node DAG only if LLM is completely unavailable
    """
    print(f"[PLANNER] Building custom DAG for project {state['project_id']}")

    icp_config = state.get("icp_config", {})
    try:
        llm = get_primary_llm(temperature=0.1)
    except RuntimeError:
        llm = None

    # ── Load live capability catalogue ──────────────────────────────────────
    from capabilities.registry import capability_registry
    capability_catalogue = capability_registry.get_catalogue_text()
    print(f"[PLANNER] Injecting {len(capability_registry.list_available())} capabilities into prompt")

    strategy = None

    if llm:
        try:
            # ── Branch: Sub-Graph generation for HITL Research ──────────
            if state.get("hitl_action") == "request_research":
                research_query = state.get("hitl_action_details", {}).get("research_query", "Unknown query")
                print(f"[PLANNER] Generating targeted research sub-graph for: '{research_query}'")
                prompt_template = _load_prompt("research_planner.txt") if (_load_prompt("research_planner.txt") if (Path(__file__).parent.parent / "prompts" / "research_planner.txt").exists() else False) else _load_prompt("planner.txt") + f"\n\nCRITICAL INSTRUCTION: You are generating a targeted RESEARCH SUB-GRAPH to answer this query: '{research_query}'. Generate a minimal DAG using ONLY the capabilities needed to find this info. Do NOT generate the full pipeline."
            else:
                prompt_template = _load_prompt("planner.txt")

            business_context = (
                f"Industry: {icp_config.get('industry', [])}\n"
                f"Target Market: {icp_config.get('_target_market_description', 'Not specified')}\n"
                f"Geography: {icp_config.get('geography', [])}\n"
                f"Personas: {len(icp_config.get('personas', []))} defined\n"
                f"Triggers Enabled: {sum(1 for t in icp_config.get('triggers', []) if t.get('enabled'))}\n"
                f"Qualification Rules: {len(icp_config.get('qualification_rules', []))} rules"
            )

            filled_prompt = (
                prompt_template
                .replace("{icp_config}", json.dumps(icp_config, indent=2))
                .replace("{business_context}", business_context)
                .replace("{capability_catalogue}", capability_catalogue)
            )

            result = await invoke_with_retry([HumanMessage(content=filled_prompt)], temperature=0.1, model="google/gemma-2-9b-it:free")
            raw = result.content if hasattr(result, "content") else str(result)
            strategy = json.loads(_clean_json(raw))

            # Validate the DAG structure
            if "dag" not in strategy or "nodes" not in strategy["dag"]:
                raise ValueError("LLM response missing 'dag.nodes' — invalid DAG structure")

            node_count = len(strategy["dag"].get("nodes", []))
            edge_count = len(strategy["dag"].get("edges", []))
            print(f"[PLANNER] DAG generated: '{strategy.get('strategy_name')}' | {node_count} nodes, {edge_count} edges")
            print(f"[PLANNER] Rationale: {strategy.get('rationale', '')[:150]}")

        except Exception as e:
            print(f"[PLANNER] LLM planning failed ({e}), using minimal fallback DAG")
            strategy = _build_minimal_fallback_dag(icp_config)
    else:
        print("[PLANNER] No LLM configured — using minimal fallback DAG")
        strategy = _build_minimal_fallback_dag(icp_config)

    return {
        "execution_strategy": strategy,
        "agent_specs": [],        # Agent Architect will populate this from the DAG
        "dag_edges": [],          # Agent Architect will populate this from the DAG
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
        "total_cost_estimate": strategy.get("cost_estimate_usd", 0.0),
        "errors": [],
        "warnings": [],
        "current_company_index": 0,
    }
