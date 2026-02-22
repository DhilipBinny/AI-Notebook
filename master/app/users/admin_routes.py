"""
Admin user management routes.
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.users.models import User
from app.auth.dependencies import get_current_admin_user
from app.users.admin_schemas import (
    AdminUserListResponse,
    AdminUserDetailResponse,
    AdminToggleActiveRequest,
    AdminToggleAdminRequest,
    AdminResetPasswordRequest,
    AdminUpdateMaxProjectsRequest,
)
from app.users.admin_service import AdminUserService

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("/", response_model=AdminUserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None, pattern="^(active|inactive)$"),
    role: Optional[str] = Query(None, pattern="^(admin|user)$"),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all users with filtering and pagination."""
    service = AdminUserService(db)
    users, total = await service.list_users(
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status,
        role=role,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return AdminUserListResponse(users=users, total=total, page=page, page_size=page_size)


@router.get("/{user_id}", response_model=AdminUserDetailResponse)
async def get_user_detail(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed user information."""
    service = AdminUserService(db)
    return await service.get_user_detail(user_id)


@router.patch("/{user_id}/active")
async def toggle_active(
    user_id: str,
    body: AdminToggleActiveRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle user active status. Revokes all sessions on deactivation."""
    service = AdminUserService(db)
    return await service.toggle_active(user_id, body.is_active, current_user.id)


@router.patch("/{user_id}/admin")
async def toggle_admin(
    user_id: str,
    body: AdminToggleAdminRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle user admin status."""
    service = AdminUserService(db)
    return await service.toggle_admin(user_id, body.is_admin, current_user.id)


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    body: AdminResetPasswordRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset user password. Only works for local auth users."""
    service = AdminUserService(db)
    return await service.reset_password(user_id, body.new_password)


@router.patch("/{user_id}/max-projects")
async def update_max_projects(
    user_id: str,
    body: AdminUpdateMaxProjectsRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user's maximum projects limit."""
    service = AdminUserService(db)
    return await service.update_max_projects(user_id, body.max_projects)
