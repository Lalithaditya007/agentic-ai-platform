import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from database.models import AsyncSessionLocal, WorkflowRun, Project, ICPConfiguration
from sqlalchemy import select
from datetime import datetime, timezone
from planner.workflow_graph import get_platform_graph
from services.icp_builder import serialize_icp_configuration

router = APIRouter()


class WorkflowResponse(BaseModel):
    run_id: str
    status: str
    message: str


async def run_workflow_background(run_id: uuid.UUID, project_id: uuid.UUID, icp_config_id: uuid.UUID, icp_data: dict):
    """Background task to execute the workflow."""
    try:
        graph = get_platform_graph()
        execution_events = []
        initial_state = {
            "project_id": str(project_id),
            "workflow_run_id": str(run_id),
            "icp_config": icp_data,
            "candidate_companies": [],
            "validated_companies": [],
            "enriched_companies": [],
            "discovered_contacts": [],
            "business_briefs": [],
            "agent_metrics": [],
            "errors": [],
            "warnings": [],
            "hitl_required": False,
            "memory_hits": 0,
            "duplicates_avoided": 0,
        }
        
        from api.ws import manager
        
        # Invoke LangGraph
        config = {"configurable": {"thread_id": str(run_id)}}
        
        # We use ainvoke for async execution
        # Note: LangGraph might pause at hitl_review node
        async for output in graph.astream(initial_state, config=config):
            node_name = list(output.keys())[0] if output else "unknown"
            execution_events.append({
                "node": node_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await manager.send(str(run_id), {
                "type": "node_complete",
                "node": node_name,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        # Update run status when done (or paused)
        state_snapshot = await graph.aget_state(config)
        is_paused = len(state_snapshot.next) > 0
        final_status = "paused_hitl" if is_paused else "completed"
        final_state = state_snapshot.values or {}
        execution_summary = {
            "events": execution_events,
            "agent_metrics": final_state.get("agent_metrics", []),
            "errors": final_state.get("errors", []),
            "warnings": final_state.get("warnings", []),
            "duplicates_avoided": final_state.get("duplicates_avoided", 0),
            "memory_hits": final_state.get("memory_hits", 0),
            "candidate_companies_count": len(final_state.get("candidate_companies", []) or []),
            "validated_companies_count": len(final_state.get("validated_companies", []) or []),
            "enriched_companies_count": len(final_state.get("enriched_companies", []) or []),
            "contacts_count": len(final_state.get("discovered_contacts", []) or []),
            "briefs_count": len(final_state.get("business_briefs", []) or []),
        }
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
            run_record = result.scalar_one_or_none()
            if run_record:
                run_record.status = final_status
                run_record.planner_strategy = final_state.get("execution_strategy")
                run_record.agent_execution_log = execution_summary
                run_record.total_cost_estimate = final_state.get("total_cost_estimate", 0.0) or 0.0
                if not is_paused:
                    run_record.completed_at = datetime.now(timezone.utc)
                await db.commit()
                
    except Exception as e:
        print(f"[WORKFLOW] Error in run {run_id}: {e}")
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
            run_record = result.scalar_one_or_none()
            if run_record:
                run_record.status = "failed"
                run_record.agent_execution_log = {
                    "events": [],
                    "errors": [{"workflow": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}],
                }
                await db.commit()


@router.post("/workflows/run")
async def start_workflow(project_id: uuid.UUID, background_tasks: BackgroundTasks):
    """Start a new workflow run for a project."""
    async with AsyncSessionLocal() as db:
        # Get latest ICP config
        result = await db.execute(
            select(ICPConfiguration)
            .where(ICPConfiguration.project_id == project_id)
            .order_by(ICPConfiguration.version.desc())
        )
        icp = result.scalar_one_or_none()
        if not icp:
            raise HTTPException(status_code=400, detail="No ICP configuration found for project")
            
        # Create run record
        new_run = WorkflowRun(
            project_id=project_id,
            icp_config_id=icp.id,
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        db.add(new_run)
        await db.commit()
        await db.refresh(new_run)
        
        # Build ICP dict for graph, preserving richer business-understanding context.
        icp_data = serialize_icp_configuration(icp)
        
        # Trigger background task
        background_tasks.add_task(run_workflow_background, new_run.id, project_id, icp.id, icp_data)
        
        return {"message": "Workflow started", "run_id": str(new_run.id)}


@router.get("/workflows/{run_id}")
async def get_workflow(run_id: uuid.UUID):
    """Get workflow run status."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
        run_record = result.scalar_one_or_none()
        if not run_record:
            raise HTTPException(status_code=404, detail="Run not found")
        return {
            "run_id": str(run_record.id), 
            "status": run_record.status,
            "started_at": run_record.started_at,
            "completed_at": run_record.completed_at,
            "total_cost_estimate": run_record.total_cost_estimate,
            "planner_strategy": run_record.planner_strategy,
        }


@router.get("/workflows/{run_id}/graph")
async def get_workflow_graph(run_id: uuid.UUID):
    """Get execution graph visualization data."""
    # We can fetch state from graph checkpointer
    graph = get_platform_graph()
    config = {"configurable": {"thread_id": str(run_id)}}
    try:
        state_snapshot = await graph.aget_state(config)
        state_values = state_snapshot.values
        return {
            "run_id": str(run_id),
            "next_nodes": state_snapshot.next,
            "strategy": state_values.get("execution_strategy"),
            "agent_specs": state_values.get("agent_specs"),
            "metrics": state_values.get("agent_metrics"),
            "summary": {
                "candidate_companies_count": len(state_values.get("candidate_companies", []) or []),
                "validated_companies_count": len(state_values.get("validated_companies", []) or []),
                "enriched_companies_count": len(state_values.get("enriched_companies", []) or []),
                "contacts_count": len(state_values.get("discovered_contacts", []) or []),
                "briefs_count": len(state_values.get("business_briefs", []) or []),
                "duplicates_avoided": state_values.get("duplicates_avoided", 0),
                "memory_hits": state_values.get("memory_hits", 0),
                "errors": state_values.get("errors", []),
            },
        }
    except Exception:
        return {"run_id": str(run_id), "message": "No graph state found"}
