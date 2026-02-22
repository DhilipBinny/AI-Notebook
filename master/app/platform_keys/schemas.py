"""
Platform API key schemas.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime


class PlatformKeyCreate(BaseModel):
    """Schema for creating a platform API key."""
    provider: str = Field(..., pattern="^(openai|anthropic|gemini|openai_compatible)$")
    label: str = Field(..., min_length=1, max_length=100)
    api_key: str = Field(default="", max_length=500)
    auth_type: Literal["api_key", "oauth_token"] = "api_key"
    model_name: Optional[str] = Field(None, max_length=100)
    base_url: Optional[str] = Field(None, max_length=500)


class PlatformKeyUpdate(BaseModel):
    """Schema for updating a platform API key."""
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    api_key: Optional[str] = Field(None, max_length=500)
    auth_type: Optional[Literal["api_key", "oauth_token"]] = None
    model_name: Optional[str] = Field(None, max_length=100)
    base_url: Optional[str] = Field(None, max_length=500)


class PlatformKeyResponse(BaseModel):
    """Schema for platform API key response (masked key)."""
    id: str
    provider: str
    label: str
    api_key_hint: str
    auth_type: str = "api_key"
    model_name: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool
    is_default: bool
    priority: int
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_created: bool = False  # True when a new model was auto-registered in the model registry

    model_config = ConfigDict(from_attributes=True)
