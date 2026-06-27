"""
Platform State Schema for LangGraph
=====================================
Defines the shared state that flows through the entire agent pipeline.
All nodes read from and write to this state.
"""

from typing import TypedDict, Optional, List, Any, Annotated
import operator


class AgentMetric(TypedDict):
    agent_name: str
    status: str          # success | failure | skipped
    duration_ms: int
    tokens_used: int
    cost_estimate: float
    output_summary: str


class HITLTrigger(TypedDict):
    reason: str
    triggered_at: str    # node name
    severity: str        # high | medium | low
    brief_id: Optional[str]


class PlatformState(TypedDict):
    # ── Input ─────────────────────────────────────────────────────────────────
    project_id: str
    workflow_run_id: str
    icp_config: dict           # Full ICP configuration dict

    # ── Planner Outputs ───────────────────────────────────────────────────────
    execution_strategy: Optional[dict]    # Strategy from Planner node
    agent_specs: List[dict]               # Specs from Agent Architect node

    # ── Discovery Pipeline ────────────────────────────────────────────────────
    trigger_signals: List[dict]           # Buying signals from Trigger Monitor
    candidate_companies: List[dict]       # Raw company candidates from discovery

    # ── Per-Company Processing ────────────────────────────────────────────────
    current_company_index: int            # Index into candidate_companies
    validated_companies: List[dict]       # Passed validation
    enriched_companies: List[dict]        # Deeply enriched
    discovered_contacts: List[dict]       # Key contacts found

    # ── Results ───────────────────────────────────────────────────────────────
    nba_recommendations: List[dict]       # Next Best Action per company
    business_briefs: List[dict]           # Final briefs

    # ── HITL (Human-in-the-Loop) ─────────────────────────────────────────────
    hitl_required: bool
    hitl_trigger_reason: str
    hitl_pending_brief_id: Optional[str]
    hitl_action: Optional[str]            # approve | reject | modify | request_research

    # ── Memory / Deduplication ───────────────────────────────────────────────
    memory_hits: int                      # Companies served from cache
    duplicates_avoided: int               # Companies skipped due to dedup

    # ── Analytics ────────────────────────────────────────────────────────────
    agent_metrics: List[AgentMetric]
    total_cost_estimate: float

    # ── Error Handling ────────────────────────────────────────────────────────
    errors: List[dict]                    # Non-fatal errors during execution
    warnings: List[str]
