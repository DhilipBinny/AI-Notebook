"""
Routes - FastAPI route handlers

Organized by domain:
- kernel: Jupyter kernel execution endpoints
- session: Session management

Note: notebook routes removed - notebooks stored in MinIO via master-api
"""

from backend.routes.kernel import router as kernel_router
from backend.routes.session import router as session_router

__all__ = ["kernel_router", "session_router"]
