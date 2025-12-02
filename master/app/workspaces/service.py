"""
Workspace service - business logic for workspace operations.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timezone
import logging

from .models import Workspace
from app.projects.models import Project

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Service class for workspace operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: str, name: str, description: str = None,
                     color: str = "#3B82F6", icon: str = "folder", is_default: bool = False) -> Workspace:
        """
        Create a new workspace.

        Args:
            user_id: Owner user ID
            name: Workspace name
            description: Optional description
            color: Hex color code
            icon: Icon name
            is_default: Whether this is the default workspace

        Returns:
            Created workspace
        """
        # Get max sort_order for user's workspaces
        result = await self.db.execute(
            select(func.max(Workspace.sort_order)).where(
                Workspace.user_id == user_id,
                Workspace.is_deleted == False
            )
        )
        max_order = result.scalar() or "0"
        new_order = str(int(max_order) + 1)

        workspace = Workspace(
            user_id=user_id,
            name=name,
            description=description,
            color=color,
            icon=icon,
            is_default=is_default,
            sort_order=new_order,
        )
        self.db.add(workspace)
        await self.db.flush()
        await self.db.refresh(workspace)
        return workspace

    async def get_by_id(self, workspace_id: str, user_id: str) -> Optional[Workspace]:
        """Get workspace by ID for a specific user."""
        result = await self.db.execute(
            select(Workspace).where(
                Workspace.id == workspace_id,
                Workspace.user_id == user_id,
                Workspace.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def get_default_for_user(self, user_id: str) -> Optional[Workspace]:
        """Get the default workspace for a user."""
        result = await self.db.execute(
            select(Workspace).where(
                Workspace.user_id == user_id,
                Workspace.is_default == True,
                Workspace.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str) -> List[Workspace]:
        """
        List all workspaces for a user (excluding deleted).

        Returns workspaces ordered by sort_order.
        """
        result = await self.db.execute(
            select(Workspace).where(
                Workspace.user_id == user_id,
                Workspace.is_deleted == False
            ).order_by(Workspace.sort_order)
        )
        return list(result.scalars().all())

    async def get_with_project_counts(self, user_id: str) -> List[dict]:
        """
        Get all workspaces for a user with project counts.

        Returns list of dicts with workspace info and project_count.
        """
        workspaces = await self.list_for_user(user_id)
        result = []

        for ws in workspaces:
            # Count non-deleted projects in this workspace
            count_result = await self.db.execute(
                select(func.count(Project.id)).where(
                    Project.workspace_id == ws.id,
                    Project.deleted_at == None
                )
            )
            project_count = count_result.scalar() or 0

            result.append({
                "id": ws.id,
                "user_id": ws.user_id,
                "name": ws.name,
                "description": ws.description,
                "color": ws.color,
                "icon": ws.icon,
                "is_default": ws.is_default,
                "sort_order": ws.sort_order,
                "created_at": ws.created_at,
                "updated_at": ws.updated_at,
                "project_count": project_count,
            })

        # Also count uncategorized projects (no workspace)
        uncategorized_result = await self.db.execute(
            select(func.count(Project.id)).where(
                Project.user_id == user_id,
                Project.workspace_id == None,
                Project.deleted_at == None
            )
        )
        uncategorized_count = uncategorized_result.scalar() or 0

        return result, uncategorized_count

    async def update(self, workspace: Workspace, **kwargs) -> Workspace:
        """
        Update workspace fields.

        Args:
            workspace: Workspace to update
            **kwargs: Fields to update

        Returns:
            Updated workspace
        """
        for key, value in kwargs.items():
            if value is not None and hasattr(workspace, key):
                setattr(workspace, key, value)
        workspace.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(workspace)
        return workspace

    async def soft_delete(self, workspace: Workspace) -> bool:
        """
        Soft delete a workspace and all its projects.

        Args:
            workspace: Workspace to delete

        Returns:
            True if deleted, False if it's the default workspace
        """
        if workspace.is_default:
            return False  # Cannot delete default workspace

        now = datetime.now(timezone.utc)

        # Soft delete the workspace
        workspace.is_deleted = True
        workspace.deleted_at = now

        # Soft delete all projects in this workspace
        result = await self.db.execute(
            select(Project).where(
                Project.workspace_id == workspace.id,
                Project.deleted_at == None
            )
        )
        projects = result.scalars().all()
        for project in projects:
            project.deleted_at = now

        await self.db.flush()
        return True

    async def ensure_default_workspace(self, user_id: str) -> Workspace:
        """
        Ensure user has a default workspace, create if not exists.

        Args:
            user_id: User ID

        Returns:
            Default workspace (existing or newly created)
        """
        default = await self.get_default_for_user(user_id)
        if default:
            return default

        # Create default workspace
        return await self.create(
            user_id=user_id,
            name="My Projects",
            description="Default workspace",
            color="#3B82F6",
            icon="folder",
            is_default=True,
        )

    async def move_project_to_workspace(self, project_id: str, workspace_id: Optional[str], user_id: str) -> bool:
        """
        Move a project to a different workspace.

        Args:
            project_id: Project to move
            workspace_id: Target workspace ID (None for uncategorized)
            user_id: User ID for verification

        Returns:
            True if successful
        """
        # Verify project ownership
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
                Project.deleted_at == None
            )
        )
        project = result.scalar_one_or_none()
        if not project:
            return False

        # Verify workspace ownership if specified
        if workspace_id:
            workspace = await self.get_by_id(workspace_id, user_id)
            if not workspace:
                return False

        project.workspace_id = workspace_id
        project.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True
