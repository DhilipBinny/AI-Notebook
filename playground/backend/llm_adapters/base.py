"""
Base Provider Adapter - Abstract interface for LLM provider adapters

All provider adapters must implement this interface to translate between
canonical format and provider-specific formats.

The adapter pattern allows the LLM clients to work with a unified format
while the adapter handles all provider-specific transformations.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import base64
from pathlib import Path

from backend.llm_adapters.canonical import (
    CanonicalMessage,
    CanonicalToolResult,
    CanonicalTool,
    CanonicalResponse,
    ImageData,
    nudge_message,
)
from backend.utils.util_func import log


# MIME types for image encoding
MIME_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp'
}


class BaseProviderAdapter(ABC):
    """
    Abstract base class for provider-specific adapters.

    Each provider (Anthropic, Gemini, OpenAI, Ollama) must implement
    this interface to translate between canonical and provider formats.

    Key responsibilities:
    1. to_messages(): Convert canonical messages to provider format
    2. from_response(): Convert provider response to canonical format
    3. to_tools(): Convert canonical tools to provider format
    4. to_history(): Serialize messages for storage
    5. from_history(): Deserialize messages from storage
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the provider (e.g., 'Anthropic', 'Gemini')"""
        pass

    # =========================================================================
    # MESSAGE CONVERSION
    # =========================================================================

    @abstractmethod
    def to_messages(self, messages: List[CanonicalMessage]) -> Any:
        """
        Convert canonical messages to provider-specific format.

        This is the main translation method. It takes our internal
        representation and converts it to what the provider's API expects.

        Args:
            messages: List of CanonicalMessage objects

        Returns:
            Provider-specific message format (varies by provider)
            - Anthropic: List[Dict] with content blocks
            - Gemini: List[types.Content]
            - OpenAI: List[Dict] with role/content
        """
        pass

    @abstractmethod
    def from_response(self, response: Any) -> CanonicalResponse:
        """
        Convert provider response to canonical format.

        Takes the raw response from the provider's API and extracts
        the relevant information into our standard format.

        Args:
            response: Raw response from provider API

        Returns:
            CanonicalResponse with text, tool_calls, thinking, etc.
        """
        pass

    @abstractmethod
    def add_tool_results(
        self,
        messages: Any,
        response: CanonicalResponse,
        tool_results: List[CanonicalToolResult]
    ) -> Any:
        """
        Add tool results to messages for the next API call.

        After tools are executed, we need to add both:
        1. The assistant's message with tool calls
        2. The tool results

        Different providers have different requirements for this.

        Args:
            messages: Current messages in provider format
            response: The assistant's response that triggered tools
            tool_results: Results from executing the tools

        Returns:
            Updated messages with tool results added
        """
        pass

    # =========================================================================
    # TOOL CONVERSION
    # =========================================================================

    @abstractmethod
    def to_tools(self, tools: List[CanonicalTool]) -> Any:
        """
        Convert canonical tools to provider-specific format.

        Each provider has its own schema for defining tools/functions.

        Args:
            tools: List of CanonicalTool objects

        Returns:
            Provider-specific tool format
            - Anthropic: List[Dict] with name, description, input_schema
            - Gemini: List[types.Tool] with FunctionDeclarations
            - OpenAI: List[Dict] with type, function
        """
        pass

    def get_web_search_tool(self) -> Optional[Any]:
        """
        Get the web search tool definition for this provider.

        Override in providers that support native web search.
        Returns None if web search is not supported.

        Returns:
            Provider-specific web search tool definition, or None
        """
        return None

    # =========================================================================
    # HISTORY SERIALIZATION
    # =========================================================================

    def to_history(self, messages: List[CanonicalMessage]) -> List[Dict[str, Any]]:
        """
        Serialize canonical messages to storable format.

        Default implementation uses CanonicalMessage.to_dict().
        Override if provider needs special handling.

        Args:
            messages: List of CanonicalMessage objects

        Returns:
            List of dictionaries that can be JSON serialized
        """
        return [msg.to_dict() for msg in messages]

    def from_history(self, history: List[Dict[str, Any]]) -> List[CanonicalMessage]:
        """
        Deserialize messages from stored format.

        Default implementation uses CanonicalMessage.from_dict().
        Override if provider needs special handling.

        Args:
            history: List of serialized message dictionaries

        Returns:
            List of CanonicalMessage objects
        """
        return [CanonicalMessage.from_dict(h) for h in history]

    # =========================================================================
    # SYSTEM PROMPT HANDLING
    # =========================================================================

    @abstractmethod
    def get_system_prompt_config(self, system_prompt: str) -> Any:
        """
        Get system prompt in provider-specific format.

        Some providers (Anthropic, Gemini) handle system prompts separately
        from the message list. Others (OpenAI) include them as messages.

        Args:
            system_prompt: The system prompt text

        Returns:
            Provider-specific system prompt configuration
        """
        pass

    # =========================================================================
    # HELPER METHODS (Shared implementations)
    # =========================================================================

    def create_nudge_message(self, text: str = None) -> CanonicalMessage:
        """
        Create a nudge message for empty response retries.

        This is the same across all providers since it's canonical format.

        Args:
            text: Custom nudge text (uses default if not provided)

        Returns:
            CanonicalMessage with the nudge text
        """
        return nudge_message(text)

    def prepare_image(self, image: ImageData) -> ImageData:
        """
        Prepare an image for sending to LLM.

        Handles path-based images by converting to base64.
        This is shared logic used by all providers.

        Args:
            image: Image dict with one of:
                   - {"data": "base64...", "mime_type": "image/png"}
                   - {"path": "/path/to/image.png"}
                   - {"url": "https://..."}

        Returns:
            Normalized image dict with "data" and "mime_type" or "url"
        """
        if "path" in image:
            return self._encode_image_from_path(image["path"])
        elif "data" in image:
            return {
                "data": image["data"],
                "mime_type": image.get("mime_type", "image/png")
            }
        elif "url" in image:
            return {"url": image["url"]}
        else:
            raise ValueError("Image must have 'data', 'path', or 'url' key")

    def _encode_image_from_path(self, file_path: str) -> ImageData:
        """Read and base64 encode an image file."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        mime_type = MIME_TYPES.get(path.suffix.lower(), 'image/png')

        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('utf-8')

        return {"data": data, "mime_type": mime_type}

    def log(self, message: str) -> None:
        """Log a message with provider prefix."""
        log(f"[{self.provider_name}] {message}")


class AdapterRegistry:
    """
    Registry for provider adapters.

    Allows getting adapters by provider name.
    """
    _adapters: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, adapter_class: type) -> None:
        """Register an adapter class for a provider name."""
        cls._adapters[name.lower()] = adapter_class

    @classmethod
    def get(cls, name: str) -> Optional[type]:
        """Get adapter class by provider name."""
        return cls._adapters.get(name.lower())

    @classmethod
    def create(cls, name: str, **kwargs) -> Optional[BaseProviderAdapter]:
        """Create an adapter instance by provider name."""
        adapter_class = cls.get(name)
        if adapter_class:
            return adapter_class(**kwargs)
        return None

    @classmethod
    def available(cls) -> List[str]:
        """List available provider names."""
        return list(cls._adapters.keys())


def register_adapter(name: str):
    """Decorator to register an adapter class."""
    def decorator(cls):
        AdapterRegistry.register(name, cls)
        return cls
    return decorator
