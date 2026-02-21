"""
User API key database model.
"""

from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from uuid import uuid4

from app.db.base import Base


class LLMProviderKey(str, enum.Enum):
    """Supported LLM providers for user keys."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"


class UserApiKey(Base):
    """User-owned API key for LLM providers."""

    __tablename__ = "user_api_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uk_user_api_keys_provider"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(
        SQLEnum(LLMProviderKey, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False
    )
    api_key_encrypted = Column(Text, nullable=False)
    api_key_hint = Column(String(20), nullable=False)
    model_override = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_validated = Column(Boolean, default=False, nullable=False)
    last_validated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<UserApiKey {self.provider.value} ({self.api_key_hint})>"
