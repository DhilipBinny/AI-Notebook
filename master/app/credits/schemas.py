"""
Credit and usage Pydantic schemas.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class CreditBalanceResponse(BaseModel):
    """User credit balance response."""
    user_id: str
    balance_cents: int
    balance_dollars: float
    total_deposited_cents: int
    total_consumed_cents: int
    last_charged_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UsageRecordResponse(BaseModel):
    """Usage record response."""
    id: int
    provider: str
    model: str
    request_type: str
    input_tokens: int
    output_tokens: int
    cost_cents: int
    is_own_key: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UsageHistoryResponse(BaseModel):
    """Paginated usage history."""
    records: List[UsageRecordResponse]
    total: int
    page: int
    page_size: int


class LLMPricingResponse(BaseModel):
    """LLM pricing response."""
    id: int
    provider: str
    model: str
    input_cost_per_1m_cents: int
    output_cost_per_1m_cents: int
    margin_multiplier: float
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class AdminCreditAdjust(BaseModel):
    """Admin credit adjustment request."""
    user_id: str
    amount_cents: int = Field(..., description="Positive to add, negative to deduct")
    reason: str = Field(..., max_length=500)


class AdminPricingUpdate(BaseModel):
    """Admin pricing update request."""
    provider: str
    model: str
    input_cost_per_1m_cents: Optional[int] = None
    output_cost_per_1m_cents: Optional[int] = None
    margin_multiplier: Optional[float] = None
    is_active: Optional[bool] = None


class UsageReport(BaseModel):
    """Usage report from playground (internal)."""
    user_id: str
    project_id: Optional[str] = None
    provider: str
    model: str
    request_type: str = "chat"
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    is_own_key: bool = False
