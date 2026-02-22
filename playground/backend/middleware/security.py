"""
Security Middleware - Authentication and authorization
"""

import os
import logging
from typing import Optional, Tuple
from fastapi import HTTPException, Header, Request

logger = logging.getLogger(__name__)

# Get internal secret from environment (set by Master when spawning container)
INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "")

# Explicit dev mode opt-in: set PLAYGROUND_DEV_MODE=1 to bypass auth
DEV_MODE = os.getenv("PLAYGROUND_DEV_MODE", "").strip() in ("1", "true", "yes")

if not INTERNAL_SECRET and not DEV_MODE:
    logger.warning(
        "INTERNAL_SECRET is not set and PLAYGROUND_DEV_MODE is not enabled. "
        "All requests will be rejected. Set INTERNAL_SECRET for production or "
        "PLAYGROUND_DEV_MODE=1 for local development."
    )


async def verify_internal_secret(x_internal_secret: str = Header(None)):
    """
    Verify requests come from Master API.

    Requires INTERNAL_SECRET to be set. Only bypasses auth if
    PLAYGROUND_DEV_MODE=1 is explicitly set in the environment.
    """
    if DEV_MODE:
        return True

    if not INTERNAL_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Playground not configured: INTERNAL_SECRET not set"
        )

    if x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Invalid internal secret")

    return True


def extract_key_overrides(request: Request, provider: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Extract API key, model, base_url, and auth_type overrides from request headers.

    Resolution order: user key > platform key > None (falls back to env).

    Args:
        request: FastAPI Request object
        provider: LLM provider name (gemini, openai, anthropic, openai_compatible)

    Returns:
        Tuple of (api_key_override, model_override, base_url_override, auth_type) - any may be None
    """
    provider_upper = provider.capitalize()
    if provider == "openai":
        provider_upper = "OpenAI"
    elif provider == "anthropic":
        provider_upper = "Anthropic"
    elif provider == "gemini":
        provider_upper = "Gemini"
    elif provider == "openai_compatible":
        provider_upper = "OpenaiCompatible"

    # User key takes priority over platform key
    user_key = request.headers.get(f"x-user-{provider_upper.lower()}-key") or \
               request.headers.get(f"X-User-{provider_upper}-Key")
    platform_key = request.headers.get(f"x-platform-{provider_upper.lower()}-key") or \
                   request.headers.get(f"X-Platform-{provider_upper}-Key")
    platform_model = request.headers.get(f"x-platform-{provider_upper.lower()}-model") or \
                     request.headers.get(f"X-Platform-{provider_upper}-Model")

    api_key = user_key or platform_key or None
    model = platform_model if not user_key else None  # Only use platform model if not using user's own key

    # Extract base_url override (for openai_compatible provider)
    base_url = None
    if provider == "openai_compatible":
        user_base_url = request.headers.get("x-user-openaicompatible-baseurl") or \
                        request.headers.get("X-User-OpenaiCompatible-BaseUrl")
        platform_base_url = request.headers.get("x-platform-openaicompatible-baseurl") or \
                            request.headers.get("X-Platform-OpenaiCompatible-BaseUrl")
        base_url = user_base_url or platform_base_url or None

    # Extract auth_type for anthropic (OAuth token support)
    # Only applies when using platform key (user keys are always api_key type)
    auth_type = None
    if provider == "anthropic" and not user_key and platform_key:
        auth_type = request.headers.get("x-platform-anthropic-authtype") or \
                    request.headers.get("X-Platform-Anthropic-AuthType")

    return api_key, model, base_url, auth_type
