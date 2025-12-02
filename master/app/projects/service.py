"""
Project service layer - business logic for project operations.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional, List, Tuple
from datetime import datetime, timezone

from .models import Project
from .schemas import ProjectCreate, ProjectUpdate
from app.users.models import User


class ProjectService:
    """Service class for project operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, project_id: str, include_playground: bool = False, include_deleted: bool = False) -> Optional[Project]:
        """Get project by ID."""
        query = select(Project).where(Project.id == project_id)

        if not include_deleted:
            query = query.where(Project.deleted_at.is_(None))

        if include_playground:
            query = query.options(selectinload(Project.playground))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_for_user(
        self,
        project_id: str,
        user_id: str,
        include_playground: bool = False,
        include_deleted: bool = False
    ) -> Optional[Project]:
        """Get project by ID, ensuring it belongs to the user."""
        query = select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id
        )

        if not include_deleted:
            query = query.where(Project.deleted_at.is_(None))

        if include_playground:
            query = query.options(selectinload(Project.playground))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: str,
        include_archived: bool = False,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Project], int]:
        """
        List projects for a user.

        Returns:
            Tuple of (projects, total_count)
        """
        # Base query - always filter out soft-deleted unless explicitly included
        query = select(Project).where(Project.user_id == user_id)

        if not include_deleted:
            query = query.where(Project.deleted_at.is_(None))

        if not include_archived:
            query = query.where(Project.is_archived == False)

        # Count total
        count_query = select(func.count(Project.id)).where(Project.user_id == user_id)
        if not include_deleted:
            count_query = count_query.where(Project.deleted_at.is_(None))
        if not include_archived:
            count_query = count_query.where(Project.is_archived == False)

        count_result = await self.db.execute(count_query)
        total = count_result.scalar()

        # Get paginated results
        query = query.options(selectinload(Project.playground))
        query = query.order_by(Project.updated_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        projects = result.scalars().all()

        return list(projects), total

    async def create(self, user: User, project_data: ProjectCreate) -> Project:
        """
        Create a new project.

        Raises:
            ValueError: If user has reached project quota
        """
        # Check quota
        from app.users.service import UserService
        user_service = UserService(self.db)

        if not await user_service.can_create_project(user):
            raise ValueError(f"Project limit reached ({user.max_projects} max)")

        # Generate storage month (mm-yyyy format)
        storage_month = Project.generate_storage_month()

        # Create project
        project = Project(
            user_id=user.id,
            name=project_data.name,
            description=project_data.description,
            workspace_id=project_data.workspace_id,  # Optional workspace
            storage_month=storage_month,
            storage_path="",  # Will be set after we have project ID
        )

        self.db.add(project)
        await self.db.flush()

        # Update storage path with actual project ID: {mm-yyyy}/{project_id}/notebook.ipynb
        project.storage_path = f"{storage_month}/{project.id}/notebook.ipynb"
        await self.db.flush()

        # Refresh to get server-generated values (created_at, updated_at) and relationships
        await self.db.refresh(project, ["playground"])

        return project

    async def update(self, project: Project, project_data: ProjectUpdate) -> Project:
        """Update project details."""
        update_data = project_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(project, field, value)

        await self.db.flush()
        return project

    async def update_last_opened(self, project: Project) -> None:
        """Update project's last opened timestamp."""
        project.last_opened_at = datetime.utcnow()
        await self.db.flush()

    async def archive(self, project: Project) -> Project:
        """Archive a project (soft delete)."""
        project.is_archived = True
        await self.db.flush()
        return project

    async def unarchive(self, project: Project) -> Project:
        """Unarchive a project."""
        project.is_archived = False
        await self.db.flush()
        return project

    async def soft_delete(self, project: Project) -> Project:
        """Soft delete a project by setting deleted_at timestamp."""
        project.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        return project

    async def restore(self, project: Project) -> Project:
        """Restore a soft-deleted project."""
        project.deleted_at = None
        await self.db.flush()
        return project

    async def delete(self, project: Project) -> None:
        """Permanently delete a project (hard delete)."""
        await self.db.delete(project)
        await self.db.flush()

    def _generate_project_id(self) -> str:
        """Generate a temporary project ID (replaced after creation)."""
        from uuid import uuid4
        return str(uuid4())
