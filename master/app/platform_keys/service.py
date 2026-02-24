"""
Platform API key service.
Manages encrypted platform-level LLM provider keys.
"""

import logging
from typing import Optional, Dict, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform_keys.models import PlatformApiKey, AuthType
from app.platform_keys.schemas import PlatformKeyCreate, PlatformKeyUpdate
from app.api_keys.models import LLMProviderKey
from app.api_keys.encryption import encrypt_key, decrypt_key, mask_key, test_provider_key
from app.llm_models.service import LLMModelService

logger = logging.getLogger(__name__)

# Standard providers that require model validation against registry
_STANDARD_PROVIDERS = {"openai", "anthropic", "gemini"}


class PlatformKeyService:
    """Service for platform-level API key operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────

    async def create(self, data: PlatformKeyCreate, admin_id: str) -> PlatformApiKey:
        """Create a new platform API key."""
        encrypted = encrypt_key(data.api_key) if data.api_key else encrypt_key("")
        hint = mask_key(data.api_key) if data.api_key else "(none)"
        key = PlatformApiKey(
            provider=LLMProviderKey(data.provider),
            label=data.label,
            api_key_encrypted=encrypted,
            api_key_hint=hint,
            auth_type=AuthType(data.auth_type),
            model_name=data.model_name,
            base_url=data.base_url,
            created_by=admin_id,
        )
        self.db.add(key)
        await self.db.flush()
        await self.db.refresh(key)

        # Auto-register model in registry if model is specified
        model_created = False
        if data.model_name:
            model_service = LLMModelService(self.db)

            if data.provider in _STANDARD_PROVIDERS:
                # Standard providers: validate model exists in registry
                existing = await model_service.get_model(data.provider, data.model_name)
                if not existing:
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=400,
                        detail=f"Model '{data.model_name}' is not in the model registry for provider '{data.provider}'. "
                               f"Add it via the Model Registry first.",
                    )
            else:
                # openai_compatible: auto-create if not exists
                _, model_created = await model_service.ensure_model_exists(
                    data.provider, data.model_name
                )

        key._model_created = model_created  # transient flag for response
        return key

    async def update(self, key_id: str, data: PlatformKeyUpdate) -> Optional[PlatformApiKey]:
        """Update a platform API key."""
        key = await self._get_by_id(key_id)
        if not key:
            return None

        if data.label is not None:
            key.label = data.label
        if data.api_key is not None:
            key.api_key_encrypted = encrypt_key(data.api_key) if data.api_key else encrypt_key("")
            key.api_key_hint = mask_key(data.api_key) if data.api_key else "(none)"
        if data.auth_type is not None:
            key.auth_type = AuthType(data.auth_type)
        if data.model_name is not None:
            key.model_name = data.model_name
        if data.base_url is not None:
            key.base_url = data.base_url

        await self.db.flush()
        await self.db.refresh(key)

        # Auto-register model in registry if model changed
        model_created = False
        if data.model_name:
            provider = key.provider.value
            model_service = LLMModelService(self.db)

            if provider in _STANDARD_PROVIDERS:
                existing = await model_service.get_model(provider, data.model_name)
                if not existing:
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=400,
                        detail=f"Model '{data.model_name}' is not in the model registry for provider '{provider}'. "
                               f"Add it via the Model Registry first.",
                    )
            else:
                _, model_created = await model_service.ensure_model_exists(
                    provider, data.model_name
                )

        key._model_created = model_created  # transient flag for response
        return key

    async def delete(self, key_id: str) -> bool:
        """Delete a platform API key."""
        key = await self._get_by_id(key_id)
        if not key:
            return False
        await self.db.delete(key)
        await self.db.flush()
        return True

    async def list_all(self, provider: Optional[str] = None) -> List[PlatformApiKey]:
        """List all platform keys, optionally filtered by provider."""
        stmt = select(PlatformApiKey).order_by(PlatformApiKey.provider, PlatformApiKey.priority.desc())
        if provider:
            stmt = stmt.where(PlatformApiKey.provider == provider)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Activation / Default ──────────────────────────────────────────

    async def activate(self, key_id: str) -> Optional[PlatformApiKey]:
        """Activate a key and deactivate all others for the same provider."""
        key = await self._get_by_id(key_id)
        if not key:
            return None

        # Deactivate all keys for this provider
        await self.db.execute(
            update(PlatformApiKey)
            .where(PlatformApiKey.provider == key.provider)
            .values(is_active=False)
        )
        # Activate the selected one
        key.is_active = True
        await self.db.flush()
        await self.db.refresh(key)
        return key

    async def deactivate(self, key_id: str) -> Optional[PlatformApiKey]:
        """Deactivate a key (provider will have no active key)."""
        key = await self._get_by_id(key_id)
        if not key:
            return None
        key.is_active = False
        await self.db.flush()
        await self.db.refresh(key)
        return key

    async def set_default(self, key_id: str) -> Optional[PlatformApiKey]:
        """Set a key's provider as the default. Clears is_default on all others."""
        key = await self._get_by_id(key_id)
        if not key:
            return None

        # Clear all defaults
        await self.db.execute(
            update(PlatformApiKey).values(is_default=False)
        )
        # Set this one
        key.is_default = True
        # Also ensure it's active
        await self.db.execute(
            update(PlatformApiKey)
            .where(PlatformApiKey.provider == key.provider)
            .values(is_active=False)
        )
        key.is_active = True
        await self.db.flush()
        await self.db.refresh(key)
        return key

    # ── Key retrieval (direct DB query) ───────────────────────────────

    async def _fetch_active_keys(self) -> List[PlatformApiKey]:
        """Fetch all active platform keys from DB."""
        result = await self.db.execute(
            select(PlatformApiKey).where(PlatformApiKey.is_active == True)
        )
        return list(result.scalars().all())

    async def get_active_key(self, provider: str) -> Optional[str]:
        """Get decrypted active key for a provider."""
        keys = await self.get_all_active_keys()
        return keys.get(provider)

    async def get_all_active_keys(self) -> Dict[str, str]:
        """Get all active decrypted keys. Returns {provider: key}."""
        keys = await self._fetch_active_keys()
        result = {}
        for k in keys:
            try:
                result[k.provider.value] = decrypt_key(k.api_key_encrypted)
            except Exception as e:
                logger.error(f"Failed to decrypt platform key {k.id}: {e}")
        return result

    async def get_active_models(self) -> Dict[str, str]:
        """Get model names for active keys. Returns {provider: model}."""
        keys = await self._fetch_active_keys()
        return {k.provider.value: k.model_name for k in keys if k.model_name}

    async def get_active_base_urls(self) -> Dict[str, str]:
        """Get base URLs for active keys. Returns {provider: base_url}."""
        keys = await self._fetch_active_keys()
        return {k.provider.value: k.base_url for k in keys if k.base_url}

    async def get_active_auth_types(self) -> Dict[str, str]:
        """Get auth types for active keys. Returns {provider: auth_type}."""
        keys = await self._fetch_active_keys()
        return {k.provider.value: (k.auth_type.value if k.auth_type else "api_key") for k in keys}

    async def get_default_provider(self) -> Optional[str]:
        """Get the default provider name."""
        keys = await self._fetch_active_keys()
        for k in keys:
            if k.is_default:
                return k.provider.value
        return None

    async def get_user_visible_providers(self) -> Dict[str, bool]:
        """Get user_visible flags for active keys. Returns {provider: bool}."""
        keys = await self._fetch_active_keys()
        return {k.provider.value: k.user_visible for k in keys}

    async def toggle_provider_visibility(self, provider: str, visible: bool) -> bool:
        """Toggle user_visible on all keys for a provider."""
        result = await self.db.execute(
            select(PlatformApiKey).where(PlatformApiKey.provider == provider)
        )
        provider_keys = result.scalars().all()
        if not provider_keys:
            return False
        await self.db.execute(
            update(PlatformApiKey)
            .where(PlatformApiKey.provider == provider)
            .values(user_visible=visible)
        )
        await self.db.flush()
        return True

    # ── Validation ────────────────────────────────────────────────────

    async def validate_key(self, key_id: str) -> dict:
        """Validate a platform API key with a lightweight API call."""
        key = await self._get_by_id(key_id)
        if not key:
            return {"valid": False, "error": "Key not found"}

        try:
            decrypted = decrypt_key(key.api_key_encrypted)
        except Exception:
            return {"valid": False, "error": "Failed to decrypt key"}

        auth_type = key.auth_type.value if key.auth_type else "api_key"
        valid = await self._test_key(key.provider.value, decrypted, auth_type)
        return {"valid": valid, "error": None if valid else "Key validation failed"}

    # ── Private helpers ───────────────────────────────────────────────

    async def _get_by_id(self, key_id: str) -> Optional[PlatformApiKey]:
        result = await self.db.execute(
            select(PlatformApiKey).where(PlatformApiKey.id == key_id)
        )
        return result.scalar_one_or_none()

    async def _test_key(self, provider: str, api_key: str, auth_type: str = "api_key") -> bool:
        """Test if an API key is valid with a lightweight request."""
        return await test_provider_key(provider, api_key, auth_type=auth_type)
