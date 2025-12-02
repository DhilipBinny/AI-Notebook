"""
Workspace database model - groups projects/notebooks together.
"""

from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime

from app.db.base import Base


class Workspace(Base):
    """Workspace model - organizes projects into groups."""

    __tablename__ = "workspaces"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Owner
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Workspace info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Visual customization
    color = Column(String(7), default="#3B82F6", nullable=False)  # Hex color (default: blue)
    icon = Column(String(50), default="folder", nullable=True)  # Icon name

    # State
    is_default = Column(Boolean, default=False, nullable=False)  # One default per user
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)  # Soft delete flag

    # Display order
    sort_order = Column(String(50), default="0", nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete timestamp

    # Relationships
    owner = relationship("User", back_populates="workspaces")
    projects = relationship("Project", back_populates="workspace", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Workspace {self.name}>"
