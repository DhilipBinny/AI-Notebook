"""
Health Routes - Health check and status endpoints
"""

from fastapi import APIRouter, Depends

import backend.config as cfg
from backend.middleware.security import verify_internal_secret
from backend.session_manager import get_session_manager

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint (no auth required)."""
    return {
        "status": "ok",
        "service": "playground",
        "provider": cfg.LLM_PROVIDER,
    }


@router.get("/status")
async def status(authorized: bool = Depends(verify_internal_secret)):
    """Detailed status (auth required)."""
    session_manager = get_session_manager()
    return {
        "status": "ok",
        "llm_provider": cfg.LLM_PROVIDER,
        "tool_mode": cfg.TOOL_EXECUTION_MODE,
        "active_sessions": session_manager.session_count,
    }
