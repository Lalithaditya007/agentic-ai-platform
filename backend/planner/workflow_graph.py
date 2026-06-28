"""
Platform Workflow Graph
=======================
Replaces the old hardcoded node-per-agent graph with a dynamic DAG executor.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from planner.hitl_trigger import check_hitl_conditions
from planner.planner_agent import planner_node
from planner.state import PlatformState
from runtime.agent_architect import agent_architect_node

_graph = None


async def dag_executor_node(state: PlatformState) -> dict:
    """
    Execute the planner-produced DAG by resolving ready nodes wave by wave.
    """
    from runtime.manager import run_agent_from_spec

    agent_specs = state.get("agent_specs", [])
    dag_edges = state.get("dag_edges", [])
    icp_config = state.get("icp_config", {})

    if not agent_specs:
        print("[DAG_EXECUTOR] No agent specs - nothing to execute")
        return {}

    print(f"[DAG_EXECUTOR] Executing DAG: {len(agent_specs)} nodes, {len(dag_edges)} edges")

    spec_map = {spec["agent_id"]: spec for spec in agent_specs}
    predecessors: dict[str, set[str]] = {spec["agent_id"]: set() for spec in agent_specs}
    successors: dict[str, set[str]] = {spec["agent_id"]: set() for spec in agent_specs}

    for edge in dag_edges:
        frm = edge.get("from", "")
        to = edge.get("to", "")
        if frm in predecessors and to in predecessors:
            predecessors[to].add(frm)
            successors[frm].add(to)

    remaining = set(spec_map.keys())
    completed: set[str] = set()
    combined_state = dict(state)
    combined_updates: dict = {}

    wave = 0
    while remaining:
        ready = [
            node_id for node_id in remaining
            if predecessors[node_id].issubset(completed)
        ]

        if not ready:
            print(f"[DAG_EXECUTOR] WARN: Circular dependency or orphaned nodes: {remaining}")
            break

        wave += 1
        print(f"[DAG_EXECUTOR] Wave {wave}: running {len(ready)} node(s) in parallel -> {ready}")

        import asyncio

        tasks = [
            run_agent_from_spec(spec_map[node_id], combined_state, icp_config)
            for node_id in ready
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for node_id, result in zip(ready, results):
            if isinstance(result, Exception):
                print(f"[DAG_EXECUTOR] Node {node_id} FAILED: {result}")
                combined_state["errors"] = combined_state.get("errors", []) + [{
                    "agent": node_id,
                    "error": str(result),
                }]
                continue

            combined_state = {**combined_state, **_merge_lists(combined_state, result)}
            combined_updates = _merge_lists(combined_updates, result)

        completed.update(ready)
        remaining -= set(ready)

    print(f"[DAG_EXECUTOR] Completed {len(completed)} nodes in {wave} waves")
    return combined_updates


async def deduplication_check_node(state: PlatformState) -> dict:
    """Run deduplication on discovered candidates before main DAG execution."""
    from memory.deduplication import check_deduplication

    candidates = state.get("candidate_companies", [])
    valid_candidates = []
    duplicates = 0

    for candidate in candidates:
        domain = candidate.get("domain", "")
        name = candidate.get("name", "")
        if not domain:
            valid_candidates.append(candidate)
            continue

        dedup_res = await check_deduplication(domain, name)
        if dedup_res["skip"]:
            print(f"[DEDUP] Skipping {name} ({domain}) - {dedup_res['reason']}")
            duplicates += 1
            continue

        if dedup_res.get("flag_for_review"):
            candidate["possible_duplicate"] = True
        valid_candidates.append(candidate)

    return {
        "candidate_companies": valid_candidates,
        "duplicates_avoided": state.get("duplicates_avoided", 0) + duplicates,
    }


async def hitl_review_node(state: PlatformState) -> dict:
    """Pause point for Human-in-the-Loop. Graph interrupted before this node."""
    return {"hitl_required": False}


async def feedback_learning_node(state: PlatformState) -> dict:
    """Store seen company domains in Redis for future deduplication."""
    from memory.deduplication import mark_company_seen

    for brief in state.get("business_briefs", []):
        domain = brief.get("company_domain", "")
        name = brief.get("company_name", "")
        if domain:
            await mark_company_seen(domain, company_name=name)
    return {}


def _merge_lists(base: dict, update: dict) -> dict:
    """Merge two state dicts, concatenating list fields instead of overwriting."""
    result = dict(base)
    for key, value in update.items():
        if key in result and isinstance(result[key], list) and isinstance(value, list):
            result[key] = result[key] + value
        else:
            result[key] = value
    return result


def get_platform_graph():
    """
    Build and return the LangGraph executable.

    Topology:
      planner -> agent_architect -> deduplication_check -> dag_executor
      -> hitl_review -> feedback_learning
    """
    global _graph
    if _graph is not None:
        return _graph

    graph = StateGraph(PlatformState)
    graph.add_node("planner", planner_node)
    graph.add_node("agent_architect", agent_architect_node)
    graph.add_node("deduplication_check", deduplication_check_node)
    graph.add_node("dag_executor", dag_executor_node)
    graph.add_node("hitl_review", hitl_review_node)
    graph.add_node("feedback_learning", feedback_learning_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "agent_architect")
    graph.add_edge("agent_architect", "deduplication_check")
    graph.add_edge("deduplication_check", "dag_executor")

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

    _graph = graph.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["hitl_review"],
    )

    print("[GRAPH] Platform graph compiled - dynamic DAG executor active")
    return _graph


def route_after_hitl(state: PlatformState) -> str:
    """Route back to planner if custom research requested, else finish."""
    if state.get("hitl_action") == "request_research":
        return "planner"
    return "feedback_learning"
