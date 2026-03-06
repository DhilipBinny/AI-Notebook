"""
System prompt admin routes.
All endpoints require admin authentication.
"""

import logging
from itertools import groupby
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_admin_user, get_current_active_user
from app.users.models import User
from app.system_prompts.schemas import (
    SystemPromptCreate, SystemPromptUpdate, SystemPromptResponse,
    AICellModeResponse, ToolCatalogItem, ToolCatalogGroup,
    ToolCatalogCreate, ToolCatalogUpdate,
)
from app.system_prompts.service import SystemPromptService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/system-prompts", tags=["Admin - System Prompts"])

# Public endpoint (authenticated, not admin)
public_router = APIRouter(tags=["System Prompts"])


@public_router.get("/ai-cell-modes", response_model=List[AICellModeResponse])
async def get_ai_cell_modes(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get available AI Cell modes for the notebook dropdown."""
    service = SystemPromptService(db)
    modes = await service.list_active_modes()
    return modes


# --- Tool Catalog endpoints ---

@router.get("/tool-catalog", response_model=List[ToolCatalogGroup])
async def get_tool_catalog(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all AI Cell tools from the DB catalog, grouped by category."""
    service = SystemPromptService(db)
    tools = await service.list_tool_catalog()
    # Group by category
    groups = []
    for category, items in groupby(tools, key=lambda t: t.category):
        groups.append(ToolCatalogGroup(
            category=category,
            tools=[ToolCatalogItem.model_validate(t) for t in items],
        ))
    return groups


@router.get("/tool-catalog/flat", response_model=List[ToolCatalogItem])
async def get_tool_catalog_flat(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all tools as a flat list."""
    service = SystemPromptService(db)
    tools = await service.list_tool_catalog()
    return tools


@router.post("/tool-catalog", response_model=ToolCatalogItem, status_code=status.HTTP_201_CREATED)
async def add_tool_to_catalog(
    data: ToolCatalogCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a new tool to the catalog (e.g., when a new tool is added to the playground)."""
    service = SystemPromptService(db)
    try:
        tool = await service.add_tool(data)
        return tool
    except Exception as e:
        if "Duplicate" in str(e) or "1062" in str(e):
            raise HTTPException(status_code=409, detail=f"Tool '{data.name}' already exists in catalog")
        raise


@router.put("/tool-catalog/{tool_name}", response_model=ToolCatalogItem)
async def update_tool_in_catalog(
    tool_name: str,
    data: ToolCatalogUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a tool's metadata in the catalog."""
    service = SystemPromptService(db)
    tool = await service.update_tool(tool_name, data)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found in catalog")
    return tool


@router.delete("/tool-catalog/{tool_name}")
async def delete_tool_from_catalog(
    tool_name: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a tool from the catalog."""
    service = SystemPromptService(db)
    deleted = await service.delete_tool(tool_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tool not found in catalog")
    return {"message": f"Tool '{tool_name}' deleted from catalog"}


# --- System Prompt CRUD endpoints ---

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
