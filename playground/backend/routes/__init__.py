"""
Routes - FastAPI route handlers

Organized by domain:
- kernel: Jupyter kernel execution endpoints
- notebook: Notebook cell operations
- session: Session management
"""

from backend.routes.kernel import router as kernel_router
from backend.routes.notebook import router as notebook_router
from backend.routes.session import router as session_router

__all__ = ["kernel_router", "notebook_router", "session_router"]
