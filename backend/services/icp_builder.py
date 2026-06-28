"""
ICP Builder Service
====================
Saves generated ICP configuration to PostgreSQL.
Handles versioning — each save creates a new version record.
"""

from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select

from database.models import AsyncSessionLocal, ICPConfiguration, Project


PRIVATE_CONTEXT_FIELD_MAP = {
    "_target_market_description": "target_market_description",
    "_product_or_service": "product_or_service",
    "_value_proposition": "value_proposition",
    "_confidence_notes": "confidence_notes",
}


def serialize_icp_configuration(icp: ICPConfiguration) -> dict:
    """Return a workflow-ready ICP payload including richer business context."""
    return {
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
        "confidence_indicator": icp.confidence_indicator,
        "_target_market_description": icp.target_market_description or "",
        "_product_or_service": icp.product_or_service or "",
        "_value_proposition": icp.value_proposition or "",
        "_confidence_notes": icp.confidence_notes or "",
    }


async def save_icp_config(project_id: UUID, icp_fields: dict, auto_version: bool = True) -> ICPConfiguration:
    """
    Save ICP configuration to the database.

    If a previous version exists, creates a new incremented version.
    If this is the first ICP for the project, creates version 1.

    Args:
        project_id: UUID of the project
        icp_fields: Dict of ICP fields (from extract_icp_fields)
        auto_version: If True, auto-increments version number

    Returns:
        The saved ICPConfiguration ORM object
    """
    async with AsyncSessionLocal() as db:
        # Find current highest version
        result = await db.execute(
            select(ICPConfiguration)
            .where(ICPConfiguration.project_id == project_id)
            .order_by(ICPConfiguration.version.desc())
        )
        current = result.scalar_one_or_none()
        explicit_version = icp_fields.get("version")
        if explicit_version is not None:
            next_version = explicit_version
        elif current and auto_version:
            next_version = current.version + 1
        else:
            next_version = 1

        # Filter out private metadata keys (prefixed with _) and map them to DB columns.
        db_fields = {k: v for k, v in icp_fields.items() if not k.startswith("_")}
        for private_key, model_field in PRIVATE_CONTEXT_FIELD_MAP.items():
            if private_key in icp_fields:
                db_fields[model_field] = icp_fields.get(private_key)

        new_icp = ICPConfiguration(
            project_id=project_id,
            version=next_version,
            **db_fields,
        )
        db.add(new_icp)
        await db.commit()
        await db.refresh(new_icp)
        await _sync_business_context_memory(project_id, new_icp)
        return new_icp


async def confirm_icp(icp_id: UUID) -> ICPConfiguration:
    """
    Mark an ICP configuration as confirmed by the user.
    Sets confirmed_at timestamp.

    Args:
        icp_id: UUID of the ICP configuration

    Returns:
        Updated ICPConfiguration object
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ICPConfiguration).where(ICPConfiguration.id == icp_id)
        )
        icp = result.scalar_one_or_none()
        if not icp:
            raise ValueError(f"ICP configuration {icp_id} not found")

        icp.confirmed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(icp)
        return icp


async def get_latest_icp(project_id: UUID) -> ICPConfiguration | None:
    """
    Retrieve the latest (highest version) ICP for a project.
    Returns None if no ICP exists yet.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ICPConfiguration)
            .where(ICPConfiguration.project_id == project_id)
            .order_by(ICPConfiguration.version.desc())
        )
        return result.scalars().first()


async def get_confirmed_icp(project_id: UUID) -> ICPConfiguration | None:
    """
    Retrieve the most recently confirmed ICP for a project.
    Returns None if no ICP has been confirmed yet.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ICPConfiguration)
            .where(
                ICPConfiguration.project_id == project_id,
                ICPConfiguration.confirmed_at.is_not(None),
            )
            .order_by(ICPConfiguration.version.desc())
        )
        return result.scalars().first()


async def _sync_business_context_memory(project_id: UUID, icp: ICPConfiguration):
    """Persist the richer business context into Chroma for future planning."""
    try:
        from memory.chromadb_client import (
            COLLECTION_BUSINESS_CONTEXT,
            chroma_upsert,
        )

        payload = serialize_icp_configuration(icp)
        document = (
            f"Project {project_id} ICP v{icp.version}. "
            f"Target market: {payload.get('_target_market_description', '')}. "
            f"Product/service: {payload.get('_product_or_service', '')}. "
            f"Value proposition: {payload.get('_value_proposition', '')}. "
            f"Industries: {', '.join(payload.get('industry', []))}. "
            f"Geographies: {', '.join(payload.get('geography', []))}. "
            f"Personas: {', '.join(p.get('title', '') for p in payload.get('personas', []) if isinstance(p, dict))}."
        )
        chroma_upsert(
            collection_name=COLLECTION_BUSINESS_CONTEXT,
            documents=[document],
            ids=[f"{project_id}:icp:{icp.version}"],
            metadatas=[{
                "project_id": str(project_id),
                "version": str(icp.version),
                "confirmed": str(bool(icp.confirmed_at)),
            }],
        )
    except Exception as exc:
        print(f"[ICP_BUILDER] Failed to sync business context memory: {exc}")
