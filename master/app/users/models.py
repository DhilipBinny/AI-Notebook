"""
User database model.
"""

from sqlalchemy import Column, String, Boolean, Integer, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from uuid import uuid4

from app.db.base import Base


class OAuthProvider(str, enum.Enum):
    """Supported OAuth providers."""
    LOCAL = "local"
    GOOGLE = "google"
    GITHUB = "github"


class User(Base):
    """User account model."""

    __tablename__ = "users"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Basic info
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)

    # Authentication
    password_hash = Column(String(255), nullable=True)  # NULL for OAuth-only users
    oauth_provider = Column(
        SQLEnum(OAuthProvider, values_callable=lambda obj: [e.value for e in obj]),
        default=OAuthProvider.LOCAL,
        nullable=False
    )
    oauth_id = Column(String(255), nullable=True)

    # Account settings
    max_projects = Column(Integer, default=5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.email}>"
