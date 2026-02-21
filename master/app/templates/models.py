"""
Notebook template database model.
"""

from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from uuid import uuid4

from app.db.base import Base


class DifficultyLevel(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class NotebookTemplate(Base):
    """Notebook template for course content."""

    __tablename__ = "notebook_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    storage_path = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    difficulty_level = Column(
        SQLEnum(DifficultyLevel, values_callable=lambda obj: [e.value for e in obj]),
        default=DifficultyLevel.BEGINNER,
        nullable=False,
    )
    estimated_minutes = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=True)
    is_public = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<NotebookTemplate {self.name}>"
