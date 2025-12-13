"""
LLM Clients - Provider-specific implementations for LLM APIs

Supported providers:
- Anthropic (Claude)
- OpenAI (GPT-4, etc.)
- Google Gemini
- Ollama (local models)

All providers support multimodal inputs (text + images) for AI Cell operations.

Usage:
    from backend.llm_clients import get_llm_client

    client = get_llm_client()  # Uses configured provider
    client = get_llm_client(provider="gemini")  # Explicit provider
"""

from backend.llm_clients.client import get_llm_client
from backend.llm_clients.base import (
    BaseLLMClient,
    ImageData,
    encode_image_from_path,
    encode_image_from_bytes,
    prepare_image,
)

__all__ = [
    "get_llm_client",
    "BaseLLMClient",
    "ImageData",
    "encode_image_from_path",
    "encode_image_from_bytes",
    "prepare_image",
]
