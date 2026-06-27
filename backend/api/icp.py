"""
ICP API Routes
===============
Handles:
  POST /api/projects/{project_id}/understand  — LLM business understanding → generate ICP
  GET  /api/projects/{project_id}/icp         — Get latest ICP config
  PUT  /api/projects/{project_id}/icp         — Update ICP (creates new version)
  POST /api/projects/{project_id}/icp/confirm — Confirm ICP (marks as approved)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import UUID
from database.models import AsyncSessionLocal, ICPConfiguration
from sqlalchemy import select

router = APIRouter()


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class BusinessUnderstandingRequest(BaseModel):
    business_description: str


class ICPResponse(BaseModel):
    id: str
    project_id: str
    version: int
    industry: list | None = None
    company_size: dict | None = None
    revenue_range: dict | None = None
    geography: list | None = None
    employee_count_min: int | None = None
    employee_count_max: int | None = None
    personas: list | None = None
    triggers: list | None = None
    qualification_rules: list | None = None
    disqualifiers: list | None = None
    constraints: list | None = None
    confidence_indicator: float | None = None
    confirmed_at: str | None = None
    created_at: str | None = None


def _icp_to_response(icp: ICPConfiguration) -> dict:
    return {
        "id": str(icp.id),
        "project_id": str(icp.project_id),
        "version": icp.version,
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
        "confidence_indicator": icp.confidence_indicator,
        "confirmed_at": icp.confirmed_at.isoformat() if icp.confirmed_at else None,
        "created_at": icp.created_at.isoformat() if icp.created_at else None,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/understand")
async def understand_business_endpoint(project_id: UUID, body: BusinessUnderstandingRequest):
    """
    Phase 2.1: Run the Business Understanding AI on a business description.
    Generates a structured ICP and saves it as a new version.
    Returns both the raw LLM analysis and the saved ICP config.
    """
    from database.models import AsyncSessionLocal, Project
    from sqlalchemy import select

    # Verify project exists
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    try:
        from services.business_understanding import generate_icp_from_description
        full_parsed, icp_fields = await generate_icp_from_description(
            body.business_description
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Save ICP to DB
    try:
        from services.icp_builder import save_icp_config
        saved_icp = await save_icp_config(project_id, icp_fields)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save ICP: {e}")

    return {
        "status": "success",
        "message": "Business understanding complete. ICP generated and saved.",
        "icp": _icp_to_response(saved_icp),
        "analysis": {
            "target_market_description": icp_fields.get("_target_market_description", ""),
            "product_or_service": icp_fields.get("_product_or_service", ""),
            "value_proposition": icp_fields.get("_value_proposition", ""),
            "confidence_notes": icp_fields.get("_confidence_notes", ""),
        },
    }


@router.get("/projects/{project_id}/icp")
async def get_icp(project_id: UUID):
    """Get the latest ICP configuration for a project."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ICPConfiguration)
            .where(ICPConfiguration.project_id == project_id)
            .order_by(ICPConfiguration.version.desc())
        )
        icp = result.scalar_one_or_none()
        if not icp:
            raise HTTPException(status_code=404, detail="No ICP configuration found")
        return _icp_to_response(icp)


@router.put("/projects/{project_id}/icp")
async def update_icp(project_id: UUID, body: dict):
    """
    Update ICP — creates a new versioned record.
    Used when the user edits the ICP in the Review UI.
    """
    async with AsyncSessionLocal() as db:
        # Find current version
        result = await db.execute(
            select(ICPConfiguration)
            .where(ICPConfiguration.project_id == project_id)
            .order_by(ICPConfiguration.version.desc())
        )
        current = result.scalar_one_or_none()
        next_version = (current.version + 1) if current else 1

        # Only allow known ICP fields
        allowed_fields = {
            "industry", "company_size", "revenue_range", "geography",
            "employee_count_min", "employee_count_max", "personas",
            "triggers", "qualification_rules", "disqualifiers",
            "constraints", "confidence_indicator",
        }
        filtered = {k: v for k, v in body.items() if k in allowed_fields}

        new_icp = ICPConfiguration(
            project_id=project_id,
            version=next_version,
            **filtered,
        )
        db.add(new_icp)
        await db.commit()
        await db.refresh(new_icp)
        return {
            "id": str(new_icp.id),
            "version": new_icp.version,
            "message": "ICP updated — new version created",
        }


@router.post("/projects/{project_id}/icp/confirm")
async def confirm_icp(project_id: UUID):
    """
    Confirm the current ICP — marks it as approved by the user.
    This is the "Confirm & Start Monitoring" action from the Review UI.
    """
    from services.icp_builder import get_latest_icp, confirm_icp as confirm_icp_service

    icp = await get_latest_icp(project_id)
    if not icp:
        raise HTTPException(status_code=404, detail="No ICP found for this project")

    confirmed = await confirm_icp_service(icp.id)
    return {
        "status": "confirmed",
        "message": "ICP confirmed. Monitoring will begin shortly.",
        "icp_id": str(confirmed.id),
        "version": confirmed.version,
        "confirmed_at": confirmed.confirmed_at.isoformat(),
    }


@router.get("/projects/{project_id}/icp/history")
async def get_icp_history(project_id: UUID):
    """Get all ICP versions for a project (for audit trail)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ICPConfiguration)
            .where(ICPConfiguration.project_id == project_id)
            .order_by(ICPConfiguration.version.desc())
        )
        icps = result.scalars().all()
        return [_icp_to_response(icp) for icp in icps]
