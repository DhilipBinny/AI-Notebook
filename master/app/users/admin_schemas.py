"""
Admin user management schemas.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.auth.schemas import validate_password_policy


class AdminUserResponse(BaseModel):
    """User info for admin list view."""
    id: str
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    oauth_provider: str
    is_active: bool
    is_verified: bool
    is_admin: bool
    max_projects: int
    created_at: datetime
    last_login_at: Optional[datetime] = None
    credit_balance_cents: Optional[int] = None
    project_count: Optional[int] = None

    model_config = {"from_attributes": True}


class AdminUserDetailResponse(AdminUserResponse):
    """Extended user info for admin detail view."""
    active_sessions_count: int = 0
    api_keys_count: int = 0
    total_consumed_cents: int = 0
    total_deposited_cents: int = 0


class AdminUserListResponse(BaseModel):
    """Paginated list of users."""
    users: List[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminToggleActiveRequest(BaseModel):
    is_active: bool


class AdminToggleAdminRequest(BaseModel):
    is_admin: bool


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator('new_password')
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_policy(v)


class AdminUpdateMaxProjectsRequest(BaseModel):
    max_projects: int = Field(..., ge=1, le=100)
