"""
Project API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_active_user
from app.users.models import User
from .models import Project
from .schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
)
from .service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    include_archived: bool = Query(False, description="Include archived projects"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all projects for the current user.
    """
    project_service = ProjectService(db)
    projects, total = await project_service.list_for_user(
        user_id=current_user.id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )

    # Convert to response with playground URL
    project_responses = []
    for project in projects:
        response = ProjectResponse.model_validate(project)
        if project.playground and project.playground.status.value == "running":
            response.playground.url = f"/playground/{project.playground.container_name}"
        project_responses.append(response)

    return ProjectListResponse(
        projects=project_responses,
        total=total,
        has_more=(offset + len(projects)) < total,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new project.

    Will fail if user has reached their project quota.
    """
    project_service = ProjectService(db)

    try:
        project = await project_service.create(current_user, request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific project.
    """
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(
        project_id=project_id,
        user_id=current_user.id,
        include_playground=True,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    response = ProjectResponse.model_validate(project)
    if project.playground and project.playground.status.value == "running":
        response.playground.url = f"/playground/{project.playground.container_name}"

    return response


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: ProjectUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a project.
    """
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(
        project_id=project_id,
        user_id=current_user.id,
        include_playground=True,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    updated = await project_service.update(project, request)

    # Reload with playground for response
    updated = await project_service.get_by_id_for_user(
        project_id=project_id,
        user_id=current_user.id,
        include_playground=True,
    )

    response = ProjectResponse.model_validate(updated)
    if updated.playground and updated.playground.status.value == "running":
        response.playground.url = f"/playground/{updated.playground.container_name}"

    return response


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete a project.

    The project will be marked as deleted but data is preserved in the database.
    """
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(
        project_id=project_id,
        user_id=current_user.id,
        include_playground=True,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Soft delete - just mark as deleted, preserve data
    await project_service.soft_delete(project)


