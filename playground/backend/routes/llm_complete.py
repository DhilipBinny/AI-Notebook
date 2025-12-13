"""
LLM Complete Routes - Simple text completion without tools
"""

from fastapi import APIRouter, Depends

import backend.config as cfg
from backend.llm_clients import get_llm_client
from backend.middleware.security import verify_internal_secret
from backend.models import LLMCompleteRequest
from backend.utils.util_func import log

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/complete")
async def llm_complete(
    request: LLMCompleteRequest,
    authorized: bool = Depends(verify_internal_secret),
):
    """
    Simple text completion without tools.
    Used for summarization and other simple LLM tasks.
    """
    try:
        provider = request.llm_provider or cfg.LLM_PROVIDER
        log(f"LLM complete request (provider={provider}): {request.prompt[:200]}...")

        client = get_llm_client(provider=provider)
        response_text = client.simple_completion(request.prompt, request.max_tokens)

        log(f"LLM complete response: {response_text[:200]}...")

        return {
            "success": True,
            "response": response_text,
        }

    except Exception as e:
        log(f"LLM complete error: {e}")
        return {
            "success": False,
            "response": "",
            "error": str(e),
        }
