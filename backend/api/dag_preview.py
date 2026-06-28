"""
DAG Preview API
================
Runs the Planner LLM in "preview mode" for a given project and returns
the complete DAG structure: nodes, edges, metadata.

This is called by the frontend DAG Visualization page to show the user
the unique agentic graph their business description generated.

Routes:
  POST /api/projects/{project_id}/dag-preview   — Run Planner, return DAG JSON
  GET  /api/projects/{project_id}/dag-preview   — Return cached DAG (from workflow run state)
"""

import json
import re
from fastapi import APIRouter, HTTPException
from uuid import UUID
from datetime import datetime, timezone
from pathlib import Path

from database.models import AsyncSessionLocal, ICPConfiguration, Project, WorkflowRun
from sqlalchemy import select

router = APIRouter()


AGENT_TEMPLATE_META = {
    "company_discovery": {
        "icon": "search",
        "color": "#3b82f6",
        "category": "Discovery",
        "description": "Finds companies matching ICP using web search & signals",
    },
    "deduplication": {
        "icon": "filter",
        "color": "#8b5cf6",
        "category": "Quality",
        "description": "Removes duplicate candidates using Redis memory",
    },
    "company_validation": {
        "icon": "check-circle",
        "color": "#10b981",
        "category": "Validation",
        "description": "Validates companies against ICP qualification rules",
    },
    "company_enrichment": {
        "icon": "database",
        "color": "#f59e0b",
        "category": "Enrichment",
        "description": "Enriches company profiles with deep intelligence data",
    },
    "contact_discovery": {
        "icon": "users",
        "color": "#ec4899",
        "category": "Contacts",
        "description": "Discovers decision-maker contacts at target companies",
    },
    "next_best_action": {
        "icon": "zap",
        "color": "#06b6d4",
        "category": "Intelligence",
        "description": "Generates personalized outreach recommendations",
    },
    "business_brief": {
        "icon": "file-text",
        "color": "#84cc16",
        "category": "Output",
        "description": "Creates comprehensive intelligence briefs for review",
    },
    "trigger_monitoring": {
        "icon": "bell",
        "color": "#f97316",
        "category": "Monitoring",
        "description": "Monitors buying signals and trigger events",
    },
    "technology_scout": {
        "icon": "cpu",
        "color": "#a78bfa",
        "category": "Research",
        "description": "Researches technology stack and tools used",
    },
}


def _enrich_node(node: dict) -> dict:
    """Add frontend display metadata to a DAG node."""
    template = node.get("agent_template", "")
    meta = AGENT_TEMPLATE_META.get(template, {
        "icon": "box",
        "color": "#6b7280",
        "category": "Custom",
        "description": node.get("goal", "Custom agent task")[:80],
    })
    return {
        **node,
        "display": {
            "icon": meta["icon"],
            "color": meta["color"],
            "category": meta["category"],
            "description": meta.get("description", node.get("goal", "")[:80]),
            "label": node.get("agent_template", node.get("task_id", "")).replace("_", " ").title(),
        }
    }


def _build_layout_positions(nodes: list, edges: list) -> dict:
    """
    Compute x/y positions for each node using a layered DAG layout.
    Returns {task_id: {x, y, layer}}.
    """
    if not nodes:
        return {}

    # Build predecessor map
    node_ids = [n["task_id"] for n in nodes]
    predecessors = {nid: set() for nid in node_ids}
    for edge in edges:
        frm = edge.get("from", "")
        to = edge.get("to", "")
        if frm in predecessors and to in predecessors:
            predecessors[to].add(frm)

    # Assign layers via longest-path algorithm
    layers = {}
    def get_layer(nid):
        if nid in layers:
            return layers[nid]
        if not predecessors[nid]:
            layers[nid] = 0
        else:
            layers[nid] = max(get_layer(p) for p in predecessors[nid]) + 1
        return layers[nid]

    for nid in node_ids:
        get_layer(nid)

    # Group by layer
    layer_groups = {}
    for nid, layer in layers.items():
        layer_groups.setdefault(layer, []).append(nid)

    # Compute positions — horizontal layers, vertical fan-out
    NODE_W = 220
    NODE_H = 100
    H_GAP = 100   # gap between layers (horizontal)
    V_GAP = 30    # gap between nodes in same layer (vertical)

    positions = {}
    max_layer = max(layers.values()) if layers else 0
    canvas_height = max(len(g) for g in layer_groups.values()) * (NODE_H + V_GAP)

    for layer_idx, group in sorted(layer_groups.items()):
        x = layer_idx * (NODE_W + H_GAP) + 40
        group_h = len(group) * (NODE_H + V_GAP) - V_GAP
        y_start = (canvas_height - group_h) / 2

        for i, nid in enumerate(group):
            positions[nid] = {
                "x": x,
                "y": y_start + i * (NODE_H + V_GAP),
                "layer": layer_idx,
            }

    # Canvas dimensions
    total_w = (max_layer + 1) * (NODE_W + H_GAP) + 40
    total_h = canvas_height + 80

    return {
        "positions": positions,
        "canvas": {"width": max(total_w, 900), "height": max(total_h, 400)},
        "node_dims": {"width": NODE_W, "height": NODE_H},
    }


@router.post("/projects/{project_id}/dag-preview")
async def generate_dag_preview(project_id: UUID):
    """
    Run the Planner LLM for this project's ICP and return a rich DAG
    structure ready for frontend visualization.
    """
    async with AsyncSessionLocal() as db:
        # Verify project exists
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get latest ICP
        icp_res = await db.execute(
            select(ICPConfiguration)
            .where(ICPConfiguration.project_id == project_id)
            .order_by(ICPConfiguration.version.desc())
        )
        icp = icp_res.scalar_one_or_none()
        if not icp:
            raise HTTPException(status_code=400, detail="No ICP configuration found. Please complete ICP setup first.")

    icp_data = {
        "industry": icp.industry or [],
        "company_size": icp.company_size or {},
        "revenue_range": icp.revenue_range or {},
        "geography": icp.geography or [],
        "employee_count_min": icp.employee_count_min,
        "employee_count_max": icp.employee_count_max,
        "personas": icp.personas or [],
        "triggers": icp.triggers or [],
        "qualification_rules": icp.qualification_rules or [],
        "disqualifiers": icp.disqualifiers or [],
        "constraints": icp.constraints or [],
        "_target_market_description": "",
    }

    # Run planner in preview mode
    try:
        from planner.planner_agent import planner_node
        result = await planner_node({
            "project_id": str(project_id),
            "workflow_run_id": "preview",
            "icp_config": icp_data,
            "agent_specs": [],
            "dag_edges": [],
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
            "total_cost_estimate": 0.0,
            "errors": [],
            "warnings": [],
            "current_company_index": 0,
        })
        strategy = result.get("execution_strategy", {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planner failed: {str(e)}")

    dag = strategy.get("dag", {})
    raw_nodes = dag.get("nodes", [])
    raw_edges = dag.get("edges", [])

    # Enrich nodes with display metadata
    enriched_nodes = [_enrich_node(n) for n in raw_nodes]

    # Compute layout positions
    layout = _build_layout_positions(raw_nodes, raw_edges)

    # Attach positions to nodes
    for node in enriched_nodes:
        pos = layout["positions"].get(node["task_id"], {"x": 0, "y": 0, "layer": 0})
        node["position"] = pos

    # Load capability catalogue for display
    try:
        from capabilities.registry import capability_registry
        catalogue = capability_registry.get_catalogue()
        total_caps = len(capability_registry.list_available())
    except Exception:
        catalogue = []
        total_caps = 0

    return {
        "project_id": str(project_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": {
            "name": strategy.get("strategy_name", "Custom Agentic DAG"),
            "rationale": strategy.get("rationale", ""),
            "cost_estimate_usd": strategy.get("cost_estimate_usd", 0.0),
            "targets": strategy.get("targets", {}),
            "hitl_triggers": strategy.get("hitl_triggers", []),
        },
        "dag": {
            "nodes": enriched_nodes,
            "edges": raw_edges,
            "node_count": len(enriched_nodes),
            "edge_count": len(raw_edges),
        },
        "layout": layout,
        "meta": {
            "total_capabilities_available": total_caps,
            "icp_industry": icp.industry or [],
            "icp_geography": icp.geography or [],
            "is_fallback": "Fallback" in strategy.get("strategy_name", ""),
        },
    }


@router.get("/projects/{project_id}/dag-preview")
async def get_dag_from_run(project_id: UUID):
    """
    Return the DAG from the most recent workflow run state (if available).
    Falls back to generating a new preview if no run exists.
    """
    async with AsyncSessionLocal() as db:
        run_res = await db.execute(
            select(WorkflowRun)
            .where(WorkflowRun.project_id == project_id)
            .order_by(WorkflowRun.started_at.desc())
        )
        run = run_res.scalar_one_or_none()

    if run:
        try:
            from planner.workflow_graph import get_platform_graph
            graph = get_platform_graph()
            config = {"configurable": {"thread_id": str(run.id)}}
            state_snapshot = await graph.aget_state(config)
            strategy = state_snapshot.values.get("execution_strategy")
            if strategy:
                dag = strategy.get("dag", {})
                raw_nodes = dag.get("nodes", [])
                raw_edges = dag.get("edges", [])
                enriched_nodes = [_enrich_node(n) for n in raw_nodes]
                layout = _build_layout_positions(raw_nodes, raw_edges)
                for node in enriched_nodes:
                    pos = layout["positions"].get(node["task_id"], {"x": 0, "y": 0, "layer": 0})
                    node["position"] = pos
                return {
                    "project_id": str(project_id),
                    "run_id": str(run.id),
                    "run_status": run.status,
                    "generated_at": run.started_at.isoformat() if run.started_at else None,
                    "strategy": {
                        "name": strategy.get("strategy_name", "Custom Agentic DAG"),
                        "rationale": strategy.get("rationale", ""),
                        "cost_estimate_usd": strategy.get("cost_estimate_usd", 0.0),
                        "targets": strategy.get("targets", {}),
                        "hitl_triggers": strategy.get("hitl_triggers", []),
                    },
                    "dag": {
                        "nodes": enriched_nodes,
                        "edges": raw_edges,
                        "node_count": len(enriched_nodes),
                        "edge_count": len(raw_edges),
                    },
                    "layout": layout,
                    "meta": {
                        "from_live_run": True,
                        "is_fallback": "Fallback" in strategy.get("strategy_name", ""),
                    },
                }
        except Exception:
            pass

    # Fall back to fresh preview
    return await generate_dag_preview(project_id)
