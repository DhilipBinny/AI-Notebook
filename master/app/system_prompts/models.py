"""
System prompt database model.
Stores admin-editable LLM system prompts for chat panel and AI cell modes.
"""

import enum

from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from uuid import uuid4

from app.db.base import Base


class PromptType(str, enum.Enum):
    CHAT_PANEL = "chat_panel"
    AI_CELL = "ai_cell"


class SystemPrompt(Base):
    """Admin-editable system prompt for LLM modes."""

    __tablename__ = "system_prompts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    prompt_type = Column(
        SQLEnum(PromptType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    label = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True, default=None)

    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"<SystemPrompt {self.prompt_type.value} '{self.label}' ({status})>"
