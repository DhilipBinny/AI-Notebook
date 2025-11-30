"""
Internal API module for playground-facing endpoints.

These endpoints are authenticated via X-Internal-Secret header,
not user JWT tokens.
"""

from .routes import router

__all__ = ["router"]
