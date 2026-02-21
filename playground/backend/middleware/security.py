"""
Security Middleware - Authentication and authorization
"""

import os
import logging
from fastapi import HTTPException, Header

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
