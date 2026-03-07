"""
User Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime

from .models import OAuthProvider


class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user (registration)."""
    password: str = Field(..., min_length=8, max_length=100)


class UserCreateOAuth(UserBase):
    """Schema for creating a user via OAuth."""
    oauth_provider: OAuthProvider
    oauth_id: str
    avatar_url: Optional[str] = None


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    name: Optional[str] = Field(None, max_length=255)
    avatar_url: Optional[str] = Field(None, max_length=500)


class UserResponse(UserBase):
    """Schema for user response (public data)."""
    id: str
    name: Optional[str]
    avatar_url: Optional[str]
    oauth_provider: OAuthProvider
    max_projects: int
    max_containers: int
    is_active: bool
    is_verified: bool
    is_admin: bool = False
    created_at: datetime
    last_login_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserResponse):
    """Schema for user with internal fields (not exposed via API)."""
    password_hash: Optional[str]
    oauth_id: Optional[str]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
