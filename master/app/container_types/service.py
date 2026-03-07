"""
Container type service — CRUD operations for container type configurations.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from uuid import uuid4
import logging

from .models import ContainerType
from .schemas import ContainerTypeCreate, ContainerTypeUpdate

logger = logging.getLogger(__name__)


class ContainerTypeService:
    """Service class for container type operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> List[ContainerType]:
        """List all container types ordered by name."""
        result = await self.db.execute(
            select(ContainerType).order_by(ContainerType.name)
        )
        return list(result.scalars().all())

    async def get_by_id(self, type_id: str) -> Optional[ContainerType]:
        """Get a container type by ID."""
        return await self.db.get(ContainerType, type_id)

    async def get_by_name(self, name: str) -> Optional[ContainerType]:
        """Get a container type by unique name."""
        result = await self.db.execute(
            select(ContainerType).where(ContainerType.name == name)
        )
        return result.scalar_one_or_none()

    async def create(self, data: ContainerTypeCreate) -> ContainerType:
        """Create a new container type."""
        ct = ContainerType(
            id=str(uuid4()),
            name=data.name,
            label=data.label,
            description=data.description,
            image=data.image,
            network=data.network,
            memory_limit=data.memory_limit,
            cpu_limit=data.cpu_limit,
            idle_timeout=data.idle_timeout,
            is_active=data.is_active,
        )
        self.db.add(ct)
        await self.db.flush()
        await self.db.refresh(ct)
        return ct

    async def update(self, type_id: str, data: ContainerTypeUpdate) -> Optional[ContainerType]:
        """Update a container type. Only updates fields that are explicitly set."""
        ct = await self.get_by_id(type_id)
        if not ct:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(ct, field, value)

        await self.db.flush()
        await self.db.refresh(ct)
        return ct

    async def delete(self, type_id: str) -> bool:
        """Delete a container type."""
        ct = await self.get_by_id(type_id)
        if not ct:
            return False

        await self.db.delete(ct)
        await self.db.flush()
        return True
