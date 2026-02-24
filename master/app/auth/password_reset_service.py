"""
Password reset service — token creation, validation, and password update.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.email.service import EmailService
from app.users.models import User
from .password import hash_password
from .password_reset_models import PasswordResetToken
from .service import AuthService

logger = logging.getLogger(__name__)

TOKEN_EXPIRY_MINUTES = 10


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


class PasswordResetService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def request_reset(self, email: str, base_url: str) -> None:
        """
        Create a reset token and send email. Returns silently regardless
        of whether the email exists (prevents user enumeration).
        """
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        # Silently ignore: user not found, no password set (OAuth-only), inactive
        if not user or user.password_hash is None:
            logger.info("Password reset requested for non-eligible email (no-op)")
            return
        if not user.is_active:
            logger.info("Password reset requested for inactive user (no-op)")
            return

        # Invalidate any existing unused tokens for this user
        await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.is_used == False,  # noqa: E712
            )
            .values(is_used=True)
        )

        # Generate token
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)

        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRY_MINUTES),
        )
        self.db.add(reset_token)
        await self.db.flush()

        # Send email (fire-and-forget)
        origin = base_url.rstrip("/")
        reset_link = f"{origin}/auth/reset-password?token={raw_token}"
        EmailService.send_password_reset_background(email, reset_link)

        logger.info("Password reset token created for user %s", user.id)

    async def validate_token(self, raw_token: str) -> User:
        """
        Validate a reset token and return the associated user.
        Raises ValueError if invalid/expired/used.
        """
        token_hash = _hash_token(raw_token)

        result = await self.db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        token = result.scalar_one_or_none()

        if not token:
            raise ValueError("Invalid or expired reset token")

        if token.is_used:
            raise ValueError("This reset link has already been used")

        if token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise ValueError("This reset link has expired")

        # Fetch user
        user_result = await self.db.execute(
            select(User).where(User.id == token.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError("Invalid or expired reset token")

        return user

    async def reset_password(self, raw_token: str, new_password_hash: str) -> None:
        """
        Validate token, update password, mark token used, revoke all sessions.
        new_password_hash is already SHA-256 from client — we bcrypt-wrap it.
        """
        token_hash = _hash_token(raw_token)

        result = await self.db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        token = result.scalar_one_or_none()

        if not token:
            raise ValueError("Invalid or expired reset token")
        if token.is_used:
            raise ValueError("This reset link has already been used")
        if token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise ValueError("This reset link has expired")

        # Fetch user
        user_result = await self.db.execute(
            select(User).where(User.id == token.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError("Invalid or expired reset token")

        # Update password: bcrypt(sha256_from_client)
        user.password_hash = hash_password(new_password_hash)

        # Mark token as used
        token.is_used = True

        # Revoke all sessions
        auth_service = AuthService(self.db)
        await auth_service.logout_all(user.id)

        await self.db.flush()
        logger.info("Password reset completed for user %s", user.id)
