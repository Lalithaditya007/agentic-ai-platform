"""
Agent Architect Node
=====================
Converts the Planner's execution strategy into concrete runtime agent JSON specs.
Each spec tells the Runtime Agent Manager what agent to instantiate, what
capabilities to inject, and what model to use.
"""

from planner.state import PlatformState


# Maps agent template names → their allowed capability IDs (capability allowlist)
AGENT_CAPABILITY_ALLOWLIST: dict[str, list[str]] = {
    "trigger_monitoring": [
        "search.web_search",
        "search.news_search",
        "search.rss_monitoring",
    ],
    "company_discovery": [
        "search.web_search",
        "search.news_search",
        "business_intelligence.company_lookup",
    ],
    "company_validation": [
        "business_intelligence.company_lookup",
        "storage.postgresql",
    ],
    "company_enrichment": [
        "search.web_search",
        "search.news_search",
        "business_intelligence.company_lookup",
        "business_intelligence.funding_lookup",
        "business_intelligence.hiring_analysis",
        "storage.postgresql",
    ],
    "contact_discovery": [
        "contact_intelligence.email_lookup",
        "contact_intelligence.linkedin_lookup",
        "business_intelligence.company_lookup",
        "storage.postgresql",
    ],
    "next_best_action": [
        "storage.postgresql",
        "data_processing.structured_extraction",
    ],
    "business_brief": [
        "storage.postgresql",
    ],
}


def _build_agent_spec(agent_name: str, phase: dict, index: int) -> dict:
    """Build a single agent spec from a phase definition."""
    return {
        "agent_id": f"{agent_name}_agent_{index:03d}",
        "template": agent_name,
        "required_capabilities": AGENT_CAPABILITY_ALLOWLIST.get(agent_name, []),
        "model": phase.get("llm_model", "gemini-1.5-flash"),
        "execution_mode": phase.get("execution_mode", "sequential"),
        "priority": phase.get("priority", 5),
        "timeout_seconds": phase.get("timeout_seconds", 120),
        "retry_on_failure": phase.get("retry_on_failure", True),
        "max_retries": 3,
        "memory_access": ["read", "write"],
    }


async def agent_architect_node(state: PlatformState) -> dict:
    """
    LangGraph node: Agent Architect

    Reads execution strategy from state and produces concrete agent specs.
    """
    print(f"[AGENT_ARCHITECT] Building agent specs for project {state['project_id']}")

    strategy = state.get("execution_strategy", {})
    phases = strategy.get("execution_phases", [])

    if not phases:
        print("[AGENT_ARCHITECT] No phases in strategy — using default agent set")
        phases = [
            {"phase": 1, "agents": ["trigger_monitoring"], "execution_mode": "sequential",
             "llm_model": "gemini-1.5-flash", "priority": 5, "timeout_seconds": 60, "retry_on_failure": True},
            {"agent_type": "company_discovery",
             "llm_model": "gemini-1.5-flash", "priority": 5, "timeout_seconds": 120, "retry_on_failure": True},
            {"agent_type": "trigger_monitoring",
             "llm_model": "gemini-1.5-flash", "priority": 4, "timeout_seconds": 60, "retry_on_failure": False},
            {"agent_type": "qualification_research",
             "llm_model": "gemini-1.5-flash", "priority": 4, "timeout_seconds": 180, "retry_on_failure": True},
            {"phase": 5, "agents": ["next_best_action", "business_brief"], "execution_mode": "sequential",
             "llm_model": "gemini-1.5-flash", "priority": 5, "timeout_seconds": 120, "retry_on_failure": True},
        ]

    agent_specs = []
    spec_index = 1
    for phase in phases:
        for agent_name in phase.get("agents", []):
            spec = _build_agent_spec(agent_name, phase, spec_index)
            agent_specs.append(spec)
            spec_index += 1
            print(f"[AGENT_ARCHITECT] Spec: {spec['agent_id']} | model={spec['model']} | mode={spec['execution_mode']}")

    print(f"[AGENT_ARCHITECT] Generated {len(agent_specs)} agent specs")
    return {"agent_specs": agent_specs}
