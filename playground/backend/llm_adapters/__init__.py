"""
LLM Adapters - Provider-agnostic message and tool format translation

This module provides a unified interface for handling different LLM provider formats.
Each provider (Anthropic, Gemini, OpenAI, OpenAI-compatible) has its own adapter that translates
between the canonical internal format and the provider-specific format.

Usage:
    from backend.llm_adapters import AnthropicAdapter, CanonicalMessage

    adapter = AnthropicAdapter()
    messages = [CanonicalMessage(role="user", content="Hello")]
    provider_messages = adapter.to_messages(messages)
"""

from backend.llm_adapters.canonical import (
    CanonicalMessage,
    CanonicalToolCall,
    CanonicalToolResult,
    CanonicalTool,
    CanonicalResponse,
    ImageData,
)
from backend.llm_adapters.base import BaseProviderAdapter

# Import adapters as they are implemented
from backend.llm_adapters.anthropic_adapter import AnthropicAdapter
from backend.llm_adapters.gemini_adapter import GeminiAdapter
from backend.llm_adapters.openai_adapter import OpenAIAdapter
from backend.llm_adapters.ollama_adapter import OllamaAdapter

__all__ = [
    # Canonical types
    "CanonicalMessage",
    "CanonicalToolCall",
    "CanonicalToolResult",
    "CanonicalTool",
    "CanonicalResponse",
    "ImageData",
    # Base adapter
    "BaseProviderAdapter",
    # Provider adapters
    "AnthropicAdapter",
    "GeminiAdapter",
    "OpenAIAdapter",
    "OllamaAdapter",
]
