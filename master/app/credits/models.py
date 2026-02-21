"""
Credit and usage tracking database models.
"""

from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Enum as SQLEnum, DECIMAL, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from uuid import uuid4

from app.db.base import Base


class UserCredit(Base):
    """User credit balance. One row per user."""

    __tablename__ = "user_credits"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    balance_cents = Column(Integer, default=1000, nullable=False)  # $10.00
    total_deposited_cents = Column(Integer, default=1000, nullable=False)
    total_consumed_cents = Column(Integer, default=0, nullable=False)
    last_charged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="credits")

    def __repr__(self) -> str:
        return f"<UserCredit user={self.user_id} balance=${self.balance_cents/100:.2f}>"


class RequestType(str, enum.Enum):
    CHAT = "chat"
    AI_CELL = "ai_cell"
    SUMMARIZE = "summarize"


class LLMPricing(Base):
    """Per-model pricing with configurable margin."""

    __tablename__ = "llm_pricing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    input_cost_per_1m_cents = Column(Integer, nullable=False)
    output_cost_per_1m_cents = Column(Integer, nullable=False)
    margin_multiplier = Column(DECIMAL(3, 2), default=1.30, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<LLMPricing {self.provider}/{self.model}>"


class UsageRecord(Base):
    """Per-request LLM usage tracking."""

    __tablename__ = "usage_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), nullable=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    request_type = Column(
        SQLEnum(RequestType, values_callable=lambda obj: [e.value for e in obj]),
        default=RequestType.CHAT,
        nullable=False
    )
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    cached_tokens = Column(Integer, default=0, nullable=False)
    cost_cents = Column(Integer, default=0, nullable=False)
    raw_cost_cents = Column(Integer, default=0, nullable=False)
    is_own_key = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<UsageRecord {self.provider}/{self.model} ${self.cost_cents/100:.4f}>"
