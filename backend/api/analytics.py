"""
Analytics API
==============
Provides project-scoped platform and business metrics using persisted workflow,
company, contact, and brief records.
"""

import uuid
from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from database.models import AsyncSessionLocal, WorkflowRun, BusinessBrief
from sqlalchemy import select, func

router = APIRouter()


def _safe_ratio(numerator: int, denominator: int) -> float:
    return round((numerator / denominator), 3) if denominator else 0.0


async def _compute_analytics(project_id: uuid.UUID) -> dict:
    async with AsyncSessionLocal() as db:
        runs = (
            await db.execute(
                select(WorkflowRun).where(WorkflowRun.project_id == project_id).order_by(WorkflowRun.created_at.desc())
            )
        ).scalars().all()

        briefs_count, avg_confidence = (
            await db.execute(
                select(func.count(BusinessBrief.id), func.avg(BusinessBrief.overall_confidence))
                .select_from(BusinessBrief)
                .join(WorkflowRun, BusinessBrief.workflow_run_id == WorkflowRun.id)
                .where(WorkflowRun.project_id == project_id)
            )
        ).first()

        hitl_rows = (
            await db.execute(
                select(BusinessBrief.hitl_status, func.count(BusinessBrief.id))
                .select_from(BusinessBrief)
                .join(WorkflowRun, BusinessBrief.workflow_run_id == WorkflowRun.id)
                .where(WorkflowRun.project_id == project_id)
                .group_by(BusinessBrief.hitl_status)
            )
        ).all()
        hitl_summary = {status: count for status, count in hitl_rows}

        brief_rows = (
            await db.execute(
                select(BusinessBrief)
                .join(WorkflowRun, BusinessBrief.workflow_run_id == WorkflowRun.id)
                .where(WorkflowRun.project_id == project_id)
            )
        ).scalars().all()

        total_duplicates_avoided = 0
        total_memory_hits = 0
        total_agent_success = 0
        total_agent_attempts = 0
        total_execution_seconds = 0.0
        completed_runs = 0
        planner_strategies = []
        companies_count = 0
        validated_count = 0
        enriched_count = 0
        contacts_count = 0
        email_count = 0
        phone_count = 0
        linkedin_count = 0

        for run in runs:
            if run.planner_strategy:
                planner_strategies.append(run.planner_strategy.get("strategy_name"))

            if run.started_at and run.completed_at:
                total_execution_seconds += max((run.completed_at - run.started_at).total_seconds(), 0.0)
                completed_runs += 1

            exec_log = run.agent_execution_log or {}
            total_duplicates_avoided += exec_log.get("duplicates_avoided", 0) or 0
            total_memory_hits += exec_log.get("memory_hits", 0) or 0
            companies_count += exec_log.get("candidate_companies_count", 0) or 0
            validated_count += exec_log.get("validated_companies_count", 0) or 0
            enriched_count += exec_log.get("enriched_companies_count", 0) or 0
            contacts_count += exec_log.get("contacts_count", 0) or 0

            for metric in exec_log.get("agent_metrics", []) or []:
                total_agent_attempts += 1
                if metric.get("status") == "success":
                    total_agent_success += 1

        for brief in brief_rows:
            for dm in brief.decision_makers or []:
                if dm.get("email") and dm.get("email") != "unavailable":
                    email_count += 1
                if dm.get("phone") and dm.get("phone") != "unavailable":
                    phone_count += 1
                if dm.get("linkedin_url") and dm.get("linkedin_url") != "unavailable":
                    linkedin_count += 1

        return {
            "project_id": str(project_id),
            "total_runs": len(runs),
            "total_briefs_generated": briefs_count or 0,
            "average_confidence": round(avg_confidence or 0.0, 3),
            "hitl_summary": hitl_summary,
            "platform_metrics": {
                "total_cost_estimate": round(sum((r.total_cost_estimate or 0.0) for r in runs), 3),
                "total_duplicates_avoided": total_duplicates_avoided,
                "memory_hit_rate": _safe_ratio(total_memory_hits, max(companies_count, 1)),
                "average_execution_time_seconds": round(total_execution_seconds / completed_runs, 2) if completed_runs else 0.0,
                "agent_success_rate": _safe_ratio(total_agent_success, total_agent_attempts),
            },
            "business_metrics": {
                "companies_discovered": companies_count,
                "companies_qualified": validated_count,
                "companies_enriched": enriched_count,
                "contacts_discovered": contacts_count,
                "email_coverage": _safe_ratio(email_count, contacts_count),
                "phone_coverage": _safe_ratio(phone_count, contacts_count),
                "linkedin_coverage": _safe_ratio(linkedin_count, contacts_count),
            },
            "recent_strategies": [s for s in planner_strategies[:5] if s],
        }


@router.get("/analytics/{project_id}")
async def get_analytics(project_id: uuid.UUID):
    """Return high-level analytics used by the dashboard."""
    payload = await _compute_analytics(project_id)
    return JSONResponse(content=jsonable_encoder(payload))


@router.get("/analytics/{project_id}/platform")
async def get_platform_metrics(project_id: uuid.UUID):
    """Return the platform_metrics slice."""
    analytics = await _compute_analytics(project_id)
    payload = {
        "project_id": str(project_id),
        "metrics": analytics["platform_metrics"],
        "recent_strategies": analytics["recent_strategies"],
    }
    return JSONResponse(content=jsonable_encoder(payload))


@router.get("/analytics/{project_id}/business")
async def get_business_metrics(project_id: uuid.UUID):
    """Return the business_metrics slice."""
    analytics = await _compute_analytics(project_id)
    payload = {
        "project_id": str(project_id),
        "metrics": analytics["business_metrics"],
        "hitl_summary": analytics["hitl_summary"],
    }
    return JSONResponse(content=jsonable_encoder(payload))
