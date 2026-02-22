"""
Invitation admin API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.users.models import User
from app.auth.dependencies import get_current_admin_user
from app.email.service import EmailService
from .service import InvitationService
from .schemas import (
    InvitationCreate,
    InvitationBatchCreate,
    InvitationResponse,
    InvitationDetailResponse,
)

router = APIRouter(prefix="/admin/invitations", tags=["Admin - Invitations"])


@router.post("/", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    data: InvitationCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Create a new invitation and send email."""
    service = InvitationService(db)
    try:
        invitation, raw_token = await service.create(created_by=admin.id, data=data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    if data.email and EmailService.is_configured():
        EmailService.send_invitation_background(
            email=data.email,
            invite_code=raw_token,
            note=data.note,
            expires_at=data.expires_at,
            base_url=data.base_url,
        )

    return invitation


@router.post("/batch", response_model=List[InvitationResponse], status_code=status.HTTP_201_CREATED)
async def batch_create_invitations(
    data: InvitationBatchCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Create one invitation per email and send emails."""
    service = InvitationService(db)
    try:
        results = await service.batch_create(created_by=admin.id, data=data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    invitations = []
    for invitation, raw_token in results:
        if invitation.email and EmailService.is_configured():
            EmailService.send_invitation_background(
                email=invitation.email,
                invite_code=raw_token,
                note=data.note,
                expires_at=data.expires_at,
                base_url=data.base_url,
            )
        invitations.append(invitation)

    return invitations


@router.post("/{invitation_id}/reinvite", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def reinvite(
    invitation_id: str,
    base_url: str = "",
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Deactivate old invitation and create a new one for the same email."""
    service = InvitationService(db)
    old = await service.get_by_id(invitation_id)
    if not old:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if not old.email:
        raise HTTPException(status_code=400, detail="Cannot re-invite: no email on invitation")

    # Deactivate the old invitation
    await service.deactivate(invitation_id)

    # Create a new invitation for the same email
    new_data = InvitationCreate(email=old.email, note=old.note, base_url=base_url or None)
    new_invitation, raw_token = await service.create(created_by=admin.id, data=new_data)

    if EmailService.is_configured():
        EmailService.send_invitation_background(
            email=old.email,
            invite_code=raw_token,
            note=old.note,
            base_url=base_url or None,
        )

    return new_invitation


@router.get("/", response_model=List[InvitationResponse])
async def list_invitations(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """List all invitations."""
    service = InvitationService(db)
    invitations = await service.list_all(active_only=active_only)
    return invitations


@router.get("/{invitation_id}", response_model=InvitationDetailResponse)
async def get_invitation(
    invitation_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Get invitation details with usage history."""
    service = InvitationService(db)
    invitation = await service.get_by_id(invitation_id)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return invitation


@router.patch("/{invitation_id}/deactivate", response_model=InvitationResponse)
async def deactivate_invitation(
    invitation_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Deactivate an invitation (soft delete)."""
    service = InvitationService(db)
    invitation = await service.deactivate(invitation_id)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return invitation


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invitation(
    invitation_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Permanently delete an invitation."""
    service = InvitationService(db)
    deleted = await service.delete(invitation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Invitation not found")
