"""
Platform Workflow Graph  (Agentic Upgrade)
==========================================
Replaces the old hardcoded node-per-agent graph with a dynamic DAG executor.

The old approach:
  - 9 hardcoded node functions (trigger_monitoring_node, company_discovery_node, ...)
  - 8 hardcoded edges wired at compile time
  - Same graph for every business

The new approach:
  - Fixed meta-nodes: planner → agent_architect → dag_executor → hitl_review → feedback_learning
  - dag_executor reads the DAG from state (produced by Planner + Agent Architect)
  - dag_executor runs each task node in dependency order using the Runtime Agent Manager
  - Different businesses run different DAG topologies through the SAME graph structure
  - Named agent templates (company_discovery, etc.) still work — DynamicAgent handles unknowns
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from planner.state import PlatformState
from planner.planner_agent import planner_node
from runtime.agent_architect import agent_architect_node
from planner.hitl_trigger import check_hitl_conditions

# The compiled graph singleton
_graph = None


# ── DAG Executor ────────────────────────────────────────────────────────────

async def dag_executor_node(state: PlatformState) -> dict:
    """
    The heart of the agentic upgrade.

    Reads the DAG (nodes + edges) from state, resolves the execution order
    using topological sort, and runs each agent through the Runtime Manager.

    This single node replaces the 7 hardcoded agent-wrapper nodes from v1.
    Different businesses execute different graphs through this one entrypoint.
    """
    from runtime.manager import run_agent_from_spec

    agent_specs = state.get("agent_specs", [])
    dag_edges = state.get("dag_edges", [])
    icp_config = state.get("icp_config", {})

    if not agent_specs:
        print("[DAG_EXECUTOR] No agent specs — nothing to execute")
        return {}

    print(f"[DAG_EXECUTOR] Executing DAG: {len(agent_specs)} nodes, {len(dag_edges)} edges")

    # ── Step 1: Build adjacency and in-degree for topological sort ───────────
    # Map agent_id → spec
    spec_map = {s["agent_id"]: s for s in agent_specs}

    # Build: child → [parents]  (who must finish before this node runs)
    predecessors: dict[str, set[str]] = {s["agent_id"]: set() for s in agent_specs}
    successors: dict[str, set[str]] = {s["agent_id"]: set() for s in agent_specs}

    for edge in dag_edges:
        frm = edge.get("from", "")
        to = edge.get("to", "")
        if frm in predecessors and to in predecessors:
            predecessors[to].add(frm)
            successors[frm].add(to)

    # ── Step 2: Kahn's algorithm — topological sort with parallel batching ───
    # Nodes with no predecessors can run immediately (first wave)
    remaining = set(spec_map.keys())
    completed: set[str] = set()
    combined_state = dict(state)  # running merged state
    combined_updates: dict = {}

    wave = 0
    while remaining:
        # Find all nodes whose predecessors are all completed
        ready = [
            nid for nid in remaining
            if predecessors[nid].issubset(completed)
        ]

        if not ready:
            print(f"[DAG_EXECUTOR] WARN: Circular dependency or orphaned nodes: {remaining}")
            break

        wave += 1
        print(f"[DAG_EXECUTOR] Wave {wave}: running {len(ready)} node(s) in parallel → {ready}")

        # Run ready nodes in parallel
        import asyncio
        tasks = [
            run_agent_from_spec(spec_map[nid], combined_state, icp_config)
            for nid in ready
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results into running state
        for nid, result in zip(ready, results):
            if isinstance(result, Exception):
                print(f"[DAG_EXECUTOR] Node {nid} FAILED: {result}")
                existing_errors = combined_state.get("errors", [])
                combined_state["errors"] = existing_errors + [{
                    "agent": nid,
                    "error": str(result),
                }]
            else:
                combined_state = {**combined_state, **_merge_lists(combined_state, result)}
                combined_updates = _merge_lists(combined_updates, result)

        completed.update(ready)
        remaining -= set(ready)

    print(f"[DAG_EXECUTOR] Completed {len(completed)} nodes in {wave} waves")
    return combined_updates


# ── Deduplication Node ───────────────────────────────────────────────────────

async def deduplication_check_node(state: PlatformState) -> dict:
    """Runs deduplication on discovered candidates before main DAG execution."""
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
            if dedup_res.get("flag_for_review"):
                c["possible_duplicate"] = True
            valid_candidates.append(c)

    return {
        "candidate_companies": valid_candidates,
        "duplicates_avoided": state.get("duplicates_avoided", 0) + duplicates,
    }


# ── HITL Node ────────────────────────────────────────────────────────────────

async def hitl_review_node(state: PlatformState) -> dict:
    """Pause point for Human-in-the-Loop. Graph interrupted before this node."""
    return {"hitl_required": False}


# ── Feedback Node ─────────────────────────────────────────────────────────────

async def feedback_learning_node(state: PlatformState) -> dict:
    """Store seen company domains in Redis for future deduplication."""
    from memory.deduplication import mark_company_seen
    for brief in state.get("business_briefs", []):
        domain = brief.get("company_domain", "")
        name = brief.get("company_name", "")
        if domain:
            await mark_company_seen(domain, company_name=name)
    return {}


# ── State Update Merge Helper ─────────────────────────────────────────────────

def _merge_lists(base: dict, update: dict) -> dict:
    """Merge two state dicts, concatenating list fields instead of overwriting."""
    result = dict(base)
    for key, value in update.items():
        if key in result and isinstance(result[key], list) and isinstance(value, list):
            result[key] = result[key] + value
        else:
            result[key] = value
    return result


# ── Graph Factory ────────────────────────────────────────────────────────────

def get_platform_graph():
    """
    Build and return the LangGraph executable.

    New topology (v2 — agentic):
      planner → agent_architect → deduplication_check → dag_executor → hitl_review → feedback_learning

    The dag_executor node runs the full business-specific DAG internally.
    """
    global _graph
    if _graph is not None:
        return _graph

    graph = StateGraph(PlatformState)

    # Meta-pipeline nodes
    graph.add_node("planner", planner_node)
    graph.add_node("agent_architect", agent_architect_node)
    graph.add_node("deduplication_check", deduplication_check_node)
    graph.add_node("dag_executor", dag_executor_node)          # ← THE DYNAMIC HEART
    graph.add_node("hitl_review", hitl_review_node)
    graph.add_node("feedback_learning", feedback_learning_node)

    # Fixed meta-pipeline edges
    graph.set_entry_point("planner")
    graph.add_edge("planner", "agent_architect")
    graph.add_edge("agent_architect", "dag_executor")

    # After DAG execution: HITL or continue
    graph.add_conditional_edges(
        "dag_executor",
        check_hitl_conditions,
        {"hitl": "hitl_review", "continue": "feedback_learning"},
    )

    graph.add_conditional_edges(
        "hitl_review",
        route_after_hitl,
        {"planner": "planner", "feedback_learning": "feedback_learning"},
    )
    graph.add_edge("feedback_learning", END)

    # Compile with memory checkpointer for HITL interruption
    checkpointer = MemorySaver()
    _graph = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl_review"],
    )

    print("[GRAPH] Platform graph compiled — dynamic DAG executor active")
    return _graph

def route_after_hitl(state: PlatformState) -> str:
    """Route back to planner if custom research requested, else finish."""
    if state.get("hitl_action") == "request_research":
        return "planner"
    return "feedback_learning"

