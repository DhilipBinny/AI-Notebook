"""
LLM Client Factory - Creates the appropriate LLM client based on configuration

Usage:
    from backend.llm_clients import LLMClient

    # Use LLMClient class (uses configured provider)
    client = LLMClient()

    # Or specify provider explicitly
    client = LLMClient(provider="openai")
"""

from typing import Optional, List, Dict, Any, Union
import backend.config as cfg
from backend.llm_clients.base import BaseLLMClient, ImageData


def get_llm_client(provider: Optional[str] = None) -> BaseLLMClient:
    """
    Factory function to create an LLM client.

    Args:
        provider: Optional provider name ("ollama", "gemini", "openai", or "anthropic").
                  If not specified, uses LLM_PROVIDER from config.

    Returns:
        An LLM client instance

    Raises:
        ValueError: If provider is unknown or API key is missing
    """
    # Use configured provider if not specified
    provider = provider or cfg.LLM_PROVIDER

    if provider == "ollama":
        from backend.llm_clients.ollama import OllamaClient
        return OllamaClient(
            base_url=cfg.OLLAMA_URL,
            model_name=cfg.OLLAMA_MODEL
        )

    elif provider == "gemini":
        if not cfg.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not configured")

        from backend.llm_clients.gemini import GeminiClient
        return GeminiClient(
            api_key=cfg.GEMINI_API_KEY,
            model_name=cfg.GEMINI_MODEL,
            enable_web_search=cfg.ENABLE_WEB_SEARCH
        )

    elif provider == "openai":
        if not cfg.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")

        from backend.llm_clients.openai import OpenAIClient
        return OpenAIClient(
            api_key=cfg.OPENAI_API_KEY,
            model_name=cfg.OPENAI_MODEL,
            enable_web_search=cfg.ENABLE_WEB_SEARCH
        )

    elif provider == "anthropic":
        if not cfg.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        from backend.llm_clients.anthropic import AnthropicClient
        return AnthropicClient(
            api_key=cfg.ANTHROPIC_API_KEY,
            model_name=cfg.ANTHROPIC_MODEL,
            enable_web_search=cfg.ENABLE_WEB_SEARCH
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Use 'ollama', 'gemini', 'openai', or 'anthropic'.")


# Backward compatibility: LLMClient class that wraps the factory
class LLMClient:
    """
    Wrapper class for backward compatibility.

    Creates the appropriate client based on configuration and delegates all calls.
    Note: This is a proxy class, not a BaseLLMClient subclass.
    """

    def __init__(self, provider: Optional[str] = None):
        """
        Initialize LLM client.

        Args:
            provider: Optional provider override ("gemini" or "openai")
        """
        self._client = get_llm_client(provider)

    def send_message(self, message: str, user_message: str = None, images: Optional[List[ImageData]] = None) -> Union[str, Dict[str, Any]]:
        return self._client.send_message(message, user_message, images)

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

    def chat_completion(self, prompt: str, max_tokens: int = 1000) -> str:
        return self._client.chat_completion(prompt, max_tokens)

    def ai_cell_completion(self, prompt: str, images: Optional[List[ImageData]] = None) -> str:
        return self._client.ai_cell_completion(prompt, images)

    def ai_cell_with_tools(self, prompt: str, images: Optional[List[ImageData]] = None, max_iterations: int = 10) -> Dict[str, Any]:
        return self._client.ai_cell_with_tools(prompt, images, max_iterations)

    def cancel(self) -> None:
        """Cancel any ongoing AI Cell operation."""
        self._client.cancel()

    def reset_cancellation(self) -> None:
        """Reset the cancellation flag."""
        self._client.reset_cancellation()

    def set_progress_callback(self, callback) -> None:
        """Set a callback for progress updates during tool execution."""
        self._client.set_progress_callback(callback)
