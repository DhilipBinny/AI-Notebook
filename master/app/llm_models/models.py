"""
LLM Model registry - single source of truth for model identity, capabilities, and pricing.
"""

from sqlalchemy import Column, String, Boolean, Integer, DateTime, DECIMAL, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base import Base


class LLMModel(Base):
    """Unified model registry combining identity, capabilities, and pricing."""

    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False)
    model_id = Column(String(100), nullable=False)
    display_name = Column(String(150), nullable=False)

    # Capabilities
    context_window = Column(Integer, nullable=True)
    max_output_tokens = Column(Integer, nullable=True)
    supports_vision = Column(Boolean, default=False, nullable=False)
    supports_function_calling = Column(Boolean, default=False, nullable=False)
    supports_streaming = Column(Boolean, default=True, nullable=False)

    # Pricing (in cents per 1M tokens)
    input_cost_per_1m_cents = Column(Integer, default=0, nullable=False)
    output_cost_per_1m_cents = Column(Integer, default=0, nullable=False)
    margin_multiplier = Column(DECIMAL(3, 2), default=1.30, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_custom = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "model_id", name="uk_llm_models_provider_model"),
    )

    def __repr__(self) -> str:
        return f"<LLMModel {self.provider}/{self.model_id}>"
