"""
Dynamic Agent  (Agentic Upgrade — NEW)
========================================
A single generic agent class that can execute ANY task defined in an AgentSpec.

The key principle:
  - Named agent classes (CompanyDiscoveryAgent, etc.) define their behaviour in code
  - DynamicAgent defines its behaviour from its AgentSpec at runtime
  - The Runtime Manager falls back to DynamicAgent for any template it doesn't recognise
  - This means the Planner can invent new agent types without any new Python files

How it works:
  1. Receives an AgentSpec containing: goal, required_capabilities, output_schema
  2. Builds a prompt from the goal + current state context + ICP
  3. Calls the LLM with its injected capabilities as tools (if available)
  4. Returns structured output conforming to the declared output_schema
  5. Saves output to state under the agent's task_id key

This is what makes the platform truly agentic — the platform can handle novel
business domains without a developer writing a new agent file.
"""

import json
from datetime import datetime, timezone

from runtime.agents.base_agent import BaseAgent


class DynamicAgent(BaseAgent):
    """
    A generic runtime agent that derives its entire identity from its AgentSpec.
    Used for any agent template not covered by a named class.
    """

    agent_name = "dynamic_agent"

    def __init__(self, icp_config: dict, agent_spec: dict = None, capabilities: dict = None):
        super().__init__(icp_config=icp_config, agent_spec=agent_spec, capabilities=capabilities)
        # Override agent_name from spec so logs are meaningful
        self.agent_name = agent_spec.get("agent_id", "dynamic_agent") if agent_spec else "dynamic_agent"
        self.goal = (agent_spec or {}).get("goal", "Execute the assigned intelligence task")
        self.output_schema = (agent_spec or {}).get("output_schema", "StateUpdate")
        self.template = (agent_spec or {}).get("template", "dynamic_agent")

    def _build_capability_summary(self) -> str:
        """Format the injected capabilities as a readable list for the LLM prompt."""
        if not self.capabilities:
            return "No capabilities injected."
        lines = []
        for cap_id, plugin in self.capabilities.items():
            lines.append(f"  • {cap_id}: {plugin.description}")
        return "\n".join(lines)

    def _build_prompt(self, state: dict) -> str:
        """
        Build the runtime prompt for this agent.
        The goal from AgentSpec drives the agent's behaviour.
        The ICP and state context are injected so the agent has full business awareness.
        """
        icp_summary = json.dumps({
            "industry": self.icp_config.get("industry", []),
            "geography": self.icp_config.get("geography", []),
            "personas": [p.get("title", "") for p in self.icp_config.get("personas", [])],
            "qualification_rules": self.icp_config.get("qualification_rules", []),
        }, indent=2)

        # Summarise relevant state context (avoid dumping entire state)
        context_parts = []
        if state.get("trigger_signals"):
            context_parts.append(f"Trigger signals found: {len(state['trigger_signals'])}")
        if state.get("candidate_companies"):
            context_parts.append(f"Candidate companies: {len(state['candidate_companies'])}")
        if state.get("validated_companies"):
            context_parts.append(f"Validated companies: {len(state['validated_companies'])}")
        if state.get("enriched_companies"):
            context_parts.append(f"Enriched companies: {len(state['enriched_companies'])}")

        context_str = "\n".join(context_parts) if context_parts else "No prior pipeline results."

        return f"""You are an AI agent in a B2B customer discovery platform.

TASK GOAL:
{self.goal}

BUSINESS ICP:
{icp_summary}

PIPELINE CONTEXT:
{context_str}

AVAILABLE CAPABILITIES YOU CAN USE:
{self._build_capability_summary()}

OUTPUT SCHEMA: {self.output_schema}

INSTRUCTIONS:
1. Execute the task goal above using the available capabilities if needed.
2. Use web search for real-time information when relevant.
3. Return structured JSON that represents your findings.
4. If a capability is unavailable, work with the information already in context.
5. Never fabricate company names, contacts, or data — mark missing info as "unavailable".

Return ONLY valid JSON. The structure should match: {self.output_schema}
If outputting a list of companies, contacts, signals, or actions — return a list.
Always include a "confidence_score" (0.0–1.0) and "source" field in your output.
"""

    async def run(self, state: dict) -> dict:
        """
        Execute the dynamic agent's task.

        Strategy:
        1. Use web search capability if available and task needs real-time data
        2. Call LLM with the goal-driven prompt
        3. Parse and return structured output
        """
        print(f"[{self.agent_name}] Goal: {self.goal[:80]}...")

        # ── Use search capability if available ────────────────────────────
        search_results = []
        if "search.web_search" in self.capabilities:
            # Extract a search query from the goal using simple heuristics
            icp_industries = self.icp_config.get("industry", [])
            industry_str = icp_industries[0] if icp_industries else ""
            search_query = f"{self.goal} {industry_str}".strip()[:200]
            print(f"[{self.agent_name}] Web search: {search_query[:80]}")
            search_results = await self.web_search(search_query, max_results=5)

        # ── Build and invoke LLM ────────────────────────────────────────
        prompt = self._build_prompt(state)

        if search_results:
            search_text = "\n".join([
                f"- {r.get('title', '')}: {r.get('content', '')[:300]}"
                for r in search_results[:3]
            ])
            prompt += f"\n\nRECENT SEARCH RESULTS (use these as data sources):\n{search_text}"

        try:
            result_data = await self.ask_llm_for_json(prompt, model=self.agent_spec.get("model"))
        except Exception as e:
            print(f"[{self.agent_name}] LLM call failed: {e}")
            result_data = {
                "status": "failed",
                "error": str(e),
                "confidence_score": 0.0,
                "source": "dynamic_agent_fallback",
            }

        # ── Map result to state key ────────────────────────────────────
        # The task_id becomes the key in state where results are stored.
        # Standard templates map to known state keys; custom agents store under their task_id.
        state_key = _template_to_state_key(self.template)
        existing = state.get(state_key, [])

        # Wrap dict results in a list for consistent state handling
        if isinstance(result_data, dict):
            result_data = [result_data]

        metric = self.build_metric(
            status="success",
            output_summary=f"Dynamic agent '{self.template}': {len(result_data)} result(s)",
        )

        return {
            state_key: existing + result_data if isinstance(existing, list) else result_data,
            "agent_metrics": state.get("agent_metrics", []) + [metric],
        }


def _template_to_state_key(template: str) -> str:
    """
    Maps agent template names to their state field.
    Unknown templates store results under their own template name.
    """
    TEMPLATE_STATE_MAP = {
        "trigger_monitoring": "trigger_signals",
        "company_discovery": "candidate_companies",
        "company_validation": "validated_companies",
        "company_enrichment": "enriched_companies",
        "contact_discovery": "discovered_contacts",
        "next_best_action": "nba_recommendations",
        "business_brief": "business_briefs",
    }
    return TEMPLATE_STATE_MAP.get(template, f"custom_{template}_results")
