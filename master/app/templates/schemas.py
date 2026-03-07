"""
Notebook template Pydantic schemas.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class TemplateCreate(BaseModel):
    """Create a new template."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    difficulty_level: str = Field(default="beginner")
    estimated_minutes: Optional[int] = None
    tags: Optional[List[str]] = None
    is_public: bool = False
    sort_order: int = 0


class TemplateUpdate(BaseModel):
    """Update a template."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    difficulty_level: Optional[str] = None
    estimated_minutes: Optional[int] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    sort_order: Optional[int] = None
    thumbnail_url: Optional[str] = None


class TemplateResponse(BaseModel):
    """Template response."""
    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    thumbnail_url: Optional[str] = None
    difficulty_level: str
    estimated_minutes: Optional[int] = None
    tags: Optional[List[str]] = None
    is_public: bool
    created_by: Optional[str] = None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TemplateForkRequest(BaseModel):
    """Request to fork a template to a new project."""
    name: Optional[str] = None


class TemplateForkResponse(BaseModel):
    """Response after forking a template."""
    project_id: str
    project_name: str
    message: str


class TemplateFromProjectRequest(BaseModel):
    """Create template from existing project."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    difficulty_level: str = Field(default="beginner")
    estimated_minutes: Optional[int] = None
    tags: Optional[List[str]] = None
    is_public: bool = False


class TemplateNotebookCell(BaseModel):
    """A single notebook cell."""
    cell_type: str = Field(..., pattern=r"^(code|markdown)$")
    source: str
    metadata: Optional[dict] = None
    outputs: Optional[List[dict]] = None
    execution_count: Optional[int] = None


class TemplateNotebookUpdate(BaseModel):
    """Update notebook content for a template."""
    cells: List[TemplateNotebookCell]
