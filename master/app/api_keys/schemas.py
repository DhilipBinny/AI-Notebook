"""
API key Pydantic schemas.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class ApiKeyCreate(BaseModel):
    """Schema for creating/updating an API key."""
    provider: str = Field(..., pattern="^(openai|anthropic|gemini|openai_compatible)$")
    api_key: str = Field(default="", max_length=500)
    model_override: Optional[str] = Field(None, max_length=100)
    base_url: Optional[str] = Field(None, max_length=500)


class ApiKeyUpdate(BaseModel):
    """Schema for updating an API key."""
    api_key: Optional[str] = Field(None, max_length=500)
    model_override: Optional[str] = Field(None, max_length=100)
    base_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class ApiKeyResponse(BaseModel):
    """Schema for API key response (masked)."""
    id: str
    provider: str
    api_key_hint: str
    model_override: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool
    is_validated: bool
    last_validated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProviderModel(BaseModel):
    """Available model for a provider."""
    id: str
    name: str
    display_name: Optional[str] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    supports_vision: Optional[bool] = None
    supports_function_calling: Optional[bool] = None


class ProviderInfo(BaseModel):
    """Provider availability info."""
    provider: str
    display_name: str
    has_key: bool
    is_own_key: bool
    is_default: bool = False
    active_model: Optional[str] = None
    models: List[ProviderModel]
