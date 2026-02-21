"""
Platform API key admin routes.
All endpoints require admin authentication.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_admin_user
from app.users.models import User
from app.platform_keys.schemas import PlatformKeyCreate, PlatformKeyUpdate, PlatformKeyResponse
from app.platform_keys.service import PlatformKeyService

router = APIRouter(prefix="/admin/platform-keys", tags=["Platform Keys"])


@router.post("/", response_model=PlatformKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_platform_key(
    data: PlatformKeyCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new platform API key for a provider."""
    service = PlatformKeyService(db)
    key = await service.create(data, current_user.id)
    return key


@router.get("/", response_model=List[PlatformKeyResponse])
async def list_platform_keys(
    provider: Optional[str] = Query(None, pattern="^(openai|anthropic|gemini|openai_compatible)$"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all platform API keys, optionally filtered by provider."""
    service = PlatformKeyService(db)
    keys = await service.list_all(provider=provider)
    return keys


@router.put("/{key_id}", response_model=PlatformKeyResponse)
async def update_platform_key(
    key_id: str,
    data: PlatformKeyUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a platform API key."""
    service = PlatformKeyService(db)
    key = await service.update(key_id, data)
    if not key:
        raise HTTPException(status_code=404, detail="Platform key not found")
    return key


@router.delete("/{key_id}")
async def delete_platform_key(
    key_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a platform API key."""
    service = PlatformKeyService(db)
    deleted = await service.delete(key_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Platform key not found")
    return {"message": "Platform key deleted"}


@router.post("/{key_id}/activate", response_model=PlatformKeyResponse)
async def activate_platform_key(
    key_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Activate this key (deactivates all others for the same provider)."""
    service = PlatformKeyService(db)
    key = await service.activate(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Platform key not found")
    return key


@router.post("/{key_id}/deactivate", response_model=PlatformKeyResponse)
async def deactivate_platform_key(
    key_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate this key (provider will have no active key)."""
    service = PlatformKeyService(db)
    key = await service.deactivate(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Platform key not found")
    return key


@router.post("/{key_id}/set-default", response_model=PlatformKeyResponse)
async def set_default_platform_key(
    key_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Set this key's provider as the system default (also activates it)."""
    service = PlatformKeyService(db)
    key = await service.set_default(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Platform key not found")
    return key


@router.post("/{key_id}/validate")
async def validate_platform_key(
    key_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Test if a platform API key is valid by making a lightweight API call."""
    service = PlatformKeyService(db)
    result = await service.validate_key(key_id)
    return result
