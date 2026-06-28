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
        next_version = (current.version + 1) if (current and auto_version) else 1

        # Filter out private metadata keys (prefixed with _)
        db_fields = {k: v for k, v in icp_fields.items() if not k.startswith("_")}

        new_icp = ICPConfiguration(
            project_id=project_id,
            version=next_version,
            **db_fields,
        )
        db.add(new_icp)
        await db.commit()
        await db.refresh(new_icp)
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
