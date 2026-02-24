"""
System prompt service.
Manages admin-editable LLM system prompts.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.system_prompts.models import SystemPrompt, PromptType
from app.system_prompts.schemas import SystemPromptCreate, SystemPromptUpdate

logger = logging.getLogger(__name__)


class SystemPromptService:
    """Service for system prompt CRUD and activation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: SystemPromptCreate, admin_id: str) -> SystemPrompt:
        """Create a new system prompt (inactive by default)."""
        prompt = SystemPrompt(
            prompt_type=PromptType(data.prompt_type),
            label=data.label,
            content=data.content,
            created_by=admin_id,
        )
        self.db.add(prompt)
        await self.db.flush()
        await self.db.refresh(prompt)
        return prompt

    async def update(self, prompt_id: str, data: SystemPromptUpdate) -> Optional[SystemPrompt]:
        """Update a system prompt's label and/or content."""
        prompt = await self._get_by_id(prompt_id)
        if not prompt:
            return None

        if data.label is not None:
            prompt.label = data.label
        if data.content is not None:
            prompt.content = data.content

        await self.db.flush()
        await self.db.refresh(prompt)
        return prompt

    async def delete(self, prompt_id: str) -> bool:
        """Soft-delete a system prompt."""
        prompt = await self._get_by_id(prompt_id)
        if not prompt:
            return False
        prompt.deleted_at = datetime.now(timezone.utc)
        prompt.is_active = False
        await self.db.flush()
        return True

    async def list_all(self, prompt_type: Optional[str] = None) -> List[SystemPrompt]:
        """List all system prompts, optionally filtered by type."""
        stmt = (
            select(SystemPrompt)
            .where(SystemPrompt.deleted_at.is_(None))
            .order_by(SystemPrompt.prompt_type, SystemPrompt.created_at)
        )
        if prompt_type:
            stmt = stmt.where(SystemPrompt.prompt_type == prompt_type)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def activate(self, prompt_id: str) -> Optional[SystemPrompt]:
        """Activate a prompt and deactivate all others of the same type."""
        prompt = await self._get_by_id(prompt_id)
        if not prompt:
            return None

        # Deactivate all prompts of the same type
        await self.db.execute(
            update(SystemPrompt)
            .where(SystemPrompt.prompt_type == prompt.prompt_type)
            .values(is_active=False)
        )
        # Activate the selected one
        prompt.is_active = True
        await self.db.flush()
        await self.db.refresh(prompt)
        return prompt

    async def deactivate(self, prompt_id: str) -> Optional[SystemPrompt]:
        """Deactivate a prompt (type will have no active prompt)."""
        prompt = await self._get_by_id(prompt_id)
        if not prompt:
            return None
        prompt.is_active = False
        await self.db.flush()
        await self.db.refresh(prompt)
        return prompt

    async def get_active(self, prompt_type: str) -> Optional[str]:
        """Get the active prompt content for a type. Returns None if no active prompt."""
        result = await self.db.execute(
            select(SystemPrompt)
            .where(
                SystemPrompt.prompt_type == prompt_type,
                SystemPrompt.is_active == True,
                SystemPrompt.deleted_at.is_(None),
            )
            .order_by(SystemPrompt.updated_at.desc())
            .limit(1)
        )
        prompt = result.scalar_one_or_none()
        return prompt.content if prompt else None

    async def _get_by_id(self, prompt_id: str) -> Optional[SystemPrompt]:
        result = await self.db.execute(
            select(SystemPrompt).where(
                SystemPrompt.id == prompt_id,
                SystemPrompt.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()
