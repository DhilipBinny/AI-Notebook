"""
Authentication Pydantic schemas.
"""

import re
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


def validate_password_policy(v: str) -> str:
    """Shared password policy validation."""
    errors = []
    if len(v) < 8:
        errors.append('at least 8 characters')
    if not re.search(r'[A-Z]', v):
        errors.append('at least one uppercase letter')
    if not re.search(r'[a-z]', v):
        errors.append('at least one lowercase letter')
    if not re.search(r'[0-9]', v):
        errors.append('at least one number')
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/~`]', v):
        errors.append('at least one special character')
    if errors:
        raise ValueError('Password must contain: ' + ', '.join(errors))
    return v


class LoginRequest(BaseModel):
    """Schema for login request."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    """Schema for registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    name: Optional[str] = Field(None, max_length=255)
    invite_code: Optional[str] = Field(None, max_length=64)

    @field_validator('password')
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_policy(v)


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """Schema for password change request."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator('new_password')
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_policy(v)


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
