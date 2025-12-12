"""
Audit log database model.
"""

from sqlalchemy import Column, String, BigInteger, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
import enum

from app.db.base import Base


class AuditStatus(str, enum.Enum):
    """Audit log status values."""
    SUCCESS = "success"
    FAILED = "failed"
    DENIED = "denied"


class ActivityLog(Base):
    """Activity log model for audit trail."""

    __tablename__ = "activity_logs"

    # Primary key (auto-increment for high-volume table)
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # User reference (NULL for system/anonymous events)
    user_id = Column(String(36), nullable=True, index=True)

    # Activity info
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(36), nullable=True)

    # Additional context
    details = Column("metadata", JSON, nullable=True)  # 'metadata' is reserved in SQLAlchemy, use 'details' as attribute
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Result status
    status = Column(
        SQLEnum(AuditStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=AuditStatus.SUCCESS,
        nullable=False,
        index=True
    )

    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<ActivityLog {self.id}: {self.action} ({self.status.value})>"
