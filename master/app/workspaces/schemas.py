"""
Workspace Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class WorkspaceBase(BaseModel):
    """Base workspace fields."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: str = Field(default="#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = Field(default="folder", max_length=50)


class WorkspaceCreate(WorkspaceBase):
    """Schema for creating a workspace."""
    pass


class WorkspaceUpdate(BaseModel):
    """Schema for updating a workspace."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = Field(None, max_length=50)
    sort_order: Optional[str] = None


class WorkspaceResponse(WorkspaceBase):
    """Schema for workspace response."""
    id: str
    user_id: str
    is_default: bool
    sort_order: str
    created_at: datetime
    updated_at: datetime
    project_count: int = 0  # Computed field

    class Config:
        from_attributes = True


class WorkspaceWithProjects(WorkspaceResponse):
    """Schema for workspace with nested projects."""
    projects: List["ProjectBrief"] = []


class ProjectBrief(BaseModel):
    """Brief project info for workspace listing."""
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Update forward reference
WorkspaceWithProjects.model_rebuild()
