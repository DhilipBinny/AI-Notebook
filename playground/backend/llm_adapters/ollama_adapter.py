"""
Ollama Adapter - OpenAI-compatible API adapter for Ollama/OpenRouter

Extends OpenAIAdapter since Ollama uses OpenAI-compatible API format.
Also used for OpenRouter and other OpenAI-compatible endpoints.
"""

from typing import Any

from backend.llm_adapters.base import register_adapter
from backend.llm_adapters.openai_adapter import OpenAIAdapter


@register_adapter("ollama")
class OllamaAdapter(OpenAIAdapter):
    """
    Adapter for Ollama and OpenRouter models.

    Ollama uses OpenAI-compatible API, so this extends OpenAIAdapter
    with minimal overrides.
    """

    @property
    def provider_name(self) -> str:
        return "Ollama"

    def get_web_search_tool(self) -> None:
        """
        Ollama doesn't support web search (local models only).

        Returns:
            None - web search not available
        """
        return None

    def log_cache_usage(self, response: Any, model_name: str = "") -> None:
        """
        Ollama doesn't have cache usage metrics.
        Just log basic usage if available.
        """
        if hasattr(response, 'usage') and response.usage:
            usage = response.usage
            input_tokens = getattr(usage, 'prompt_tokens', 0)
            output_tokens = getattr(usage, 'completion_tokens', 0)
            if input_tokens > 0 or output_tokens > 0:
                self.log(f"📊 Usage: input={input_tokens}, output={output_tokens}")
