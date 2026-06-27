"""
Platform Workflow Graph
========================
Compiles the LangGraph StateGraph from all individual agent nodes.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from planner.state import PlatformState
from planner.planner_agent import planner_node
from runtime.agent_architect import agent_architect_node
from planner.hitl_trigger import check_hitl_conditions
from runtime.manager import run_phase

# The compiled graph
_graph = None


# Wrapper nodes for runtime agents
async def trigger_monitoring_node(state: PlatformState) -> dict:
    specs = [s for s in state["agent_specs"] if s["template"] == "trigger_monitoring"]
    return await run_phase(specs, state, state["icp_config"])

async def company_discovery_node(state: PlatformState) -> dict:
    specs = [s for s in state["agent_specs"] if s["template"] == "company_discovery"]
    return await run_phase(specs, state, state["icp_config"])

async def company_validation_node(state: PlatformState) -> dict:
    specs = [s for s in state["agent_specs"] if s["template"] == "company_validation"]
    return await run_phase(specs, state, state["icp_config"])

async def company_enrichment_node(state: PlatformState) -> dict:
    specs = [s for s in state["agent_specs"] if s["template"] == "company_enrichment"]
    return await run_phase(specs, state, state["icp_config"])

async def contact_discovery_node(state: PlatformState) -> dict:
    specs = [s for s in state["agent_specs"] if s["template"] == "contact_discovery"]
    return await run_phase(specs, state, state["icp_config"])

async def next_best_action_node(state: PlatformState) -> dict:
    specs = [s for s in state["agent_specs"] if s["template"] == "next_best_action"]
    return await run_phase(specs, state, state["icp_config"])

async def business_brief_node(state: PlatformState) -> dict:
    specs = [s for s in state["agent_specs"] if s["template"] == "business_brief"]
    return await run_phase(specs, state, state["icp_config"])

async def deduplication_check_node(state: PlatformState) -> dict:
    """Runs deduplication on discovered candidates."""
    from memory.deduplication import check_deduplication
    candidates = state.get("candidate_companies", [])
    valid_candidates = []
    duplicates = 0
    
    for c in candidates:
        domain = c.get("domain", "")
        name = c.get("name", "")
        if not domain:
            valid_candidates.append(c)
            continue
            
        dedup_res = await check_deduplication(domain, name)
        if dedup_res["skip"]:
            print(f"[DEDUP] Skipping {name} ({domain}) - {dedup_res['reason']}")
            duplicates += 1
        else:
            valid_candidates.append(c)
            
    return {
        "candidate_companies": valid_candidates,
        "duplicates_avoided": state.get("duplicates_avoided", 0) + duplicates
    }

def route_after_dedup(state: PlatformState) -> str:
    if not state.get("candidate_companies"):
        return "skip"
    return "validate"

async def hitl_review_node(state: PlatformState) -> dict:
    """This node is just a pause point. Graph will be interrupted before it."""
    # Action taken in HITL API will update state
    return {"hitl_required": False}

async def feedback_learning_node(state: PlatformState) -> dict:
    """Store feedback for future learning."""
    # Mark domains as seen
    from memory.deduplication import mark_company_seen
    for brief in state.get("business_briefs", []):
        domain = brief.get("company_domain", "")
        if domain:
            await mark_company_seen(domain)
    return {}


def get_platform_graph():
    """Build and return the LangGraph executable."""
    global _graph
    if _graph is not None:
        return _graph

    graph = StateGraph(PlatformState)
    
    graph.add_node("planner", planner_node)
    graph.add_node("agent_architect", agent_architect_node)
    graph.add_node("trigger_monitoring", trigger_monitoring_node)
    graph.add_node("company_discovery", company_discovery_node)
    graph.add_node("deduplication_check", deduplication_check_node)
    graph.add_node("company_validation", company_validation_node)
    graph.add_node("company_enrichment", company_enrichment_node)
    graph.add_node("contact_discovery", contact_discovery_node)
    graph.add_node("next_best_action", next_best_action_node)
    graph.add_node("business_brief", business_brief_node)
    graph.add_node("hitl_review", hitl_review_node)
    graph.add_node("feedback_learning", feedback_learning_node)
    
    # Edges
    graph.set_entry_point("planner")
    graph.add_edge("planner", "agent_architect")
    graph.add_edge("agent_architect", "trigger_monitoring")
    graph.add_edge("trigger_monitoring", "company_discovery")
    graph.add_edge("company_discovery", "deduplication_check")
    
    graph.add_conditional_edges(
        "deduplication_check",
        route_after_dedup,
        {"skip": END, "validate": "company_validation"}
    )
    
    graph.add_edge("company_validation", "company_enrichment")
    graph.add_edge("company_enrichment", "contact_discovery")
    graph.add_edge("contact_discovery", "next_best_action")
    graph.add_edge("next_best_action", "business_brief")
    
    graph.add_conditional_edges(
        "business_brief",
        check_hitl_conditions,
        {"hitl": "hitl_review", "continue": "feedback_learning"}
    )
    
    graph.add_edge("hitl_review", "feedback_learning")
    graph.add_edge("feedback_learning", END)
    
    # Compile with memory checkpointer for HITL interruption
    checkpointer = MemorySaver()
    _graph = graph.compile(checkpointer=checkpointer, interrupt_before=["hitl_review"])
    
    return _graph
