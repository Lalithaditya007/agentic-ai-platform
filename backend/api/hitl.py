"""
Human-in-the-Loop (HITL) API
=============================
Handles all 6 HITL actions (Approve, Reject, Modify, Personas, ICP, Research).
"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from database.models import AsyncSessionLocal, BusinessBrief, WorkflowRun, Project
from sqlalchemy import select, update
from planner.workflow_graph import get_platform_graph

router = APIRouter()


class HITLActionRequest(BaseModel):
    action: str  # approve, reject, modify, change_personas, update_icp, request_research
    details: dict = {}  # E.g., rejection_reason, research_query, modified_fields


async def resume_workflow(run_id: str, action: str, details: dict):
    """Resume the LangGraph workflow after HITL action."""
    graph = get_platform_graph()
    config = {"configurable": {"thread_id": run_id}}
    
    # Update the graph state to resolve the pause
    await graph.aupdate_state(
        config, 
        {"hitl_required": False, "hitl_action": action, "hitl_action_details": details}, 
        as_node="hitl_review"
    )
    
    # Resume execution
    async for output in graph.astream(None, config=config):
        pass
        
    # Check if finished
    state_snapshot = await graph.aget_state(config)
    is_paused = len(state_snapshot.next) > 0
    final_status = "paused_hitl" if is_paused else "completed"
    
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(WorkflowRun).where(WorkflowRun.id == uuid.UUID(run_id))
            .values(status=final_status, completed_at=datetime.now(timezone.utc) if not is_paused else None)
        )
        await db.commit()


@router.get("/hitl/queue")
async def get_hitl_queue():
    """Get all briefs waiting for human review."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(BusinessBrief)
            .where(BusinessBrief.hitl_status.in_(["pending_review", "pending_research"]))
            .order_by(BusinessBrief.created_at.desc())
        )
        briefs = result.scalars().all()
        
        return {
            "queue": [
                {
                    "id": str(b.id),
                    "company_name": b.company_name,
                    "status": b.hitl_status,
                    "overall_confidence": b.overall_confidence,
                    "created_at": b.created_at
                } for b in briefs
            ]
        }


@router.get("/hitl/{brief_id}")
async def get_hitl_brief(brief_id: uuid.UUID):
    """Get a specific brief for HITL review."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(BusinessBrief).where(BusinessBrief.id == brief_id))
        brief = result.scalar_one_or_none()
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")
            
        return {
            "id": str(brief.id),
            "company_name": brief.company_name,
            "company_domain": brief.company_domain,
            "company_summary": brief.company_summary,
            "trigger_summary": brief.trigger_summary,
            "qualification_summary": brief.qualification_summary,
            "company_insights": brief.company_insights,
            "decision_makers": brief.decision_makers,
            "next_best_actions": brief.next_best_actions,
            "priority_score": brief.priority_score,
            "overall_confidence": brief.overall_confidence,
            "hitl_status": brief.hitl_status,
        }


@router.post("/hitl/{brief_id}/action")
async def submit_hitl_action(brief_id: uuid.UUID, request: HITLActionRequest, background_tasks: BackgroundTasks):
    """Process a HITL action on a specific brief."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(BusinessBrief).where(BusinessBrief.id == brief_id))
        brief = result.scalar_one_or_none()
        
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")
            
        if request.action == "approve":
            brief.hitl_status = "approved"
        elif request.action == "reject":
            brief.hitl_status = "rejected"
            # In a full implementation, we'd add the rejection_reason to ChromaDB here
        elif request.action == "modify":
            # Update specific fields
            updates = request.details.get("fields", {})
            for k, v in updates.items():
                if hasattr(brief, k):
                    setattr(brief, k, v)
            brief.hitl_status = "approved" # Modified implies approved
        elif request.action == "request_research":
            brief.hitl_status = "pending_research"
            
        await db.commit()
        
        # Resume the workflow graph in background
        if brief.workflow_run_id:
            background_tasks.add_task(
                resume_workflow, 
                str(brief.workflow_run_id), 
                request.action, 
                request.details
            )
            
        return {"message": f"Action {request.action} processed", "brief_id": str(brief_id)}
