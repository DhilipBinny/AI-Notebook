"""
Security Middleware - Authentication and authorization
"""

import os
from fastapi import HTTPException, Header

# Get internal secret from environment (set by Master when spawning container)
INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "")


async def verify_internal_secret(x_internal_secret: str = Header(None)):
    """
    Verify requests come from Master API.

    In development mode (no secret configured), allows all requests.
    In production, requires matching X-Internal-Secret header.
    """
    if not INTERNAL_SECRET:
        # No secret configured - development mode
        return True

    if x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Invalid internal secret")

    return True
