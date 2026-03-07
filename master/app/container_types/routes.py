"""
Container type admin routes.
All endpoints require admin authentication.
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_admin_user
from app.users.models import User
from .schemas import ContainerTypeCreate, ContainerTypeUpdate, ContainerTypeResponse
from .service import ContainerTypeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/container-types", tags=["Admin - Container Types"])


@router.get("/", response_model=List[ContainerTypeResponse])
async def list_container_types(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all container types."""
    service = ContainerTypeService(db)
    return await service.list_all()


@router.post("/", response_model=ContainerTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_container_type(
    data: ContainerTypeCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new container type."""
    service = ContainerTypeService(db)

    # Check for duplicate name
    existing = await service.get_by_name(data.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Container type '{data.name}' already exists")

    return await service.create(data)


@router.put("/{type_id}", response_model=ContainerTypeResponse)
async def update_container_type(
    type_id: str,
    data: ContainerTypeUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a container type's configuration."""
    service = ContainerTypeService(db)
    ct = await service.update(type_id, data)
    if not ct:
        raise HTTPException(status_code=404, detail="Container type not found")
    return ct


@router.delete("/{type_id}")
async def delete_container_type(
    type_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a container type."""
    service = ContainerTypeService(db)

    # Prevent deleting the playground type
    ct = await service.get_by_id(type_id)
    if ct and ct.name == "playground":
        raise HTTPException(status_code=400, detail="Cannot delete the default 'playground' container type")

    deleted = await service.delete(type_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Container type not found")
    return {"message": "Container type deleted"}
