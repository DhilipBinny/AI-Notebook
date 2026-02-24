"""
LLM Model registry Pydantic schemas.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class LLMModelResponse(BaseModel):
    """Full model info for admin views."""
    id: int
    provider: str
    model_id: str
    display_name: str
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    supports_vision: bool
    supports_function_calling: bool
    supports_streaming: bool
    input_cost_per_1m_cents: int
    output_cost_per_1m_cents: int
    margin_multiplier: float
    is_active: bool
    is_custom: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LLMModelBrief(BaseModel):
    """Brief model info for dropdowns."""
    id: int
    model_id: str
    display_name: str
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    supports_vision: bool
    supports_function_calling: bool

    model_config = ConfigDict(from_attributes=True)


class LLMModelCreate(BaseModel):
    """Schema for creating a model."""
    provider: str = Field(..., max_length=50)
    model_id: str = Field(..., max_length=100)
    display_name: str = Field(..., max_length=150)
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_streaming: bool = True
    input_cost_per_1m_cents: int = 0
    output_cost_per_1m_cents: int = 0
    margin_multiplier: float = 1.30
    is_custom: bool = False
    sort_order: int = 0


class LLMModelUpdate(BaseModel):
    """Schema for updating a model (all fields optional)."""
    model_id: Optional[str] = Field(None, max_length=100)
    display_name: Optional[str] = Field(None, max_length=150)
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    supports_vision: Optional[bool] = None
    supports_function_calling: Optional[bool] = None
    supports_streaming: Optional[bool] = None
    input_cost_per_1m_cents: Optional[int] = None
    output_cost_per_1m_cents: Optional[int] = None
    margin_multiplier: Optional[float] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class LLMModelGroupedResponse(BaseModel):
    """Models grouped by provider."""
    provider: str
    provider_display_name: str
    models: List[LLMModelBrief]
