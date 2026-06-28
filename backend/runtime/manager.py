"""
Runtime Agent Manager  (Agentic Upgrade)
=========================================
Instantiates agents from specs, injects capabilities, and runs them.

Key change from v1:
  - _get_agent_registry() still maps known template names → named classes
  - NEW: if template is NOT in the registry, fall back to DynamicAgent
  - This means the Planner can invent ANY new agent type and the Manager
    will run it via DynamicAgent without any code changes
  - Enforces capability allowlist — agents cannot use caps outside their spec
"""

import asyncio
from datetime import datetime, timezone
from typing import Type

from runtime.agents.base_agent import BaseAgent
from capabilities.registry import capability_registry
from planner.state import PlatformState


# ── Named Agent Template Registry ───────────────────────────────────────────
# Maps known template names → dedicated agent classes.
# If a template is NOT here, DynamicAgent handles it automatically.

def _get_agent_registry() -> dict[str, Type[BaseAgent]]:
    from runtime.agents.trigger_monitoring import TriggerMonitoringAgent
    from runtime.agents.company_discovery import CompanyDiscoveryAgent
    from runtime.agents.company_validation import CompanyValidationAgent
    from runtime.agents.company_enrichment import CompanyEnrichmentAgent
    from runtime.agents.contact_discovery import ContactDiscoveryAgent
    from runtime.agents.next_best_action import NextBestActionAgent
    from runtime.agents.business_brief import BusinessBriefAgent

    return {
        "trigger_monitoring": TriggerMonitoringAgent,
        "company_discovery": CompanyDiscoveryAgent,
        "company_validation": CompanyValidationAgent,
        "company_enrichment": CompanyEnrichmentAgent,
        "contact_discovery": ContactDiscoveryAgent,
        "next_best_action": NextBestActionAgent,
        "business_brief": BusinessBriefAgent,
        # DynamicAgent is NOT listed here — it's the implicit fallback
    }


def instantiate_agent(spec: dict, icp_config: dict) -> BaseAgent:
    """
    Create a runtime agent from a spec, injecting only allowlisted capabilities.

    Resolution order:
      1. Check named registry → use dedicated class (full domain logic)
      2. Not found → use DynamicAgent (goal-driven, LLM-only execution)
    """
    registry = _get_agent_registry()
    template = spec.get("template", "")
    agent_class = registry.get(template)

    if not agent_class:
        # ── Agentic Fallback: DynamicAgent handles unknown templates ──────
        from runtime.agents.dynamic_agent import DynamicAgent
        print(f"[MANAGER] Template '{template}' not in registry — routing to DynamicAgent")
        agent_class = DynamicAgent

    # Resolve only the allowlisted capabilities (enforces least-privilege)
    allowed_caps = spec.get("required_capabilities", [])
    resolved_caps = capability_registry.resolve(allowed_caps)
    unavailable = set(allowed_caps) - set(resolved_caps.keys())
    if unavailable:
        print(f"[MANAGER] WARN: Unavailable caps for {spec['agent_id']}: {unavailable}")

    return agent_class(
        icp_config=icp_config,
        agent_spec=spec,
        capabilities=resolved_caps,
    )


async def run_agent_from_spec(spec: dict, state: dict, icp_config: dict) -> dict:
    """Instantiate and execute a single agent, returning state updates."""
    agent = instantiate_agent(spec, icp_config)
    return await agent.execute(state)


async def run_phase(phase_specs: list[dict], state: dict, icp_config: dict) -> dict:
    """
    Run a group of agents in the execution mode specified (sequential or parallel).
    Merges all state update dicts and returns combined result.
    Kept for backward compatibility — the dag_executor in workflow_graph.py
    handles the primary execution path now.
    """
    if not phase_specs:
        return {}

    execution_mode = phase_specs[0].get("execution_mode", "sequential")
    combined: dict = {}

    if execution_mode == "parallel":
        tasks = [run_agent_from_spec(spec, state, icp_config) for spec in phase_specs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for spec, result in zip(phase_specs, results):
            if isinstance(result, Exception):
                print(f"[MANAGER] Agent {spec['agent_id']} failed: {result}")
            else:
                combined = _merge_state_updates(combined, result)
    else:
        for spec in phase_specs:
            result = await run_agent_from_spec(spec, state, icp_config)
            combined = _merge_state_updates(combined, result)
            state = {**state, **result}

    return combined


def _merge_state_updates(base: dict, update: dict) -> dict:
    """Merge two state update dicts, concatenating list fields."""
    result = dict(base)
    for key, value in update.items():
        if key in result and isinstance(result[key], list) and isinstance(value, list):
            result[key] = result[key] + value
        else:
            result[key] = value
    return result
