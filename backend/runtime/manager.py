"""
Runtime Agent Manager
======================
Instantiates agent classes from specs, injects capabilities, and runs them.
Enforces the capability allowlist — agents cannot access out-of-spec capabilities.
"""

import asyncio
from datetime import datetime, timezone
from typing import Type

from runtime.agents.base_agent import BaseAgent
from capabilities.registry import capability_registry
from planner.state import PlatformState


# ── Agent Template Registry ─────────────────────────────────────────────────
# Maps template names to agent classes (lazy import to avoid circular imports)

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
    }


def instantiate_agent(spec: dict, icp_config: dict) -> BaseAgent:
    """
    Create a runtime agent from a spec, injecting only allowlisted capabilities.
    """
    registry = _get_agent_registry()
    template = spec.get("template", "")
    agent_class = registry.get(template)
    if not agent_class:
        raise ValueError(f"Unknown agent template: '{template}'")

    # Resolve only the allowlisted capabilities
    allowed_caps = spec.get("required_capabilities", [])
    resolved_caps = capability_registry.resolve(allowed_caps)
    unavailable = set(allowed_caps) - set(resolved_caps.keys())
    if unavailable:
        print(f"[MANAGER] WARN: Capabilities unavailable for {spec['agent_id']}: {unavailable}")

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
    """
    if not phase_specs:
        return {}

    execution_mode = phase_specs[0].get("execution_mode", "sequential")
    combined: dict = {}

    if execution_mode == "parallel":
        # Run all agents in parallel, merge results
        tasks = [run_agent_from_spec(spec, state, icp_config) for spec in phase_specs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for spec, result in zip(phase_specs, results):
            if isinstance(result, Exception):
                print(f"[MANAGER] Agent {spec['agent_id']} failed: {result}")
            else:
                combined = _merge_state_updates(combined, result)
    else:
        # Run sequentially
        for spec in phase_specs:
            result = await run_agent_from_spec(spec, state, icp_config)
            combined = _merge_state_updates(combined, result)
            # Update state with intermediate results for next agent
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
