"""
LLM Client Factory - Creates the appropriate LLM client based on configuration

Usage:
    from backend.llm_client import LLMClient, get_llm_client

    # Create client using factory (recommended)
    client = get_llm_client()

    # Or use LLMClient class directly (uses configured provider)
    client = LLMClient()

    # Or specify provider explicitly
    client = get_llm_client(provider="openai")
"""

from typing import Optional, List, Dict, Any, Union
import backend.config as cfg
from backend.llm_client_base import BaseLLMClient


def get_llm_client(provider: Optional[str] = None) -> BaseLLMClient:
    """
    Factory function to create an LLM client.

    Args:
        provider: Optional provider name ("ollama", "gemini", or "openai").
                  If not specified, uses LLM_PROVIDER from config.

    Returns:
        An LLM client instance (OllamaClient, GeminiClient, or OpenAIClient)

    Raises:
        ValueError: If provider is unknown or API key is missing
    """
    # Use configured provider if not specified
    provider = provider or cfg.LLM_PROVIDER

    if provider == "ollama":
        from backend.llm_client_ollama import OllamaClient
        return OllamaClient(
            base_url=cfg.OLLAMA_URL,
            model_name=cfg.OLLAMA_MODEL
        )

    elif provider == "gemini":
        if not cfg.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not configured")

        from backend.llm_client_gemini import GeminiClient
        return GeminiClient(
            api_key=cfg.GEMINI_API_KEY,
            model_name=cfg.GEMINI_MODEL
        )

    elif provider == "openai":
        if not cfg.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")

        from backend.llm_client_openai import OpenAIClient
        return OpenAIClient(
            api_key=cfg.OPENAI_API_KEY,
            model_name=cfg.OPENAI_MODEL
        )

    elif provider == "anthropic":
        if not cfg.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        from backend.llm_client_anthropic import AnthropicClient
        return AnthropicClient(
            api_key=cfg.ANTHROPIC_API_KEY,
            model_name=cfg.ANTHROPIC_MODEL
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Use 'ollama', 'gemini', 'openai', or 'anthropic'.")


# Backward compatibility: LLMClient class that wraps the factory
class LLMClient(BaseLLMClient):
    """
    Wrapper class for backward compatibility.

    Creates the appropriate client based on configuration and delegates all calls.
    """

    def __init__(self, provider: Optional[str] = None):
        """
        Initialize LLM client.

        Args:
            provider: Optional provider override ("gemini" or "openai")
        """
        self._client = get_llm_client(provider)

    def send_message(self, message: str) -> Union[str, Dict[str, Any]]:
        return self._client.send_message(message)

    def execute_approved_tools(self, approved_tool_calls: List[Dict[str, Any]]) -> str:
        return self._client.execute_approved_tools(approved_tool_calls)

    def clear_history(self) -> None:
        self._client.clear_history()

    def get_history(self):
        return self._client.get_history()

    def set_history(self, history_list) -> None:
        self._client.set_history(history_list)

    @property
    def provider_name(self) -> str:
        return self._client.provider_name
