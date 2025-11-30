"""
Project database model.
"""

from sqlalchemy import Column, String, Boolean, Text, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from uuid import uuid4
from datetime import datetime

from app.db.base import Base


class LLMProvider(str, enum.Enum):
    """Supported LLM providers."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class Project(Base):
    """Notebook project model."""

    __tablename__ = "projects"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Owner
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Project info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Storage location in MinIO
    storage_path = Column(String(500), nullable=False)

    # LLM settings
    llm_provider = Column(
        SQLEnum(LLMProvider, values_callable=lambda obj: [e.value for e in obj]),
        default=LLMProvider.GEMINI,
        nullable=False
    )
    llm_model = Column(String(100), nullable=True)

    # State
    is_archived = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), onupdate=datetime.utcnow, nullable=False)
    last_opened_at = Column(DateTime, nullable=True)

    # Relationships
    owner = relationship("User", back_populates="projects")
    playground = relationship("Playground", back_populates="project", uselist=False, cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project {self.name}>"
