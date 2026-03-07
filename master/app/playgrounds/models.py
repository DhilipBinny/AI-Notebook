"""
Playground database model - tracks active container instances.
Multiple containers per user (up to max_containers), one per project.
"""

from sqlalchemy import Column, String, Text, DateTime, Enum as SQLEnum, ForeignKey, Integer, Numeric, UniqueConstraint
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
    """Active playground container model. One per project per user."""

    __tablename__ = "playgrounds"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # User reference (multiple playgrounds per user, up to max_containers)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Project reference (one playground per project)
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
    user = relationship("User", back_populates="playgrounds")
    project = relationship("Project", back_populates="playground")

    # One container per project per user
    __table_args__ = (
        UniqueConstraint('user_id', 'project_id', name='uk_playgrounds_user_project'),
    )

    def __repr__(self) -> str:
        return f"<Playground {self.container_name} ({self.status.value})>"
