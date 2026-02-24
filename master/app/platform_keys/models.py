"""
Platform API key database model.
Stores encrypted LLM provider keys at the platform level (admin-managed).
Multiple keys per provider allowed; one active per provider at a time.
"""

import enum

from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from uuid import uuid4

from app.db.base import Base
from app.api_keys.models import LLMProviderKey


class AuthType(str, enum.Enum):
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"


class PlatformApiKey(Base):
    """Platform-level API key for LLM providers."""

    __tablename__ = "platform_api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    provider = Column(
        SQLEnum(LLMProviderKey, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False
    )
    label = Column(String(100), nullable=False)
    api_key_encrypted = Column(Text, nullable=False)
    api_key_hint = Column(String(20), nullable=False)
    auth_type = Column(
        SQLEnum(AuthType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=AuthType.API_KEY,
        server_default="api_key",
    )
    model_name = Column(String(100), nullable=True)
    base_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    user_visible = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"<PlatformApiKey {self.provider.value} '{self.label}' ({status})>"
