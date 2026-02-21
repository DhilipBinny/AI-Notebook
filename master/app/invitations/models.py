"""
Invitation database models.
"""

from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from uuid import uuid4

from app.db.base import Base


class Invitation(Base):
    """Invitation code for controlled user onboarding."""

    __tablename__ = "invitations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    max_uses = Column(Integer, default=1, nullable=False)
    used_count = Column(Integer, default=0, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    uses = relationship("InvitationUse", back_populates="invitation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Invitation {self.code[:8]}... ({self.used_count}/{self.max_uses})>"


class InvitationUse(Base):
    """Tracks which users redeemed which invitations."""

    __tablename__ = "invitation_uses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    invitation_id = Column(String(36), ForeignKey("invitations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    used_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    invitation = relationship("Invitation", back_populates="uses")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<InvitationUse {self.invitation_id} -> {self.user_id}>"
