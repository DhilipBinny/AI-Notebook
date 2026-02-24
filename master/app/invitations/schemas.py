"""
Invitation Pydantic schemas.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class InvitationCreate(BaseModel):
    """Schema for creating an invitation."""
    email: Optional[str] = Field(None, max_length=255)
    expires_at: Optional[datetime] = None
    note: Optional[str] = Field(None, max_length=500)
    base_url: Optional[str] = Field(None, max_length=500)


class InvitationBatchCreate(BaseModel):
    """Schema for batch creating invitations (one per email)."""
    emails: List[str] = Field(..., min_length=1, max_length=100)
    note: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[datetime] = None
    base_url: Optional[str] = Field(None, max_length=500)


class InvitationResponse(BaseModel):
    """Schema for invitation in list views. No raw token — only hash prefix."""
    id: str
    code_prefix: str
    email: Optional[str]
    is_used: bool
    created_by: str
    expires_at: Optional[datetime]
    is_active: bool
    note: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvitationListResponse(BaseModel):
    """Paginated invitation list response."""
    invitations: List[InvitationResponse]
    total: int
    page: int
    page_size: int


class InvitationUseResponse(BaseModel):
    """Schema for invitation use record."""
    id: str
    invitation_id: str
    user_id: str
    used_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvitationDetailResponse(InvitationResponse):
    """Invitation with usage details."""
    uses: List[InvitationUseResponse] = []

    model_config = ConfigDict(from_attributes=True)
