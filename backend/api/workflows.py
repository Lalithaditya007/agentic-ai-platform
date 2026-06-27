import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from database.models import AsyncSessionLocal, WorkflowRun, Project, ICPConfiguration
from sqlalchemy import select
from datetime import datetime, timezone
from planner.workflow_graph import get_platform_graph

router = APIRouter()


class WorkflowResponse(BaseModel):
    run_id: str
    status: str
    message: str


async def run_workflow_background(run_id: uuid.UUID, project_id: uuid.UUID, icp_config_id: uuid.UUID, icp_data: dict):
    """Background task to execute the workflow."""
    try:
        graph = get_platform_graph()
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
            await manager.send(str(run_id), {
                "type": "node_complete",
                "node": node_name,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        # Update run status when done (or paused)
        state_snapshot = await graph.aget_state(config)
        is_paused = len(state_snapshot.next) > 0
        final_status = "paused_hitl" if is_paused else "completed"
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
            run_record = result.scalar_one_or_none()
            if run_record:
                run_record.status = final_status
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
        
        # Build ICP dict for graph
        icp_data = {
            "industry": icp.industry,
            "company_size": icp.company_size,
            "revenue_range": icp.revenue_range,
            "geography": icp.geography,
            "employee_count_min": icp.employee_count_min,
            "employee_count_max": icp.employee_count_max,
            "personas": icp.personas,
            "triggers": icp.triggers,
            "qualification_rules": icp.qualification_rules,
            "disqualifiers": icp.disqualifiers,
            "constraints": icp.constraints,
        }
        
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
            "completed_at": run_record.completed_at
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
        }
    except Exception:
        return {"run_id": str(run_id), "message": "No graph state found"}
