"""
Playground database model - tracks active container instances.
One container per user (not per project).
"""

from sqlalchemy import Column, String, Text, DateTime, Enum as SQLEnum, ForeignKey, Integer, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from uuid import uuid4

from app.db.base import Base


class PlaygroundStatus(str, enum.Enum):
    """Playground container status."""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class Playground(Base):
    """Active playground container model. One per user."""

    __tablename__ = "playgrounds"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # User reference (one playground per user)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # Active project reference (nullable - tracks which project is loaded)
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Container info
    container_id = Column(String(255), unique=True, nullable=False)
    container_name = Column(String(255), nullable=False)
    internal_url = Column(String(500), nullable=False)
    internal_secret = Column(String(255), nullable=False)

    # Status
    status = Column(
        SQLEnum(PlaygroundStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=PlaygroundStatus.STARTING,
        nullable=False
    )
    error_message = Column(Text, nullable=True)

    # Resource limits
    memory_limit_mb = Column(Integer, default=2048, nullable=False)
    cpu_limit = Column(Numeric(3, 2), default=1.0, nullable=False)

    # Timestamps
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_activity_at = Column(DateTime, server_default=func.now(), nullable=False)
    stopped_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="playground")
    project = relationship("Project", back_populates="playground")

    def __repr__(self) -> str:
        return f"<Playground {self.container_name} ({self.status.value})>"
