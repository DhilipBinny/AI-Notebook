"""
Workspace API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.session import get_db
from app.auth.dependencies import get_current_active_user
from app.users.models import User
from .service import WorkspaceService
from .schemas import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
)

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.get("", response_model=dict)
async def list_workspaces(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all workspaces for the current user.

    Returns workspaces with project counts.
    """
    workspace_service = WorkspaceService(db)

    # Ensure user has a default workspace
    await workspace_service.ensure_default_workspace(current_user.id)

    # Get workspaces with counts
    workspaces, uncategorized_count = await workspace_service.get_with_project_counts(current_user.id)

    return {
        "workspaces": workspaces,
        "uncategorized_count": uncategorized_count,
    }


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: WorkspaceCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new workspace.
    """
    workspace_service = WorkspaceService(db)

    workspace = await workspace_service.create(
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon,
        is_default=False,
    )

    # Get project count (will be 0 for new workspace)
    return WorkspaceResponse(
        id=workspace.id,
        user_id=workspace.user_id,
        name=workspace.name,
        description=workspace.description,
        color=workspace.color,
        icon=workspace.icon,
        is_default=workspace.is_default,
        sort_order=workspace.sort_order,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        project_count=0,
    )


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a workspace by ID.
    """
    workspace_service = WorkspaceService(db)
    workspace = await workspace_service.get_by_id(workspace_id, current_user.id)

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Get project count
    workspaces, _ = await workspace_service.get_with_project_counts(current_user.id)
    project_count = next((w["project_count"] for w in workspaces if w["id"] == workspace_id), 0)

    return WorkspaceResponse(
        id=workspace.id,
        user_id=workspace.user_id,
        name=workspace.name,
        description=workspace.description,
        color=workspace.color,
        icon=workspace.icon,
        is_default=workspace.is_default,
        sort_order=workspace.sort_order,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        project_count=project_count,
    )


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    request: WorkspaceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a workspace.
    """
    workspace_service = WorkspaceService(db)
    workspace = await workspace_service.get_by_id(workspace_id, current_user.id)

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Update workspace
    workspace = await workspace_service.update(
        workspace,
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon,
        sort_order=request.sort_order,
    )

    # Get project count
    workspaces, _ = await workspace_service.get_with_project_counts(current_user.id)
    project_count = next((w["project_count"] for w in workspaces if w["id"] == workspace_id), 0)

    return WorkspaceResponse(
        id=workspace.id,
        user_id=workspace.user_id,
        name=workspace.name,
        description=workspace.description,
        color=workspace.color,
        icon=workspace.icon,
        is_default=workspace.is_default,
        sort_order=workspace.sort_order,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        project_count=project_count,
    )


@router.delete("/{workspace_id}", status_code=status.HTTP_200_OK)
async def delete_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete a workspace and all its projects.

    Cannot delete the default workspace.
    """
    workspace_service = WorkspaceService(db)
    workspace = await workspace_service.get_by_id(workspace_id, current_user.id)

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    if workspace.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default workspace",
        )

    success = await workspace_service.soft_delete(workspace)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete workspace",
        )

    return {"message": "Workspace and projects deleted successfully"}


@router.post("/{workspace_id}/projects/{project_id}", status_code=status.HTTP_200_OK)
async def move_project_to_workspace(
    workspace_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Move a project to a workspace.
    """
    workspace_service = WorkspaceService(db)

    # Verify workspace exists
    workspace = await workspace_service.get_by_id(workspace_id, current_user.id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    success = await workspace_service.move_project_to_workspace(
        project_id=project_id,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to move project",
        )

    return {"message": "Project moved successfully"}


@router.delete("/{workspace_id}/projects/{project_id}", status_code=status.HTTP_200_OK)
async def remove_project_from_workspace(
    workspace_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a project from a workspace (makes it uncategorized).
    """
    workspace_service = WorkspaceService(db)

    success = await workspace_service.move_project_to_workspace(
        project_id=project_id,
        workspace_id=None,  # Remove from workspace
        user_id=current_user.id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to remove project from workspace",
        )

    return {"message": "Project removed from workspace"}
