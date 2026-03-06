"""
System prompt schemas.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class SystemPromptCreate(BaseModel):
    """Schema for creating a system prompt."""
    prompt_type: str = Field(..., pattern="^(chat_panel|ai_cell)$")
    label: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    mode_name: Optional[str] = Field(None, max_length=50)
    tools: Optional[List[str]] = None


class SystemPromptUpdate(BaseModel):
    """Schema for updating a system prompt."""
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    content: Optional[str] = Field(None, min_length=1)
    mode_name: Optional[str] = Field(None, max_length=50)
    tools: Optional[List[str]] = None


class SystemPromptResponse(BaseModel):
    """Schema for system prompt response."""
    id: str
    prompt_type: str
    label: str
    content: str
    mode_name: Optional[str] = None
    tools: Optional[List[str]] = None
    is_active: bool
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AICellModeResponse(BaseModel):
    """Public response for available AI Cell modes."""
    mode_name: str
    label: str


# --- Tool Catalog schemas ---

class ToolCatalogItem(BaseModel):
    """Single tool in the catalog."""
    name: str
    category: str
    description: Optional[str] = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class ToolCatalogGroup(BaseModel):
    """Grouped tools for the admin UI."""
    category: str
    tools: List[ToolCatalogItem]


class ToolCatalogCreate(BaseModel):
    """Schema for adding a tool to the catalog."""
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)


class ToolCatalogUpdate(BaseModel):
    """Schema for updating a tool in the catalog."""
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
