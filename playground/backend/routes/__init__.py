"""
Routes - FastAPI route handlers

Organized by domain:
- health: Health check and status endpoints
- kernel: Jupyter kernel execution endpoints
- session: Session management
- ai_cell: AI Cell execution with SSE streaming
- chat: Chat with LLM assistant
- llm_complete: Simple LLM completion
"""

from backend.routes.kernel import router as kernel_router
from backend.routes.session import router as session_router
from backend.routes.health import router as health_router
from backend.routes.ai_cell import router as ai_cell_router
from backend.routes.chat import router as chat_router
from backend.routes.llm_complete import router as llm_complete_router

__all__ = [
    "kernel_router",
    "session_router",
    "health_router",
    "ai_cell_router",
    "chat_router",
    "llm_complete_router",
]
