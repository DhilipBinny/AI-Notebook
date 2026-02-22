"""
LLM Model registry service - CRUD and queries for the llm_models table.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from decimal import Decimal
import logging

from .models import LLMModel
from .schemas import LLMModelCreate, LLMModelUpdate

logger = logging.getLogger(__name__)

PROVIDER_DISPLAY_NAMES = {
    "openai": "OpenAI",
    "anthropic": "Anthropic Claude",
    "gemini": "Google Gemini",
    "openai_compatible": "OpenAI Compatible",
}


class LLMModelService:
    """Service for LLM model registry operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_models_by_provider(self, provider: str) -> List[LLMModel]:
        """Get active models for a provider, ordered by sort_order."""
        result = await self.db.execute(
            select(LLMModel)
            .where(LLMModel.provider == provider, LLMModel.is_active == True)
            .order_by(LLMModel.sort_order, LLMModel.display_name)
        )
        return list(result.scalars().all())

    async def get_all_active(self) -> List[LLMModel]:
        """Get all active models."""
        result = await self.db.execute(
            select(LLMModel)
            .where(LLMModel.is_active == True)
            .order_by(LLMModel.provider, LLMModel.sort_order, LLMModel.display_name)
        )
        return list(result.scalars().all())

    async def get_all(self) -> List[LLMModel]:
        """Get all models including inactive (admin view)."""
        result = await self.db.execute(
            select(LLMModel)
            .order_by(LLMModel.provider, LLMModel.sort_order, LLMModel.display_name)
        )
        return list(result.scalars().all())

    async def get_all_grouped(self) -> List[dict]:
        """Get all active models grouped by provider with display names."""
        models = await self.get_all_active()
        groups: dict[str, list] = {}
        for m in models:
            groups.setdefault(m.provider, []).append(m)

        result = []
        for provider in ["openai", "anthropic", "gemini", "openai_compatible"]:
            if provider in groups:
                result.append({
                    "provider": provider,
                    "provider_display_name": PROVIDER_DISPLAY_NAMES.get(provider, provider),
                    "models": groups[provider],
                })
        # Include any providers not in the predefined order
        for provider, provider_models in groups.items():
            if provider not in ["openai", "anthropic", "gemini", "openai_compatible"]:
                result.append({
                    "provider": provider,
                    "provider_display_name": PROVIDER_DISPLAY_NAMES.get(provider, provider),
                    "models": provider_models,
                })
        return result

    async def get_model(self, provider: str, model_id: str) -> Optional[LLMModel]:
        """Get a single model by provider and model_id."""
        result = await self.db.execute(
            select(LLMModel).where(
                LLMModel.provider == provider,
                LLMModel.model_id == model_id,
                LLMModel.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_model_by_id(self, model_db_id: int) -> Optional[LLMModel]:
        """Get a model by its database ID."""
        result = await self.db.execute(
            select(LLMModel).where(LLMModel.id == model_db_id)
        )
        return result.scalar_one_or_none()

    async def ensure_model_exists(
        self, provider: str, model_id: str, display_name: Optional[str] = None
    ) -> tuple[LLMModel, bool]:
        """Upsert: ensure a model entry exists. Creates with is_custom=True and $0 pricing if missing.

        Returns:
            (model, created) - created is True if a new row was inserted.
        """
        existing = await self.get_model(provider, model_id)
        if existing:
            return existing, False

        # Also check inactive models
        result = await self.db.execute(
            select(LLMModel).where(
                LLMModel.provider == provider,
                LLMModel.model_id == model_id,
            )
        )
        inactive = result.scalar_one_or_none()
        if inactive:
            inactive.is_active = True
            await self.db.flush()
            return inactive, False

        model = LLMModel(
            provider=provider,
            model_id=model_id,
            display_name=display_name or model_id,
            input_cost_per_1m_cents=0,
            output_cost_per_1m_cents=0,
            margin_multiplier=Decimal("1.00"),
            is_active=True,
            is_custom=True,
        )
        self.db.add(model)
        await self.db.flush()
        return model, True

    async def create_model(self, data: LLMModelCreate) -> LLMModel:
        """Admin: create a new model."""
        model = LLMModel(
            provider=data.provider,
            model_id=data.model_id,
            display_name=data.display_name,
            context_window=data.context_window,
            max_output_tokens=data.max_output_tokens,
            supports_vision=data.supports_vision,
            supports_function_calling=data.supports_function_calling,
            supports_streaming=data.supports_streaming,
            input_cost_per_1m_cents=data.input_cost_per_1m_cents,
            output_cost_per_1m_cents=data.output_cost_per_1m_cents,
            margin_multiplier=Decimal(str(data.margin_multiplier)),
            is_custom=data.is_custom,
            sort_order=data.sort_order,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def update_model(self, model_db_id: int, data: LLMModelUpdate) -> Optional[LLMModel]:
        """Admin: update a model."""
        model = await self.get_model_by_id(model_db_id)
        if not model:
            return None

        if data.display_name is not None:
            model.display_name = data.display_name
        if data.context_window is not None:
            model.context_window = data.context_window
        if data.max_output_tokens is not None:
            model.max_output_tokens = data.max_output_tokens
        if data.supports_vision is not None:
            model.supports_vision = data.supports_vision
        if data.supports_function_calling is not None:
            model.supports_function_calling = data.supports_function_calling
        if data.supports_streaming is not None:
            model.supports_streaming = data.supports_streaming
        if data.input_cost_per_1m_cents is not None:
            model.input_cost_per_1m_cents = data.input_cost_per_1m_cents
        if data.output_cost_per_1m_cents is not None:
            model.output_cost_per_1m_cents = data.output_cost_per_1m_cents
        if data.margin_multiplier is not None:
            model.margin_multiplier = Decimal(str(data.margin_multiplier))
        if data.is_active is not None:
            model.is_active = data.is_active
        if data.sort_order is not None:
            model.sort_order = data.sort_order

        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def delete_model(self, model_db_id: int) -> bool:
        """Delete a model. Hard-delete if is_custom, otherwise soft-delete (is_active=False)."""
        model = await self.get_model_by_id(model_db_id)
        if not model:
            return False

        if model.is_custom:
            await self.db.delete(model)
        else:
            model.is_active = False

        await self.db.flush()
        return True

    async def get_zero_pricing_warnings(self) -> List[dict]:
        """Get models with $0 pricing (users won't be charged)."""
        result = await self.db.execute(
            select(LLMModel).where(
                LLMModel.is_active == True,
                LLMModel.input_cost_per_1m_cents == 0,
                LLMModel.output_cost_per_1m_cents == 0,
            ).order_by(LLMModel.provider, LLMModel.model_id)
        )
        entries = result.scalars().all()
        return [
            {"provider": e.provider, "model_id": e.model_id, "display_name": e.display_name}
            for e in entries
            if not (e.provider == "openai_compatible" and e.model_id == "custom")
        ]
