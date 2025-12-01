"""
Project Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class ProjectBase(BaseModel):
    """Base project schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Schema for creating a new project."""
    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_archived: Optional[bool] = None


class PlaygroundStatus(BaseModel):
    """Embedded playground status in project response."""
    id: str
    status: str
    started_at: datetime
    last_activity_at: datetime
    url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectResponse(ProjectBase):
    """Schema for project response."""
    id: str
    user_id: str
    storage_path: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    last_opened_at: Optional[datetime]

    # Nested playground status (if running)
    playground: Optional[PlaygroundStatus] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    """Schema for project list response."""
    projects: List[ProjectResponse]
    total: int
    has_more: bool
