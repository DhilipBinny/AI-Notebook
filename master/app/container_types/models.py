"""
Container type database model.
Defines container configurations (image, resources, network) that admin can manage.
Used by PlaygroundService (and future container services) to spin up containers.
"""

from sqlalchemy import Column, String, Boolean, Text, DateTime, Numeric, Integer
from sqlalchemy.sql import func
from uuid import uuid4

from app.db.base import Base


class ContainerType(Base):
    """Admin-configurable container type with resource limits."""

    __tablename__ = "container_types"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Unique identifier (e.g., "playground", "doc_analyzer")
    name = Column(String(50), unique=True, nullable=False, index=True)

    # Display
    label = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Docker settings
    image = Column(String(255), nullable=False)
    network = Column(String(100), nullable=False, default="ainotebook-network")

    # Resource limits
    memory_limit = Column(String(20), nullable=False, default="4g")
    cpu_limit = Column(Numeric(4, 2), nullable=False, default=4.0)
    idle_timeout = Column(Integer, nullable=False, default=3600)

    # State
    is_active = Column(Boolean, nullable=False, default=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"<ContainerType '{self.name}' ({status})>"
