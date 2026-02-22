"""
LLM Model registry routes.
Public GET endpoints for users + admin CRUD endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_active_user, get_current_admin_user
from app.users.models import User
from .service import LLMModelService
from .schemas import (
    LLMModelResponse,
    LLMModelBrief,
    LLMModelGroupedResponse,
    LLMModelCreate,
    LLMModelUpdate,
)

router = APIRouter(tags=["Models"])


# =============================================================================
# Public (user) routes
# =============================================================================

@router.get("/models", response_model=List[LLMModelGroupedResponse])
async def get_models_grouped(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all active models grouped by provider (for dropdowns)."""
    service = LLMModelService(db)
    groups = await service.get_all_grouped()
    return [
        LLMModelGroupedResponse(
            provider=g["provider"],
            provider_display_name=g["provider_display_name"],
            models=[
                LLMModelBrief(
                    id=m.id,
                    model_id=m.model_id,
                    display_name=m.display_name,
                    context_window=m.context_window,
                    max_output_tokens=m.max_output_tokens,
                    supports_vision=m.supports_vision,
                    supports_function_calling=m.supports_function_calling,
                )
                for m in g["models"]
            ],
        )
        for g in groups
    ]


@router.get("/models/{provider}", response_model=List[LLMModelBrief])
async def get_models_by_provider(
    provider: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get models for a specific provider."""
    service = LLMModelService(db)
    models = await service.get_models_by_provider(provider)
    return [
        LLMModelBrief(
            id=m.id,
            model_id=m.model_id,
            display_name=m.display_name,
            context_window=m.context_window,
            max_output_tokens=m.max_output_tokens,
            supports_vision=m.supports_vision,
            supports_function_calling=m.supports_function_calling,
        )
        for m in models
    ]


# =============================================================================
# Admin routes
# =============================================================================

@router.get("/admin/models", response_model=List[LLMModelResponse])
async def admin_list_models(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: get all models including inactive."""
    service = LLMModelService(db)
    models = await service.get_all()
    return [
        LLMModelResponse(
            id=m.id,
            provider=m.provider,
            model_id=m.model_id,
            display_name=m.display_name,
            context_window=m.context_window,
            max_output_tokens=m.max_output_tokens,
            supports_vision=m.supports_vision,
            supports_function_calling=m.supports_function_calling,
            supports_streaming=m.supports_streaming,
            input_cost_per_1m_cents=m.input_cost_per_1m_cents,
            output_cost_per_1m_cents=m.output_cost_per_1m_cents,
            margin_multiplier=float(m.margin_multiplier),
            is_active=m.is_active,
            is_custom=m.is_custom,
            sort_order=m.sort_order,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in models
    ]


@router.post("/admin/models", response_model=LLMModelResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_model(
    data: LLMModelCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: create a new model entry."""
    service = LLMModelService(db)

    # Check for duplicate
    existing = await service.get_model(data.provider, data.model_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Model {data.provider}/{data.model_id} already exists",
        )

    model = await service.create_model(data)
    await db.commit()

    return LLMModelResponse(
        id=model.id,
        provider=model.provider,
        model_id=model.model_id,
        display_name=model.display_name,
        context_window=model.context_window,
        max_output_tokens=model.max_output_tokens,
        supports_vision=model.supports_vision,
        supports_function_calling=model.supports_function_calling,
        supports_streaming=model.supports_streaming,
        input_cost_per_1m_cents=model.input_cost_per_1m_cents,
        output_cost_per_1m_cents=model.output_cost_per_1m_cents,
        margin_multiplier=float(model.margin_multiplier),
        is_active=model.is_active,
        is_custom=model.is_custom,
        sort_order=model.sort_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.put("/admin/models/{model_id}", response_model=LLMModelResponse)
async def admin_update_model(
    model_id: int,
    data: LLMModelUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: update a model (pricing, capabilities, etc.)."""
    service = LLMModelService(db)
    model = await service.update_model(model_id, data)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    await db.commit()

    return LLMModelResponse(
        id=model.id,
        provider=model.provider,
        model_id=model.model_id,
        display_name=model.display_name,
        context_window=model.context_window,
        max_output_tokens=model.max_output_tokens,
        supports_vision=model.supports_vision,
        supports_function_calling=model.supports_function_calling,
        supports_streaming=model.supports_streaming,
        input_cost_per_1m_cents=model.input_cost_per_1m_cents,
        output_cost_per_1m_cents=model.output_cost_per_1m_cents,
        margin_multiplier=float(model.margin_multiplier),
        is_active=model.is_active,
        is_custom=model.is_custom,
        sort_order=model.sort_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.delete("/admin/models/{model_id}")
async def admin_delete_model(
    model_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: delete a model (soft-delete for built-in, hard-delete for custom)."""
    service = LLMModelService(db)
    deleted = await service.delete_model(model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")

    await db.commit()
    return {"message": "Model deleted"}


@router.get("/admin/models/warnings")
async def admin_get_warnings(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: get models with $0 pricing."""
    service = LLMModelService(db)
    warnings = await service.get_zero_pricing_warnings()
    return {"warnings": warnings}
