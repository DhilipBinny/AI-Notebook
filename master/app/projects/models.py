"""
Project database model.
"""

from sqlalchemy import Column, String, Boolean, Text, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from uuid import uuid4
from datetime import datetime, timezone

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

    # Workspace (optional - for grouping)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)

    # Project info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Storage location in MinIO
    storage_path = Column(String(500), nullable=False)

    # LLM settings (deprecated - provider is now selected per-chat session)
    # Kept for backward compatibility with existing database
    llm_provider = Column(
        SQLEnum(LLMProvider, values_callable=lambda obj: [e.value for e in obj]),
        default=LLMProvider.GEMINI,
        nullable=False
    )
    llm_model = Column(String(100), nullable=True)

    # State
    is_archived = Column(Boolean, default=False, nullable=False)

    # Storage month folder (mm-yyyy format, derived from created_at)
    storage_month = Column(String(7), nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), onupdate=datetime.utcnow, nullable=False)
    last_opened_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True, index=True)  # Soft delete timestamp

    # Relationships
    owner = relationship("User", back_populates="projects")
    workspace = relationship("Workspace", back_populates="projects")
    playground = relationship("Playground", back_populates="project", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project {self.name}>"

    def get_storage_base_path(self) -> str:
        """Get the base S3 path for this project: {mm-yyyy}/{project_id}"""
        return f"{self.storage_month}/{self.id}"

    @staticmethod
    def generate_storage_month(dt: datetime = None) -> str:
        """Generate storage month string in mm-yyyy format."""
        if dt is None:
            dt = datetime.now(timezone.utc)
        return dt.strftime("%m-%Y")
