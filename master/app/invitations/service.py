"""
Invitation service - handles invite code lifecycle.

Security: tokens are hashed (SHA-256) before storage. The raw token
only exists in the email link and is returned once on creation.
Even if the database is compromised, tokens cannot be recovered.
"""

import hashlib
import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple

DEFAULT_EXPIRY_HOURS = 48

from app.users.models import User
from .models import Invitation, InvitationUse
from .schemas import InvitationCreate, InvitationBatchCreate


def _generate_token() -> Tuple[str, str]:
    """Generate a raw token and its SHA-256 hash."""
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def _hash_token(raw: str) -> str:
    """Hash a raw token for DB lookup."""
    return hashlib.sha256(raw.encode()).hexdigest()


class InvitationService:
    """Service class for invitation operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _check_email_not_registered(self, email: str) -> None:
        """Raise ValueError if the email already has an account."""
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        if result.scalar_one_or_none():
            raise ValueError(f"{email} is already registered")

    async def create(self, created_by: str, data: InvitationCreate) -> Tuple[Invitation, str]:
        """
        Create a new invitation.
        Returns (invitation, raw_token). Raw token is only available at creation time.
        """
        if data.email:
            await self._check_email_not_registered(data.email)
        expires_at = data.expires_at or (datetime.now(timezone.utc) + timedelta(hours=DEFAULT_EXPIRY_HOURS))
        raw_token, hashed = _generate_token()
        invitation = Invitation(
            code=hashed,
            email=data.email,
            created_by=created_by,
            expires_at=expires_at,
            note=data.note,
        )
        self.db.add(invitation)
        await self.db.flush()
        await self.db.refresh(invitation)
        return invitation, raw_token

    async def batch_create(self, created_by: str, data: InvitationBatchCreate) -> List[Tuple[Invitation, str]]:
        """
        Create one invitation per email, locked to that email.
        Returns list of (invitation, raw_token) tuples.
        """
        expires_at = data.expires_at or (datetime.now(timezone.utc) + timedelta(hours=DEFAULT_EXPIRY_HOURS))
        for email in data.emails:
            await self._check_email_not_registered(email.strip())
        results: List[Tuple[Invitation, str]] = []
        for email in data.emails:
            raw_token, hashed = _generate_token()
            invitation = Invitation(
                code=hashed,
                email=email.strip().lower(),
                created_by=created_by,
                expires_at=expires_at,
                note=data.note,
            )
            self.db.add(invitation)
            results.append((invitation, raw_token))
        await self.db.flush()
        for inv, _ in results:
            await self.db.refresh(inv)
        return results

    async def validate_code(self, code: str, email: Optional[str] = None) -> Invitation:
        """
        Validate a raw invitation token.
        Hashes the input and looks up by hash. Returns the invitation if valid.
        """
        hashed = _hash_token(code)
        result = await self.db.execute(
            select(Invitation).where(Invitation.code == hashed)
        )
        invitation = result.scalar_one_or_none()

        if invitation is None:
            raise ValueError("Invalid invitation code")

        if not invitation.is_active:
            raise ValueError("Invitation has been deactivated")

        if invitation.expires_at and invitation.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise ValueError("Invitation has expired")

        if invitation.used_count > 0:
            raise ValueError("Invitation has already been used")

        if invitation.email and email:
            if invitation.email.lower() != email.lower():
                raise ValueError("Invitation is not valid for this email")

        return invitation

    async def redeem(self, invitation: Invitation, user_id: str) -> InvitationUse:
        """Record invitation usage after successful registration."""
        invitation.used_count += 1

        use = InvitationUse(
            invitation_id=invitation.id,
            user_id=user_id,
        )
        self.db.add(use)
        await self.db.flush()
        return use

    async def list_all(
        self,
        active_only: bool = False,
        created_by: Optional[str] = None,
    ) -> List[Invitation]:
        """List all invitations with optional filters."""
        query = select(Invitation).order_by(Invitation.created_at.desc())

        if active_only:
            query = query.where(Invitation.is_active == True)

        if created_by:
            query = query.where(Invitation.created_by == created_by)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, invitation_id: str) -> Optional[Invitation]:
        """Get invitation by ID."""
        result = await self.db.execute(
            select(Invitation).where(Invitation.id == invitation_id)
        )
        return result.scalar_one_or_none()

    async def deactivate(self, invitation_id: str) -> Optional[Invitation]:
        """Deactivate an invitation."""
        invitation = await self.get_by_id(invitation_id)
        if invitation:
            invitation.is_active = False
            await self.db.flush()
            await self.db.refresh(invitation)
        return invitation

    async def delete(self, invitation_id: str) -> bool:
        """Hard delete an invitation and its usage records."""
        invitation = await self.get_by_id(invitation_id)
        if not invitation:
            return False
        await self.db.delete(invitation)
        await self.db.flush()
        return True
