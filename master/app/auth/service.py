"""
Authentication service - handles login, registration, token management.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, timezone
from typing import Optional
import hashlib

from .models import Session
from .jwt import create_token_pair, verify_token, get_refresh_token_expiry, TokenPair
from .password import verify_password, hash_password
from app.users.models import User
from app.users.service import UserService
from app.users.schemas import UserCreate


class AuthService:
    """Service class for authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)

    async def register(
        self,
        email: str,
        password: str,
        name: Optional[str] = None,
    ) -> tuple[User, TokenPair]:
        """
        Register a new user.

        Args:
            email: User email
            password: Plain text password
            name: Optional display name

        Returns:
            Tuple of (user, token_pair)

        Raises:
            ValueError: If email already exists
        """
        user_data = UserCreate(email=email, password=password, name=name)
        user = await self.user_service.create(user_data)

        # Create tokens
        tokens = create_token_pair(user.id)

        # Store refresh token
        await self._create_session(user.id, tokens.refresh_token)

        return user, tokens

    async def login(
        self,
        email: str,
        password: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> tuple[User, TokenPair]:
        """
        Authenticate a user with email and password.

        Args:
            email: User email
            password: Plain text password
            user_agent: Optional browser user agent
            ip_address: Optional client IP

        Returns:
            Tuple of (user, token_pair)

        Raises:
            ValueError: If credentials invalid
        """
        user = await self.user_service.get_by_email(email)

        if user is None:
            raise ValueError("Invalid email or password")

        if user.password_hash is None:
            raise ValueError("Please login with your OAuth provider")

        if not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is disabled")

        # Update last login
        await self.user_service.update_last_login(user)

        # Create tokens
        tokens = create_token_pair(user.id)

        # Store refresh token
        await self._create_session(
            user.id,
            tokens.refresh_token,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return user, tokens

    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New token pair

        Raises:
            ValueError: If refresh token invalid
        """
        # Verify token
        token_data = verify_token(refresh_token, expected_type="refresh")
        if token_data is None:
            raise ValueError("Invalid refresh token")

        # Check session exists and not revoked
        token_hash = self._hash_token(refresh_token)
        session = await self._get_session_by_token_hash(token_hash)

        if session is None or session.is_revoked:
            raise ValueError("Session expired or revoked")

        if session.expires_at < datetime.now(timezone.utc):
            raise ValueError("Refresh token expired")

        # Revoke old session
        session.is_revoked = True

        # Create new tokens
        tokens = create_token_pair(token_data.sub)

        # Create new session
        await self._create_session(token_data.sub, tokens.refresh_token)

        return tokens

    async def logout(self, refresh_token: str) -> None:
        """
        Logout user by revoking refresh token.

        Args:
            refresh_token: Refresh token to revoke
        """
        token_hash = self._hash_token(refresh_token)
        session = await self._get_session_by_token_hash(token_hash)

        if session:
            session.is_revoked = True
            await self.db.flush()

    async def logout_all(self, user_id: str) -> None:
        """
        Logout user from all sessions.

        Args:
            user_id: User ID to logout
        """
        await self.db.execute(
            delete(Session).where(Session.user_id == user_id)
        )
        await self.db.flush()

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        """
        Change user's password.

        Args:
            user: User object
            current_password: Current password for verification
            new_password: New password to set

        Raises:
            ValueError: If current password incorrect
        """
        if user.password_hash is None:
            raise ValueError("Cannot change password for OAuth users")

        if not verify_password(current_password, user.password_hash):
            raise ValueError("Current password is incorrect")

        user.password_hash = hash_password(new_password)
        await self.db.flush()

        # Revoke all sessions (force re-login)
        await self.logout_all(user.id)

    async def _create_session(
        self,
        user_id: str,
        refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Session:
        """Create a new session with refresh token."""
        session = Session(
            user_id=user_id,
            refresh_token_hash=self._hash_token(refresh_token),
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=get_refresh_token_expiry(),
        )

        self.db.add(session)
        await self.db.flush()

        return session

    async def _get_session_by_token_hash(self, token_hash: str) -> Optional[Session]:
        """Get session by refresh token hash."""
        result = await self.db.execute(
            select(Session).where(Session.refresh_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash a token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
