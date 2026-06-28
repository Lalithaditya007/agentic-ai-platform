"""
Agent Architect Node  (Agentic Upgrade)
=========================================
Converts the Planner's DAG nodes into concrete, executable AgentSpec objects.

Key changes from the old static version:
  - Removed AGENT_CAPABILITY_ALLOWLIST static dict
  - Now calls an LLM to validate + refine capability assignments per task
  - Produces AgentSpecs with proper input/output schemas
  - Falls back to using the Planner's capability list directly (no hardcoded map)
  - The Architect is now an actual AI reasoner, not a lookup table
"""

import json
import re
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


def _build_spec_from_node(node: dict, index: int) -> dict:
    """
    Build an AgentSpec directly from a DAG node without LLM.
    Used as fallback when LLM is unavailable.
    The Planner's capability list is used as-is (already validated against registry).
    """
    return {
        "agent_id": node.get("task_id", f"agent_{index:03d}"),
        "template": node.get("agent_template", "dynamic_agent"),
        "goal": node.get("goal", "Execute assigned task"),
        "required_capabilities": node.get("required_capabilities", []),
        "model": node.get("model", "gemini-1.5-flash"),
        "priority": node.get("priority", 5),
        "timeout_seconds": node.get("timeout_seconds", 120),
        "retry_on_failure": node.get("retry_on_failure", True),
        "max_retries": 3,
        "memory_access": ["read", "write"],
        "input_schema": "PlatformState",
        "output_schema": "StateUpdate",
        "capability_rationale": "Built directly from Planner DAG node (no LLM refinement)",
    }


async def agent_architect_node(state: PlatformState) -> dict:
    """
    LangGraph node: Agent Architect (Agentic Upgrade)

    1. Reads the DAG from execution_strategy (output of Planner)
    2. Loads live capability catalogue
    3. Uses LLM to validate + refine capability assignments per task node
    4. Produces concrete AgentSpec objects consumed by Runtime Agent Manager
    """
    print(f"[AGENT_ARCHITECT] Building agent specs for project {state['project_id']}")

    strategy = state.get("execution_strategy", {})
    dag = strategy.get("dag", {})
    nodes = dag.get("nodes", [])

    if not nodes:
        print("[AGENT_ARCHITECT] No DAG nodes found in strategy — producing empty spec list")
        return {"agent_specs": []}

    # ── Load live capability catalogue ──────────────────────────────────────
    from capabilities.registry import capability_registry
    available_caps = capability_registry.list_available()
    capability_catalogue = capability_registry.get_catalogue_text()

    # ── Filter nodes to only include available capabilities ─────────────────
    # This ensures the Planner didn't hallucinate a capability that isn't loaded
    sanitized_nodes = []
    for node in nodes:
        original_caps = node.get("required_capabilities", [])
        valid_caps = [c for c in original_caps if c in available_caps]
        skipped = set(original_caps) - set(valid_caps)
        if skipped:
            print(f"[AGENT_ARCHITECT] Removed unavailable caps from {node['task_id']}: {skipped}")
        sanitized_nodes.append({**node, "required_capabilities": valid_caps})

    icp_config = state.get("icp_config", {})
    industry = icp_config.get("industry", ["unknown"])
    if isinstance(industry, list):
        industry = industry[0] if industry else "unknown"
    target_market = icp_config.get("_target_market_description", "Not specified")

    try:
        llm = get_primary_llm(temperature=0.0)
    except RuntimeError:
        llm = None
    agent_specs = []

    if llm:
        try:
            prompt_template = _load_prompt("agent_architect.txt")
            filled_prompt = (
                prompt_template
                .replace("{capability_catalogue}", capability_catalogue)
                .replace("{dag_nodes}", json.dumps(sanitized_nodes, indent=2))
                .replace("{industry}", str(industry))
                .replace("{target_market}", str(target_market))
            )

            result = await invoke_with_retry([HumanMessage(content=filled_prompt)], temperature=0.0, model="openai/gpt-oss-120b:free")
            raw = result.content if hasattr(result, "content") else str(result)
            agent_specs = json.loads(_clean_json(raw))

            if not isinstance(agent_specs, list):
                raise ValueError("Agent Architect LLM did not return a list of AgentSpecs")

            print(f"[AGENT_ARCHITECT] LLM assigned capabilities for {len(agent_specs)} agents")
            for spec in agent_specs:
                caps = spec.get("required_capabilities", [])
                print(f"  → {spec['agent_id']} | template={spec['template']} | caps={len(caps)} | model={spec.get('model')}")

        except Exception as e:
            print(f"[AGENT_ARCHITECT] LLM spec refinement failed ({e}), building specs from DAG nodes directly")
            agent_specs = [_build_spec_from_node(node, i + 1) for i, node in enumerate(sanitized_nodes)]
    else:
        print("[AGENT_ARCHITECT] No LLM — building specs from DAG nodes directly")
        agent_specs = [_build_spec_from_node(node, i + 1) for i, node in enumerate(sanitized_nodes)]

    # ── Attach DAG edges to state for dynamic executor ───────────────────────
    dag_edges = dag.get("edges", [])
    print(f"[AGENT_ARCHITECT] Final: {len(agent_specs)} agent specs, {len(dag_edges)} DAG edges")

    return {
        "agent_specs": agent_specs,
        "dag_edges": dag_edges,   # Stored in state for workflow_graph dynamic executor
    }
