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


def get_llm_client(
    provider: Optional[str] = None,
    auto_function_calling: Optional[bool] = None,
    api_key_override: Optional[str] = None,
    model_override: Optional[str] = None,
    base_url_override: Optional[str] = None,
    auth_type: Optional[str] = None,
) -> BaseLLMClient:
    """
    Factory function to create an LLM client.

    Args:
        provider: Optional provider name ("openai_compatible", "gemini", "openai", or "anthropic").
                  If not specified, uses LLM_PROVIDER from config.
        auto_function_calling: Whether to auto-execute tool calls. If None, uses config.
                               True = client executes tools automatically
                               False = client returns pending tools for approval
        api_key_override: Optional API key to use instead of env var (from per-request headers).
        model_override: Optional model name to use instead of config default.
        base_url_override: Optional base URL for openai_compatible provider.
        auth_type: Optional auth type for Anthropic ("api_key" or "oauth_token").

    Returns:
        An LLM client instance (BaseLLMClient subclass)

    Raises:
        ValueError: If provider is unknown or API key is missing
    """
    # Use configured provider if not specified
    provider = provider or cfg.LLM_PROVIDER

    # Model name is required — single source of truth is platform_api_keys.model_name
    # in the DB, injected via headers by master-api. Env vars are only emergency fallbacks.

    if provider == "openai_compatible":
        from backend.llm_clients.ollama import OllamaClient
        from backend.utils.util_func import log

        base_url = base_url_override or cfg.OPENAI_COMPATIBLE_BASE_URL
        api_key = api_key_override or cfg.OPENAI_COMPATIBLE_API_KEY
        model = model_override or cfg.OPENAI_COMPATIBLE_MODEL

        log(f"Using OpenAI-Compatible: {base_url} ({model})")
        return OllamaClient(
            base_url=base_url,
            model_name=model,
            api_key=api_key,
            auto_function_calling=auto_function_calling
        )

    elif provider == "gemini":
        api_key = api_key_override or cfg.GEMINI_API_KEY
        if not api_key:
            raise ValueError("Gemini API key not configured. Add one in Admin > Platform API Keys.")

        from backend.llm_clients.gemini import GeminiClient
        return GeminiClient(
            api_key=api_key,
            model_name=model_override or cfg.GEMINI_MODEL,
            auto_function_calling=auto_function_calling,
            enable_web_search=cfg.ENABLE_WEB_SEARCH
        )

    elif provider == "openai":
        api_key = api_key_override or cfg.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OpenAI API key not configured. Add one in Admin > Platform API Keys.")

        from backend.llm_clients.openai import OpenAIClient
        return OpenAIClient(
            api_key=api_key,
            model_name=model_override or cfg.OPENAI_MODEL,
            auto_function_calling=auto_function_calling,
            enable_web_search=cfg.ENABLE_WEB_SEARCH
        )

    elif provider == "anthropic":
        api_key = api_key_override or cfg.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("Anthropic API key not configured. Add one in Admin > Platform API Keys.")

        from backend.llm_clients.anthropic import AnthropicClient
        return AnthropicClient(
            api_key=api_key,
            model_name=model_override or cfg.ANTHROPIC_MODEL,
            auto_function_calling=auto_function_calling,
            enable_web_search=cfg.ENABLE_WEB_SEARCH,
            auth_type=auth_type or "api_key",
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Use 'openai_compatible', 'gemini', 'openai', or 'anthropic'.")
