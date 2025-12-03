"""
User service layer - business logic for user operations.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import Optional
from datetime import datetime

from .models import User, OAuthProvider
from .schemas import UserCreate, UserCreateOAuth, UserUpdate
from app.auth.password import hash_password


class UserService:
    """Service class for user operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_oauth(self, provider: OAuthProvider, oauth_id: str) -> Optional[User]:
        """Get user by OAuth provider and ID."""
        result = await self.db.execute(
            select(User).where(
                User.oauth_provider == provider,
                User.oauth_id == oauth_id
            )
        )
        return result.scalar_one_or_none()

    async def create(self, user_data: UserCreate) -> User:
        """
        Create a new user with email/password.

        Raises:
            ValueError: If email already exists
        """
        # Check if email exists
        existing = await self.get_by_email(user_data.email)
        if existing:
            raise ValueError("Email already registered")

        # Create user
        user = User(
            email=user_data.email.lower(),
            name=user_data.name,
            password_hash=hash_password(user_data.password),
            oauth_provider=OAuthProvider.LOCAL,
        )

        self.db.add(user)

        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise ValueError("Email already registered")

        return user

    async def create_oauth(self, user_data: UserCreateOAuth) -> User:
        """
        Create a new user via OAuth.

        Raises:
            ValueError: If email or OAuth ID already exists
        """
        # Check if email exists
        existing = await self.get_by_email(user_data.email)
        if existing:
            raise ValueError("Email already registered")

        # Check if OAuth ID exists
        existing_oauth = await self.get_by_oauth(user_data.oauth_provider, user_data.oauth_id)
        if existing_oauth:
            raise ValueError("OAuth account already linked")

        # Create user
        user = User(
            email=user_data.email.lower(),
            name=user_data.name,
            avatar_url=user_data.avatar_url,
            oauth_provider=user_data.oauth_provider,
            oauth_id=user_data.oauth_id,
            is_verified=True,  # OAuth users are pre-verified
        )

        self.db.add(user)

        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise ValueError("Account already exists")

        return user

    async def update(self, user: User, user_data: UserUpdate) -> User:
        """Update user profile."""
        update_data = user_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.flush()
        return user

    async def update_last_login(self, user: User) -> None:
        """Update user's last login timestamp."""
        user.last_login_at = datetime.utcnow()
        await self.db.flush()

    async def delete(self, user: User) -> None:
        """Delete user account."""
        await self.db.delete(user)
        await self.db.flush()

    async def count_projects(self, user_id: str) -> int:
        """Count user's active (non-archived, non-deleted) projects."""
        from app.projects.models import Project

        result = await self.db.execute(
            select(Project).where(
                Project.user_id == user_id,
                Project.is_archived == False,
                Project.deleted_at.is_(None)
            )
        )
        return len(result.scalars().all())

    async def can_create_project(self, user: User) -> bool:
        """Check if user can create another project (quota check)."""
        current_count = await self.count_projects(user.id)
        return current_count < user.max_projects
