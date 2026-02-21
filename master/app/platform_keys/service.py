"""
Platform API key service.
Manages encrypted platform-level LLM provider keys with in-memory caching.
"""

import logging
import time
from typing import Optional, Dict, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform_keys.models import PlatformApiKey
from app.platform_keys.schemas import PlatformKeyCreate, PlatformKeyUpdate
from app.api_keys.models import LLMProviderKey
from app.api_keys.encryption import encrypt_key, decrypt_key, mask_key, test_provider_key

logger = logging.getLogger(__name__)

# In-memory cache for decrypted platform keys
_cache: Dict[str, str] = {}  # {provider: decrypted_key}
_cache_models: Dict[str, str] = {}  # {provider: model_name}
_cache_base_urls: Dict[str, str] = {}  # {provider: base_url}
_cache_default: Optional[str] = None  # default provider
_cache_ts: float = 0
_CACHE_TTL = 300  # 5 minutes


def _invalidate_cache():
    """Clear the in-memory key cache."""
    global _cache, _cache_models, _cache_base_urls, _cache_default, _cache_ts
    _cache = {}
    _cache_models = {}
    _cache_base_urls = {}
    _cache_default = None
    _cache_ts = 0


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
            model_name=data.model_name,
            base_url=data.base_url,
            created_by=admin_id,
        )
        self.db.add(key)
        await self.db.flush()
        await self.db.refresh(key)
        _invalidate_cache()
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
        if data.model_name is not None:
            key.model_name = data.model_name
        if data.base_url is not None:
            key.base_url = data.base_url

        await self.db.flush()
        await self.db.refresh(key)
        _invalidate_cache()
        return key

    async def delete(self, key_id: str) -> bool:
        """Delete a platform API key."""
        key = await self._get_by_id(key_id)
        if not key:
            return False
        await self.db.delete(key)
        await self.db.flush()
        _invalidate_cache()
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
        _invalidate_cache()
        return key

    async def deactivate(self, key_id: str) -> Optional[PlatformApiKey]:
        """Deactivate a key (provider will have no active key)."""
        key = await self._get_by_id(key_id)
        if not key:
            return None
        key.is_active = False
        await self.db.flush()
        await self.db.refresh(key)
        _invalidate_cache()
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
        _invalidate_cache()
        return key

    # ── Key retrieval (cached) ────────────────────────────────────────

    async def get_active_key(self, provider: str) -> Optional[str]:
        """Get decrypted active key for a provider. Uses cache."""
        keys = await self.get_all_active_keys()
        return keys.get(provider)

    async def get_all_active_keys(self) -> Dict[str, str]:
        """Get all active decrypted keys. Returns {provider: key}. Cached 5 min."""
        global _cache, _cache_ts
        if _cache and (time.time() - _cache_ts) < _CACHE_TTL:
            return dict(_cache)

        result = await self.db.execute(
            select(PlatformApiKey).where(PlatformApiKey.is_active == True)
        )
        keys = result.scalars().all()

        new_cache = {}
        new_models = {}
        new_base_urls = {}
        new_default = None
        for k in keys:
            try:
                new_cache[k.provider.value] = decrypt_key(k.api_key_encrypted)
                if k.model_name:
                    new_models[k.provider.value] = k.model_name
                if k.base_url:
                    new_base_urls[k.provider.value] = k.base_url
                if k.is_default:
                    new_default = k.provider.value
            except Exception as e:
                logger.error(f"Failed to decrypt platform key {k.id}: {e}")

        global _cache_models, _cache_base_urls, _cache_default
        _cache = new_cache
        _cache_models = new_models
        _cache_base_urls = new_base_urls
        _cache_default = new_default
        _cache_ts = time.time()
        return dict(_cache)

    async def get_active_models(self) -> Dict[str, str]:
        """Get model names for active keys. Returns {provider: model}. Cached."""
        await self.get_all_active_keys()  # ensures cache is fresh
        return dict(_cache_models)

    async def get_active_base_urls(self) -> Dict[str, str]:
        """Get base URLs for active keys. Returns {provider: base_url}. Cached."""
        await self.get_all_active_keys()  # ensures cache is fresh
        return dict(_cache_base_urls)

    async def get_default_provider(self) -> Optional[str]:
        """Get the default provider name. Cached."""
        await self.get_all_active_keys()  # ensures cache is fresh
        return _cache_default

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

        valid = await self._test_key(key.provider.value, decrypted)
        return {"valid": valid, "error": None if valid else "Key validation failed"}

    # ── Private helpers ───────────────────────────────────────────────

    async def _get_by_id(self, key_id: str) -> Optional[PlatformApiKey]:
        result = await self.db.execute(
            select(PlatformApiKey).where(PlatformApiKey.id == key_id)
        )
        return result.scalar_one_or_none()

    async def _test_key(self, provider: str, api_key: str) -> bool:
        """Test if an API key is valid with a lightweight request."""
        return await test_provider_key(provider, api_key)
