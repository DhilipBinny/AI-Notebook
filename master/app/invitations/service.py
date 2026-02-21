"""
Invitation service - handles invite code lifecycle.
"""

import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from typing import Optional, List

from .models import Invitation, InvitationUse
from .schemas import InvitationCreate, InvitationBatchCreate


class InvitationService:
    """Service class for invitation operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, created_by: str, data: InvitationCreate) -> Invitation:
        """Create a new invitation."""
        invitation = Invitation(
            code=secrets.token_urlsafe(32),
            email=data.email,
            max_uses=data.max_uses,
            created_by=created_by,
            expires_at=data.expires_at,
            note=data.note,
        )
        self.db.add(invitation)
        await self.db.flush()
        return invitation

    async def batch_create(self, created_by: str, data: InvitationBatchCreate) -> List[Invitation]:
        """Create one invitation per email, locked to that email."""
        invitations = []
        for email in data.emails:
            invitation = Invitation(
                code=secrets.token_urlsafe(32),
                email=email.strip().lower(),
                max_uses=1,
                created_by=created_by,
                expires_at=data.expires_at,
                note=data.note,
            )
            self.db.add(invitation)
            invitations.append(invitation)
        await self.db.flush()
        return invitations

    async def validate_code(self, code: str, email: Optional[str] = None) -> Invitation:
        """
        Validate an invitation code.

        Returns the invitation if valid, raises ValueError otherwise.
        """
        result = await self.db.execute(
            select(Invitation).where(Invitation.code == code)
        )
        invitation = result.scalar_one_or_none()

        if invitation is None:
            raise ValueError("Invalid invitation code")

        if not invitation.is_active:
            raise ValueError("Invitation has been deactivated")

        if invitation.expires_at and invitation.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise ValueError("Invitation has expired")

        if invitation.used_count >= invitation.max_uses:
            raise ValueError("Invitation has been fully used")

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
        return invitation
