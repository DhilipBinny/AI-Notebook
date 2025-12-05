"""
LLM Clients - Provider-specific implementations for LLM APIs

Supported providers:
- Anthropic (Claude)
- OpenAI (GPT-4, etc.)
- Google Gemini
- Ollama (local models)

All providers support multimodal inputs (text + images) for AI Cell operations.
"""

from backend.llm_clients.client import LLMClient
from backend.llm_clients.base import (
    ImageData,
    encode_image_from_path,
    encode_image_from_bytes,
    prepare_image,
)

__all__ = [
    "LLMClient",
    "ImageData",
    "encode_image_from_path",
    "encode_image_from_bytes",
    "prepare_image",
]
