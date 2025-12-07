"""
User API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_active_user
from .models import User
from .schemas import UserResponse, UserUpdate
from .service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get current user profile.
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    request: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update current user profile.
    """
    user_service = UserService(db)
    updated_user = await user_service.update(current_user, request)

    return updated_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete current user account.

    This will delete all projects and associated data.
    """
    user_service = UserService(db)
    await user_service.delete(current_user)


