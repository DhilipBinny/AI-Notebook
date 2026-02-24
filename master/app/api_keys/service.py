"""
API key service - manages user-owned LLM API keys.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List, Dict
from datetime import datetime, timezone
import logging

from .models import UserApiKey, LLMProviderKey
from .encryption import encrypt_key, decrypt_key, mask_key, test_provider_key
from .schemas import ApiKeyCreate, ApiKeyUpdate

logger = logging.getLogger(__name__)


class ApiKeyService:
    """Service class for API key operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_or_update(self, user_id: str, data: ApiKeyCreate) -> UserApiKey:
        """Create or update an API key for a provider (upsert)."""
        existing = await self._get_by_provider(user_id, data.provider)

        if existing:
            # Update existing key
            existing.api_key_encrypted = encrypt_key(data.api_key) if data.api_key else encrypt_key("")
            existing.api_key_hint = mask_key(data.api_key) if data.api_key else "(none)"
            existing.model_override = data.model_override
            if hasattr(data, 'base_url'):
                existing.base_url = data.base_url
            existing.is_validated = False
            existing.is_active = True
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        # Create new
        encrypted = encrypt_key(data.api_key) if data.api_key else encrypt_key("")
        hint = mask_key(data.api_key) if data.api_key else "(none)"
        api_key = UserApiKey(
            user_id=user_id,
            provider=LLMProviderKey(data.provider),
            api_key_encrypted=encrypted,
            api_key_hint=hint,
            model_override=data.model_override,
            base_url=getattr(data, 'base_url', None),
        )
        self.db.add(api_key)
        await self.db.flush()
        await self.db.refresh(api_key)
        return api_key

    async def update(self, key_id: str, user_id: str, data: ApiKeyUpdate) -> Optional[UserApiKey]:
        """Update an API key."""
        api_key = await self._get_by_id(key_id, user_id)
        if not api_key:
            return None

        if data.api_key is not None:
            api_key.api_key_encrypted = encrypt_key(data.api_key)
            api_key.api_key_hint = mask_key(data.api_key)
            api_key.is_validated = False

        if data.model_override is not None:
            api_key.model_override = data.model_override

        if data.is_active is not None:
            api_key.is_active = data.is_active

        await self.db.flush()
        await self.db.refresh(api_key)
        return api_key

    async def delete(self, key_id: str, user_id: str) -> bool:
        """Delete an API key."""
        api_key = await self._get_by_id(key_id, user_id)
        if not api_key:
            return False
        await self.db.delete(api_key)
        await self.db.flush()
        return True

    async def get_for_user(self, user_id: str) -> List[UserApiKey]:
        """List all API keys for a user."""
        result = await self.db.execute(
            select(UserApiKey)
            .where(UserApiKey.user_id == user_id)
            .order_by(UserApiKey.provider)
        )
        return list(result.scalars().all())

    async def get_decrypted_key(self, user_id: str, provider: str) -> Optional[str]:
        """Get decrypted API key for a specific provider."""
        api_key = await self._get_by_provider(user_id, provider)
        if not api_key or not api_key.is_active:
            return None
        try:
            return decrypt_key(api_key.api_key_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt key for user {user_id}, provider {provider}: {e}")
            return None

    async def get_all_decrypted_keys(self, user_id: str) -> Dict[str, str]:
        """Get all active decrypted keys for a user. Returns {provider: key}."""
        keys = await self.get_for_user(user_id)
        result = {}
        for key in keys:
            if key.is_active:
                try:
                    result[key.provider.value] = decrypt_key(key.api_key_encrypted)
                except Exception as e:
                    logger.error(f"Failed to decrypt key {key.id}: {e}")
        return result

    async def validate_key(self, key_id: str, user_id: str) -> dict:
        """Validate an API key by making a lightweight API call."""
        api_key = await self._get_by_id(key_id, user_id)
        if not api_key:
            return {"valid": False, "error": "Key not found"}

        try:
            decrypted = decrypt_key(api_key.api_key_encrypted)
        except Exception:
            return {"valid": False, "error": "Failed to decrypt key"}

        valid = await self._test_key(api_key.provider.value, decrypted)

        api_key.is_validated = valid
        api_key.last_validated_at = datetime.now(timezone.utc)
        await self.db.flush()

        return {"valid": valid, "error": None if valid else "Key validation failed"}

    async def get_available_providers(self, user_id: str) -> List[dict]:
        """Get available providers with model lists for a user."""
        from app.platform_keys.service import PlatformKeyService
        from app.llm_models.service import LLMModelService, PROVIDER_DISPLAY_NAMES

        user_keys = await self.get_for_user(user_id)
        user_key_providers = {k.provider.value for k in user_keys if k.is_active}

        # Platform keys available (from DB)
        pk_service = PlatformKeyService(self.db)
        active_platform_keys = await pk_service.get_all_active_keys()
        platform_key_providers = set(active_platform_keys.keys())
        platform_models = await pk_service.get_active_models()
        default_provider = await pk_service.get_default_provider()
        user_visible = await pk_service.get_user_visible_providers()

        # Get models from registry
        model_service = LLMModelService(self.db)
        grouped = await model_service.get_all_grouped()
        provider_models = {
            g["provider"]: [
                {"id": m.model_id, "name": m.display_name}
                for m in g["models"]
            ]
            for g in grouped
        }

        providers = []
        for provider in provider_models:
            has_own = provider in user_key_providers
            has_platform = provider in platform_key_providers
            # Skip providers hidden by admin (unless user has their own key)
            if has_platform and not has_own and not user_visible.get(provider, True):
                continue
            if has_own or has_platform:
                providers.append({
                    "provider": provider,
                    "display_name": PROVIDER_DISPLAY_NAMES.get(provider, provider),
                    "has_key": True,
                    "is_own_key": has_own,
                    "is_default": provider == default_provider,
                    "active_model": platform_models.get(provider),
                    "models": provider_models[provider],
                })

        return providers

    async def _get_by_id(self, key_id: str, user_id: str) -> Optional[UserApiKey]:
        """Get API key by ID for a specific user."""
        result = await self.db.execute(
            select(UserApiKey).where(
                UserApiKey.id == key_id,
                UserApiKey.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_by_provider(self, user_id: str, provider: str) -> Optional[UserApiKey]:
        """Get API key by provider for a specific user."""
        result = await self.db.execute(
            select(UserApiKey).where(
                UserApiKey.user_id == user_id,
                UserApiKey.provider == provider,
            )
        )
        return result.scalar_one_or_none()

    async def _test_key(self, provider: str, api_key: str) -> bool:
        """Test if an API key is valid with a lightweight request."""
        return await test_provider_key(provider, api_key)
