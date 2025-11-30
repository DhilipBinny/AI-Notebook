"""
Session model for refresh token management.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from uuid import uuid4

from app.db.base import Base


class Session(Base):
    """User session model for refresh tokens."""

    __tablename__ = "sessions"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # User reference
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Token info (stored as hash)
    refresh_token_hash = Column(String(255), nullable=False, index=True)

    # Device info
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Validity
    expires_at = Column(DateTime, nullable=False, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<Session {self.id[:8]} for user {self.user_id[:8]}>"
