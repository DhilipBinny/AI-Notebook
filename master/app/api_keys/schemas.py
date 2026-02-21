"""
API key Pydantic schemas.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class ApiKeyCreate(BaseModel):
    """Schema for creating/updating an API key."""
    provider: str = Field(..., pattern="^(openai|anthropic|gemini|ollama)$")
    api_key: str = Field(..., min_length=1, max_length=500)
    model_override: Optional[str] = Field(None, max_length=100)


class ApiKeyUpdate(BaseModel):
    """Schema for updating an API key."""
    api_key: Optional[str] = Field(None, min_length=1, max_length=500)
    model_override: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class ApiKeyResponse(BaseModel):
    """Schema for API key response (masked)."""
    id: str
    provider: str
    api_key_hint: str
    model_override: Optional[str] = None
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


class ProviderInfo(BaseModel):
    """Provider availability info."""
    provider: str
    has_key: bool
    is_own_key: bool
    models: List[ProviderModel]
