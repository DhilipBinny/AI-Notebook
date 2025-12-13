"""
Middleware - Security and request handling middleware
"""

from backend.middleware.security import verify_internal_secret, INTERNAL_SECRET

__all__ = ["verify_internal_secret", "INTERNAL_SECRET"]
