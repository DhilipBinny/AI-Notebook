"""
System prompt schemas.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class SystemPromptCreate(BaseModel):
    """Schema for creating a system prompt."""
    prompt_type: str = Field(..., pattern="^(chat_panel|ai_cell)$")
    label: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)


class SystemPromptUpdate(BaseModel):
    """Schema for updating a system prompt."""
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    content: Optional[str] = Field(None, min_length=1)


class SystemPromptResponse(BaseModel):
    """Schema for system prompt response."""
    id: str
    prompt_type: str
    label: str
    content: str
    is_active: bool
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
