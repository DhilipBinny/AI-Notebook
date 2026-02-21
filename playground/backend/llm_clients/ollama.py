"""
Ollama LLM Client - Ollama/OpenRouter API implementation (OpenAI-compatible)

Extends OpenAIClient since Ollama provides an OpenAI-compatible API.
Also used for OpenRouter and other OpenAI-compatible providers.

Key differences from OpenAI:
- Custom base_url for API endpoint
- Optional API key (not required for local Ollama)
- Fallback for models that don't support tool calling
- No web search (local models)
"""

from typing import List, Dict, Any, Optional
from openai import OpenAI

from backend.llm_clients.openai import OpenAIClient, _safe_json_loads
from backend.llm_clients.base import LLMResponse, ToolCall
from backend.llm_adapters.tool_schemas import build_openai_tools
from backend.utils.util_func import log
from backend.llm_tools import TOOL_FUNCTIONS
import backend.config as cfg

# Import the adapter
from backend.llm_adapters import OllamaAdapter


class OllamaClient(OpenAIClient):
    """
    Ollama LLM client - extends OpenAI client for OpenAI-compatible APIs.

    Used for:
    - Local Ollama server
    - OpenRouter API
    - Any OpenAI-compatible endpoint
    """

    def __init__(
        self,
        base_url: str = None,
        model_name: str = None,
        api_key: str = None,
        max_tokens: int = None,
        auto_function_calling: Optional[bool] = None
    ):
        """
        Initialize Ollama/OpenRouter client.

        Args:
            base_url: API server URL (e.g., "http://localhost:11434/v1" for Ollama,
                      "https://openrouter.ai/api/v1" for OpenRouter)
            model_name: Model to use (default: from config)
            api_key: API key (optional for Ollama, required for OpenRouter)
            max_tokens: Max tokens for response (default: 4096)
            auto_function_calling: Override config setting
        """
        # Don't call super().__init__() - we initialize differently
        from backend.llm_clients.base import BaseLLMClient
        BaseLLMClient.__init__(self)

        # Store Ollama-specific config
        self.base_url = base_url or cfg.OLLAMA_URL
        self.max_tokens = max_tokens or 4096
        self.enable_web_search = False  # No web search for local models

        # Initialize OpenAI client with custom endpoint
        actual_api_key = api_key or "ollama"
        self.client = OpenAI(base_url=self.base_url, api_key=actual_api_key)
        self.model_name = model_name or cfg.OLLAMA_MODEL

        # Use Ollama adapter
        self.adapter = OllamaAdapter()

        # Build tools and init state
        self.tools = build_openai_tools(TOOL_FUNCTIONS)
        self.history: List[Dict[str, Any]] = []
        self.auto_function_calling = auto_function_calling if auto_function_calling is not None else cfg.AUTO_FUNCTION_CALLING
        self._pending_messages: List[Dict[str, Any]] = []
        self._pending_tool_calls: List[Dict[str, Any]] = []
        self._ai_cell_tools_cache = None
        self._ai_cell_tool_map_cache = None

        log(f"{self._provider_display_name} client initialized: {self.model_name}")
        log(f"Config: base_url={self.base_url}, max_tokens={self.max_tokens}, auto_func={self.auto_function_calling}")

    @property
    def _provider_display_name(self) -> str:
        """Detect OpenRouter vs Ollama based on base_url."""
        return "OpenRouter" if "openrouter" in self.base_url.lower() else "Ollama"

    def _call_chat_api(self, messages: Any, tools: Any) -> Any:
        """Make API call with fallback for non-tool-supporting models."""
        try:
            return self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=self.max_tokens
            )
        except Exception as e:
            log(f"⚠️ Tool calling failed, trying without tools: {e}")
            return self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.max_tokens
            )

    def _call_llm_for_ai_cell(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> LLMResponse:
        """Make API call for AI Cell with fallback for non-tool-supporting models."""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                max_tokens=self.max_tokens,
            )
        except Exception as e:
            if "tools" in str(e).lower() or "function" in str(e).lower():
                log(f"⚠️ {self.model_name} Model doesn't support tools, falling back to simple completion")
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=self.max_tokens,
                )
                # Extract usage for fallback path
                fallback_usage = None
                if hasattr(response, 'usage') and response.usage:
                    usage_obj = response.usage
                    fallback_usage = {
                        "input_tokens": getattr(usage_obj, 'prompt_tokens', 0),
                        "output_tokens": getattr(usage_obj, 'completion_tokens', 0),
                        "cached_tokens": 0,
                    }
                return LLMResponse(
                    text=response.choices[0].message.content or "",
                    tool_calls=[],
                    is_final=True,
                    usage=fallback_usage
                )
            raise

        message = response.choices[0].message
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=_safe_json_loads(tc.function.arguments)
                ))

        # Extract usage stats
        usage = None
        if hasattr(response, 'usage') and response.usage:
            usage_obj = response.usage
            usage = {
                "input_tokens": getattr(usage_obj, 'prompt_tokens', 0),
                "output_tokens": getattr(usage_obj, 'completion_tokens', 0),
                "cached_tokens": 0,
            }

        return LLMResponse(
            text=message.content or "",
            tool_calls=tool_calls,
            is_final=len(tool_calls) == 0,
            usage=usage
        )
