"""
AI Notebook Playground - Headless FastAPI Server
Container-based kernel execution and LLM chat API.
No frontend - pure API for Master backend to proxy.
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Import all routers
from backend.routes import (
    kernel_router,
    session_router,
    health_router,
    ai_cell_router,
    chat_router,
    llm_complete_router,
)
import backend.config as cfg


# =============================================================================
# App Lifecycle
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    yield

    # Shutdown: clean up all sessions and kernels
    try:
        from backend.session_manager import get_session_manager
        get_session_manager().cleanup_all()
    except Exception as e:
        print(f"[Shutdown] Error cleaning up sessions: {e}")


# =============================================================================
# App Initialization
# =============================================================================

app = FastAPI(
    title="AI Notebook Playground",
    version="0.1.0",
    description="Headless notebook execution container",
    lifespan=lifespan,
)


# =============================================================================
# Include All Routers
# =============================================================================

# Health & Status (no prefix)
app.include_router(health_router)

# Kernel execution (no prefix - /execute, /ws/execute)
app.include_router(kernel_router)

# Session management (/session/...)
app.include_router(session_router)

# AI Cell (/ai-cell/...)
app.include_router(ai_cell_router)

# Chat (/chat/...)
app.include_router(chat_router)

# LLM completion (/llm/...)
app.include_router(llm_complete_router)



# =============================================================================
# Logging Configuration
# =============================================================================

class HealthCheckFilter(logging.Filter):
    """Filter out health check request logs to reduce noise."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "GET /health" in message:
            return False
        return True


# Apply filter at module load time (works with uvicorn)
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    PORT = int(os.getenv("PLAYGROUND_PORT", "8888"))
    HOST = os.getenv("HOST", "0.0.0.0")

    print("\n" + "=" * 50)
    print("  AI Notebook Playground (Headless)")
    print("=" * 50)
    print(f"  Port: {PORT}")
    print(f"  LLM Provider: {cfg.LLM_PROVIDER}")
    print("=" * 50 + "\n")

    uvicorn.run(
        "backend.server:app",
        host=HOST,
        port=PORT,
        log_level="info",
    )
