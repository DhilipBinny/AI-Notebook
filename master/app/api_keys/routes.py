"""
User API key management routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.users.models import User
from app.auth.dependencies import get_current_active_user
from .service import ApiKeyService
from .schemas import ApiKeyCreate, ApiKeyUpdate, ApiKeyResponse, ProviderInfo

router = APIRouter(prefix="/users/me/api-keys", tags=["API Keys"])


@router.post("/", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: ApiKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update an API key for a provider."""
    service = ApiKeyService(db)
    api_key = await service.create_or_update(current_user.id, data)
    return api_key


@router.get("/", response_model=List[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the current user (masked)."""
    service = ApiKeyService(db)
    keys = await service.get_for_user(current_user.id)
    return keys


@router.put("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: str,
    data: ApiKeyUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an API key."""
    service = ApiKeyService(db)
    api_key = await service.update(key_id, current_user.id, data)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    return api_key


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an API key."""
    service = ApiKeyService(db)
    deleted = await service.delete(key_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"message": "API key deleted"}


@router.post("/{key_id}/validate")
async def validate_api_key(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Test if an API key is valid."""
    service = ApiKeyService(db)
    result = await service.validate_key(key_id, current_user.id)
    return result


@router.get("/providers", response_model=List[ProviderInfo])
async def get_available_providers(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get available LLM providers with model lists."""
    service = ApiKeyService(db)
    providers = await service.get_available_providers(current_user.id)
    return providers
