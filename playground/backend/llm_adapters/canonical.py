"""
Canonical Types - Universal message and tool formats for LLM communication

These types serve as the internal representation used by the application.
Provider adapters translate between these canonical types and provider-specific formats.

This approach provides:
1. Single source of truth for message structure
2. Provider-agnostic business logic
3. Easy addition of new providers
4. Consistent serialization for history storage
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum


class MessageRole(str, Enum):
    """Standard message roles across all providers"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"  # For tool results in some providers


# Type alias for image data
# Images can be:
# - {"data": "base64_string", "mime_type": "image/png"}
# - {"url": "https://..."}
# - {"path": "/workspace/image.png"} (will be converted to base64)
ImageData = Dict[str, str]


@dataclass
class CanonicalToolCall:
    """
    Universal tool call representation.

    Represents a request from the LLM to execute a tool/function.
    All providers use this same structure internally.
    """
    id: str                      # Unique identifier for this tool call
    name: str                    # Name of the tool/function to call
    arguments: Dict[str, Any]    # Arguments to pass to the tool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalToolCall":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            arguments=data.get("arguments", {})
        )


@dataclass
class CanonicalToolResult:
    """
    Universal tool result representation.

    Represents the result of executing a tool/function.
    """
    tool_call_id: str           # ID of the tool call this result is for
    name: str                   # Name of the tool that was called
    result: str                 # JSON string result
    is_error: bool = False      # Whether this result represents an error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "result": self.result,
            "is_error": self.is_error
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalToolResult":
        return cls(
            tool_call_id=data.get("tool_call_id", ""),
            name=data.get("name", ""),
            result=data.get("result", ""),
            is_error=data.get("is_error", False)
        )


@dataclass
class CanonicalMessage:
    """
    Universal message representation.

    This is the core type that represents any message in a conversation.
    It can represent user messages, assistant responses, system prompts,
    or tool results.

    Provider adapters translate this to/from provider-specific formats:
    - Anthropic: content blocks with type fields
    - Gemini: Content objects with Part lists
    - OpenAI: dict with role and content string/array
    - Ollama: OpenAI-compatible format
    """
    role: str                                              # "user", "assistant", "system", "tool"
    content: str = ""                                      # Text content
    images: List[ImageData] = field(default_factory=list)  # Attached images
    tool_calls: List[CanonicalToolCall] = field(default_factory=list)    # Tool calls (assistant)
    tool_results: List[CanonicalToolResult] = field(default_factory=list) # Tool results (user/tool)
    thinking: str = ""                                     # LLM thinking/reasoning (Claude extended thinking)
    cache_hint: bool = False                               # Hint for providers that support caching

    # Provider-specific data that needs to be preserved (e.g., Anthropic thinking signatures)
    provider_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage/transmission"""
        data = {
            "role": self.role,
            "content": self.content,
        }
        if self.images:
            data["images"] = self.images
        if self.tool_calls:
            data["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_results:
            data["tool_results"] = [tr.to_dict() for tr in self.tool_results]
        if self.thinking:
            data["thinking"] = self.thinking
        if self.cache_hint:
            data["cache_hint"] = self.cache_hint
        if self.provider_metadata:
            data["provider_metadata"] = self.provider_metadata
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalMessage":
        """Deserialize from dictionary"""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            images=data.get("images", []),
            tool_calls=[CanonicalToolCall.from_dict(tc) for tc in data.get("tool_calls", [])],
            tool_results=[CanonicalToolResult.from_dict(tr) for tr in data.get("tool_results", [])],
            thinking=data.get("thinking", ""),
            cache_hint=data.get("cache_hint", False),
            provider_metadata=data.get("provider_metadata", {})
        )

    @classmethod
    def user(cls, content: str, images: List[ImageData] = None, cache_hint: bool = False) -> "CanonicalMessage":
        """Factory method for user messages"""
        return cls(
            role=MessageRole.USER.value,
            content=content,
            images=images or [],
            cache_hint=cache_hint
        )

    @classmethod
    def assistant(cls, content: str, tool_calls: List[CanonicalToolCall] = None, thinking: str = "") -> "CanonicalMessage":
        """Factory method for assistant messages"""
        return cls(
            role=MessageRole.ASSISTANT.value,
            content=content,
            tool_calls=tool_calls or [],
            thinking=thinking
        )

    @classmethod
    def system(cls, content: str, cache_hint: bool = True) -> "CanonicalMessage":
        """Factory method for system messages"""
        return cls(
            role=MessageRole.SYSTEM.value,
            content=content,
            cache_hint=cache_hint  # System prompts are usually good cache candidates
        )

    @classmethod
    def tool_result(cls, tool_results: List[CanonicalToolResult]) -> "CanonicalMessage":
        """Factory method for tool result messages"""
        return cls(
            role=MessageRole.USER.value,  # Most providers expect tool results as user role
            tool_results=tool_results
        )


@dataclass
class CanonicalResponse:
    """
    Universal LLM response representation.

    Represents the response from an LLM API call, including:
    - Text content
    - Tool calls (if any)
    - Thinking/reasoning (for models that support it)
    - Metadata about the response
    """
    text: str = ""                                           # Response text
    tool_calls: List[CanonicalToolCall] = field(default_factory=list)  # Tools the LLM wants to call
    thinking: str = ""                                       # LLM thinking/reasoning
    is_final: bool = True                                    # True if no more tool calls needed

    # Provider-specific data that needs to be preserved for multi-turn
    # E.g., Anthropic thinking blocks with signatures
    raw_provider_blocks: List[Any] = field(default_factory=list)

    # Usage statistics (optional)
    usage: Dict[str, int] = field(default_factory=dict)      # input_tokens, output_tokens, etc.

    def to_message(self) -> CanonicalMessage:
        """Convert response to an assistant message for history"""
        return CanonicalMessage(
            role=MessageRole.ASSISTANT.value,
            content=self.text,
            tool_calls=self.tool_calls,
            thinking=self.thinking,
            provider_metadata={"raw_blocks": self.raw_provider_blocks} if self.raw_provider_blocks else {}
        )


@dataclass
class CanonicalTool:
    """
    Universal tool/function definition.

    Represents a tool that can be called by the LLM.
    Provider adapters translate this to provider-specific formats.
    """
    name: str                           # Tool name (must be unique)
    description: str                    # Human-readable description
    parameters: Dict[str, Any]          # JSON Schema for parameters
    function: Optional[Callable] = None # The actual function to call (optional)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (without function)"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

    @classmethod
    def from_function(cls, func: Callable, description: str = None, parameters: Dict[str, Any] = None) -> "CanonicalTool":
        """
        Create a CanonicalTool from a Python function.

        If parameters not provided, attempts to infer from function signature.
        """
        name = func.__name__
        desc = description or func.__doc__ or f"Call the {name} function"

        # If parameters not provided, create a basic schema
        if parameters is None:
            import inspect
            sig = inspect.signature(func)
            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue

                prop = {"type": "string"}  # Default to string

                # Try to infer type from annotation
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        prop["type"] = "integer"
                    elif param.annotation == float:
                        prop["type"] = "number"
                    elif param.annotation == bool:
                        prop["type"] = "boolean"
                    elif param.annotation == list or param.annotation == List:
                        prop["type"] = "array"
                    elif param.annotation == dict or param.annotation == Dict:
                        prop["type"] = "object"

                properties[param_name] = prop

                # Required if no default
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            parameters = {
                "type": "object",
                "properties": properties,
                "required": required
            }

        return cls(
            name=name,
            description=desc,
            parameters=parameters,
            function=func
        )


# Convenience functions for creating messages
def user_message(content: str, images: List[ImageData] = None, cache_hint: bool = False) -> CanonicalMessage:
    """Create a user message"""
    return CanonicalMessage.user(content, images, cache_hint)


def assistant_message(content: str, tool_calls: List[CanonicalToolCall] = None, thinking: str = "") -> CanonicalMessage:
    """Create an assistant message"""
    return CanonicalMessage.assistant(content, tool_calls, thinking)


def system_message(content: str, cache_hint: bool = True) -> CanonicalMessage:
    """Create a system message"""
    return CanonicalMessage.system(content, cache_hint)


def nudge_message(text: str = None) -> CanonicalMessage:
    """Create a nudge message for empty response retries"""
    default_text = (
        "Your previous response was empty or filtered. "
        "Please provide a valid response with either text content, "
        "a tool call, or your reasoning. Try a different approach if needed."
    )
    return CanonicalMessage.user(text or default_text)
