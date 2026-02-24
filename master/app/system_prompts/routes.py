"""
System prompt admin routes.
All endpoints require admin authentication.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_admin_user
from app.users.models import User
from app.system_prompts.schemas import SystemPromptCreate, SystemPromptUpdate, SystemPromptResponse
from app.system_prompts.service import SystemPromptService

router = APIRouter(prefix="/admin/system-prompts", tags=["Admin - System Prompts"])


@router.post("/", response_model=SystemPromptResponse, status_code=status.HTTP_201_CREATED)
async def create_system_prompt(
    data: SystemPromptCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new system prompt."""
    service = SystemPromptService(db)
    prompt = await service.create(data, current_user.id)
    return prompt


@router.get("/", response_model=List[SystemPromptResponse])
async def list_system_prompts(
    prompt_type: Optional[str] = Query(None, pattern="^(chat_panel|ai_cell)$"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all system prompts, optionally filtered by type."""
    service = SystemPromptService(db)
    prompts = await service.list_all(prompt_type=prompt_type)
    return prompts


@router.put("/{prompt_id}", response_model=SystemPromptResponse)
async def update_system_prompt(
    prompt_id: str,
    data: SystemPromptUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a system prompt's label and/or content."""
    service = SystemPromptService(db)
    prompt = await service.update(prompt_id, data)
    if not prompt:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return prompt


@router.delete("/{prompt_id}")
async def delete_system_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a system prompt."""
    service = SystemPromptService(db)
    deleted = await service.delete(prompt_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return {"message": "System prompt deleted"}


@router.post("/{prompt_id}/activate", response_model=SystemPromptResponse)
async def activate_system_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Activate this prompt (deactivates all others of the same type)."""
    service = SystemPromptService(db)
    prompt = await service.activate(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return prompt


@router.post("/{prompt_id}/deactivate", response_model=SystemPromptResponse)
async def deactivate_system_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate this prompt (type will have no active prompt, falls back to hardcoded default)."""
    service = SystemPromptService(db)
    prompt = await service.deactivate(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return prompt
