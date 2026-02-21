"""
Invitation admin API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.users.models import User
from app.auth.dependencies import get_current_admin_user
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
    """Create a new invitation code."""
    service = InvitationService(db)
    invitation = await service.create(created_by=admin.id, data=data)
    return invitation


@router.post("/batch", response_model=List[InvitationResponse], status_code=status.HTTP_201_CREATED)
async def batch_create_invitations(
    data: InvitationBatchCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Create one invitation per email (locked to that email)."""
    service = InvitationService(db)
    invitations = await service.batch_create(created_by=admin.id, data=data)
    return invitations


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


@router.delete("/{invitation_id}", response_model=InvitationResponse)
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
