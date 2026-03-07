"""
Template service - manages notebook templates and fork-to-project.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import json
import logging

from .models import NotebookTemplate, DifficultyLevel
from app.projects.service import ProjectService
from app.projects.schemas import ProjectCreate
from app.notebooks.s3_client import s3_client as notebook_s3_client
from app.users.models import User

logger = logging.getLogger(__name__)

# Default empty notebook for new templates
DEFAULT_NOTEBOOK = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        }
    },
    "cells": [],
}


class TemplateService:
    """Service class for template operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_public(self, category: Optional[str] = None) -> List[NotebookTemplate]:
        """List all public templates, optionally filtered by category."""
        query = select(NotebookTemplate).where(
            NotebookTemplate.is_public == True
        )
        if category:
            query = query.where(NotebookTemplate.category == category)
        query = query.order_by(NotebookTemplate.sort_order, NotebookTemplate.name)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, template_id: str) -> Optional[NotebookTemplate]:
        """Get a template by ID."""
        result = await self.db.execute(
            select(NotebookTemplate).where(NotebookTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        data: dict,
        notebook_data: Optional[dict],
        created_by: str,
    ) -> NotebookTemplate:
        """Create a new template with optional notebook content."""
        try:
            difficulty = DifficultyLevel(data.get("difficulty_level", "beginner"))
        except ValueError:
            difficulty = DifficultyLevel.BEGINNER

        template = NotebookTemplate(
            name=data["name"],
            description=data.get("description"),
            category=data.get("category"),
            difficulty_level=difficulty,
            estimated_minutes=data.get("estimated_minutes"),
            tags=data.get("tags"),
            is_public=data.get("is_public", False),
            sort_order=data.get("sort_order", 0),
            created_by=created_by,
            storage_path="",  # Set after flush to get ID
        )
        self.db.add(template)
        await self.db.flush()

        # Set storage path and save notebook to S3
        template.storage_path = f"templates/{template.id}/notebook.ipynb"
        nb_data = notebook_data or DEFAULT_NOTEBOOK
        await self._save_template_notebook(template.id, nb_data)

        await self.db.flush()
        return template

    async def create_from_project(
        self,
        project_id: str,
        data: dict,
        created_by: str,
    ) -> Optional[NotebookTemplate]:
        """Create a template from an existing project's notebook."""
        project_service = ProjectService(self.db)
        project = await project_service.get_by_id(project_id)
        if not project:
            return None

        # Load project's notebook from S3
        notebook_data = await notebook_s3_client.load_notebook(
            project.storage_month, project_id
        )
        if not notebook_data:
            notebook_data = DEFAULT_NOTEBOOK

        return await self.create(data, notebook_data, created_by)

    async def update(
        self, template_id: str, data: dict
    ) -> Optional[NotebookTemplate]:
        """Update template metadata."""
        template = await self.get_by_id(template_id)
        if not template:
            return None

        if "name" in data and data["name"] is not None:
            template.name = data["name"]
        if "description" in data and data["description"] is not None:
            template.description = data["description"]
        if "category" in data and data["category"] is not None:
            template.category = data["category"]
        if "difficulty_level" in data and data["difficulty_level"] is not None:
            try:
                template.difficulty_level = DifficultyLevel(data["difficulty_level"])
            except ValueError:
                pass
        if "estimated_minutes" in data and data["estimated_minutes"] is not None:
            template.estimated_minutes = data["estimated_minutes"]
        if "tags" in data and data["tags"] is not None:
            template.tags = data["tags"]
        if "is_public" in data and data["is_public"] is not None:
            template.is_public = data["is_public"]
        if "sort_order" in data and data["sort_order"] is not None:
            template.sort_order = data["sort_order"]
        if "thumbnail_url" in data and data["thumbnail_url"] is not None:
            template.thumbnail_url = data["thumbnail_url"]

        await self.db.flush()
        return template

    async def delete(self, template_id: str) -> bool:
        """Delete a template."""
        template = await self.get_by_id(template_id)
        if not template:
            return False

        await self.db.delete(template)
        await self.db.flush()
        return True

    async def fork_to_project(
        self,
        template_id: str,
        user: User,
        project_name: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Fork a template to a new project for the user.

        Creates a new project and copies the template's notebook into it.

        Returns:
            Dict with project_id and project_name, or None if template not found.
        """
        template = await self.get_by_id(template_id)
        if not template:
            return None

        # Load template notebook from S3
        notebook_data = await self._load_template_notebook(template.id)
        if not notebook_data:
            notebook_data = DEFAULT_NOTEBOOK

        # Create a new project for the user
        name = project_name or f"{template.name}"
        project_service = ProjectService(self.db)
        project = await project_service.create(
            user=user,
            project_data=ProjectCreate(
                name=name,
                description=f"Forked from template: {template.name}",
            ),
        )

        # Save the template's notebook to the new project's S3 path
        await notebook_s3_client.save_notebook(
            project.storage_month,
            project.id,
            notebook_data,
            create_version=False,
        )

        logger.info(
            f"Forked template {template.id} to project {project.id} for user {user.id}"
        )

        return {
            "project_id": project.id,
            "project_name": project.name,
        }

    async def get_notebook_content(self, template_id: str) -> Optional[dict]:
        """Load notebook data from the template's S3 path."""
        template = await self.get_by_id(template_id)
        if not template:
            return None
        return await self._load_template_notebook(template_id)

    async def update_notebook_content(
        self, template_id: str, notebook_data: dict
    ) -> bool:
        """Update notebook content for a template."""
        template = await self.get_by_id(template_id)
        if not template:
            return False
        await self._save_template_notebook(template_id, notebook_data)
        return True

    async def _save_template_notebook(
        self, template_id: str, notebook_data: dict
    ) -> None:
        """Save notebook data to the template's S3 path."""
        key = f"templates/{template_id}/notebook.ipynb"
        notebook_json = json.dumps(notebook_data, indent=2)
        notebook_s3_client.client.put_object(
            Bucket=notebook_s3_client.bucket,
            Key=key,
            Body=notebook_json.encode("utf-8"),
            ContentType="application/json",
        )

    async def _load_template_notebook(
        self, template_id: str
    ) -> Optional[dict]:
        """Load notebook data from the template's S3 path."""
        key = f"templates/{template_id}/notebook.ipynb"
        try:
            response = notebook_s3_client.client.get_object(
                Bucket=notebook_s3_client.bucket, Key=key
            )
            content = response["Body"].read().decode("utf-8")
            return json.loads(content)
        except Exception:
            return None
