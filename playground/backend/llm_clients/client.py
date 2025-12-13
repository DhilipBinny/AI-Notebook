"""
LLM Client Factory - Creates the appropriate LLM client based on configuration

Usage:
    from backend.llm_clients import get_llm_client

    # Get client using configured provider
    client = get_llm_client()

    # Or specify provider explicitly
    client = get_llm_client(provider="openai")
"""

from typing import Optional
import backend.config as cfg
from backend.llm_clients.base import BaseLLMClient


def get_llm_client(provider: Optional[str] = None, auto_function_calling: Optional[bool] = None) -> BaseLLMClient:
    """
    Factory function to create an LLM client.

    Args:
        provider: Optional provider name ("ollama", "gemini", "openai", or "anthropic").
                  If not specified, uses LLM_PROVIDER from config.
        auto_function_calling: Whether to auto-execute tool calls. If None, uses config.
                               True = client executes tools automatically
                               False = client returns pending tools for approval

    Returns:
        An LLM client instance (BaseLLMClient subclass)

    Raises:
        ValueError: If provider is unknown or API key is missing
    """
    # Use configured provider if not specified
    provider = provider or cfg.LLM_PROVIDER

    if provider == "ollama":
        from backend.llm_clients.ollama import OllamaClient
        return OllamaClient(
            base_url=cfg.OLLAMA_URL,
            model_name=cfg.OLLAMA_MODEL,
            auto_function_calling=auto_function_calling
        )

    elif provider == "gemini":
        if not cfg.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not configured")

        from backend.llm_clients.gemini import GeminiClient
        return GeminiClient(
            api_key=cfg.GEMINI_API_KEY,
            model_name=cfg.GEMINI_MODEL,
            auto_function_calling=auto_function_calling,
            enable_web_search=cfg.ENABLE_WEB_SEARCH
        )

    elif provider == "openai":
        if not cfg.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")

        from backend.llm_clients.openai import OpenAIClient
        return OpenAIClient(
            api_key=cfg.OPENAI_API_KEY,
            model_name=cfg.OPENAI_MODEL,
            auto_function_calling=auto_function_calling,
            enable_web_search=cfg.ENABLE_WEB_SEARCH
        )

    elif provider == "anthropic":
        if not cfg.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        from backend.llm_clients.anthropic import AnthropicClient
        return AnthropicClient(
            api_key=cfg.ANTHROPIC_API_KEY,
            model_name=cfg.ANTHROPIC_MODEL,
            auto_function_calling=auto_function_calling,
            enable_web_search=cfg.ENABLE_WEB_SEARCH
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Use 'ollama', 'gemini', 'openai', or 'anthropic'.")
