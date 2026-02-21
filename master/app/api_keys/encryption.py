"""
Fernet encryption and shared utilities for API keys.
"""

from cryptography.fernet import Fernet
from app.core.config import settings
import logging
import httpx

logger = logging.getLogger(__name__)

_fernet = None


def _get_fernet() -> Fernet:
    """Get or create Fernet instance."""
    global _fernet
    if _fernet is None:
        key = settings.encryption_key
        if not key:
            raise ValueError(
                "ENCRYPTION_KEY not configured. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_key(api_key: str) -> str:
    """Encrypt an API key for storage."""
    f = _get_fernet()
    return f.encrypt(api_key.encode()).decode()


def decrypt_key(encrypted: str) -> str:
    """Decrypt an API key from storage."""
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()


def mask_key(api_key: str) -> str:
    """Create a masked display hint for an API key.
    e.g., 'sk-proj-abc...xyz' → 'sk-...xyz'
    """
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:3]}...{api_key[-4:]}"


async def test_provider_key(provider: str, api_key: str) -> bool:
    """Test if an API key is valid with a lightweight request.

    Shared by both user API key and platform API key validation.

    TODO (beta): This validation needs improvement:
    - openai_compatible: Currently skips validation entirely. Should accept base_url
      param and ping {base_url}/models to verify connectivity.
    - anthropic: Uses hardcoded model "claude-3-5-sonnet-20241022". Should use a
      models list endpoint or the configured model from platform_api_keys.
    - All providers: Only returns bool. Should return error details (status code,
      error message) so the UI can show *why* validation failed.
    - Should accept base_url parameter for openai_compatible provider testing.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # TODO: Should use /v1/models only (lightweight). Currently works but
            # returns full model list which is wasteful.
            if provider == "openai":
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                return resp.status_code == 200

            # TODO: Uses hardcoded model. Should use models list endpoint instead,
            # or accept configured model. Also 400 = valid key but bad request body,
            # which is a fragile check.
            elif provider == "anthropic":
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-5-sonnet-20241022",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )
                return resp.status_code in (200, 400)

            elif provider == "gemini":
                resp = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                )
                return resp.status_code == 200

            # TODO: Should accept base_url and ping {base_url}/models to verify
            # the endpoint is reachable and responding.
            elif provider == "openai_compatible":
                return True

    except Exception as e:
        logger.warning(f"Key validation failed for {provider}: {e}")
        return False
