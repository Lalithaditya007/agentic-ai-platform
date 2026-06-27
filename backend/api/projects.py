from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy import select
from database.models import AsyncSessionLocal, Project

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str
    business_description: str


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    business_description: str
    status: str
    created_at: datetime


@router.post("/projects", response_model=ProjectResponse)
async def create_project(body: CreateProjectRequest):
    """Create a new project from a business description."""
    async with AsyncSessionLocal() as db:
        project = Project(
            name=body.name,
            business_description=body.business_description,
            status="draft",
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return ProjectResponse(
            id=project.id,
            name=project.name,
            business_description=project.business_description,
            status=project.status,
            created_at=project.created_at,
        )


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects():
    """List all projects."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Project).order_by(Project.created_at.desc()))
        projects = result.scalars().all()
        return [
            ProjectResponse(
                id=p.id,
                name=p.name,
                business_description=p.business_description,
                status=p.status,
                created_at=p.created_at,
            )
            for p in projects
        ]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID):
    """Get a project by ID."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return ProjectResponse(
            id=project.id,
            name=project.name,
            business_description=project.business_description,
            status=project.status,
            created_at=project.created_at,
        )
