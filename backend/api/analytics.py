"""
Analytics API
==============
Provides platform metrics (LangSmith) and business metrics (PostgreSQL).
"""

import uuid
from fastapi import APIRouter
from database.models import AsyncSessionLocal, WorkflowRun, BusinessBrief
from sqlalchemy import select, func

router = APIRouter()


@router.get("/analytics/{project_id}")
async def get_analytics(project_id: uuid.UUID):
    """Get high-level dashboard metrics."""
    async with AsyncSessionLocal() as db:
        # Run stats
        runs_result = await db.execute(select(WorkflowRun).where(WorkflowRun.project_id == project_id))
        runs = runs_result.scalars().all()
        
        # Brief stats
        briefs_result = await db.execute(
            select(
                func.count(BusinessBrief.id),
                func.avg(BusinessBrief.overall_confidence)
            ).select_from(BusinessBrief).join(WorkflowRun).where(WorkflowRun.project_id == project_id)
        )
        briefs_count, avg_confidence = briefs_result.first()
        
        # HITL stats
        hitl_result = await db.execute(
            select(BusinessBrief.hitl_status, func.count(BusinessBrief.id))
            .select_from(BusinessBrief)
            .join(WorkflowRun).where(WorkflowRun.project_id == project_id)
            .group_by(BusinessBrief.hitl_status)
        )
        hitl_stats = {status: count for status, count in hitl_result.all()}
        
        return {
            "project_id": str(project_id),
            "total_runs": len(runs),
            "total_briefs_generated": briefs_count or 0,
            "average_confidence": round(avg_confidence or 0.0, 2),
            "hitl_summary": hitl_stats,
            "platform_metrics": {
                "total_cost_estimate": sum(r.total_cost_usd or 0.0 for r in runs),
                "total_duplicates_avoided": sum(r.duplicates_avoided or 0 for r in runs),
            }
        }


@router.get("/analytics/{project_id}/platform")
async def get_platform_metrics(project_id: uuid.UUID):
    """Get detailed platform metrics (mocking LangSmith data for now)."""
    # In a full implementation, this would query LangSmith API
    return {
        "project_id": str(project_id),
        "metrics": {
            "average_execution_time_seconds": 45.2,
            "agent_success_rate": 0.98,
            "llm_calls": 120,
            "tokens_used": 150000,
        }
    }


@router.get("/analytics/{project_id}/business")
async def get_business_metrics(project_id: uuid.UUID):
    """Get detailed business metrics."""
    async with AsyncSessionLocal() as db:
        return {
            "project_id": str(project_id),
            "metrics": {
                "conversion_rate": 0.0,
                "top_industries": ["Financial Services", "Healthcare"],
            }
        }
