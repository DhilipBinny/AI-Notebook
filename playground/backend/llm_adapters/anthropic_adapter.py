"""
Anthropic Provider Adapter - Translates between canonical and Anthropic formats

Handles Anthropic-specific requirements:
1. Content blocks format: [{"type": "text", "text": "..."}, {"type": "image", ...}]
2. Tool definitions: {"name", "description", "input_schema": {...}}
3. Extended thinking: thinking blocks with signatures
4. Prompt caching: cache_control on content blocks
5. System prompt: Separate from messages, supports array format
"""

from typing import List, Dict, Any, Callable

from backend.llm_adapters.base import BaseProviderAdapter, register_adapter
from backend.llm_adapters.canonical import (
    CanonicalMessage,
    CanonicalToolCall,
    CanonicalToolResult,
    CanonicalTool,
    CanonicalResponse,
    ImageData,
)


@register_adapter("anthropic")
class AnthropicAdapter(BaseProviderAdapter):
    """
    Adapter for Anthropic Claude models.

    Anthropic uses a content blocks format where each message content
    is a list of typed blocks (text, image, tool_use, tool_result, thinking).
    """

    # Web search tool configuration (update here if Anthropic changes API)
    WEB_SEARCH_TOOL_TYPE = "web_search_20250305"
    WEB_SEARCH_TOOL_NAME = "web_search"

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    # =========================================================================
    # MESSAGE CONVERSION
    # =========================================================================

    def to_messages(self, messages: List[CanonicalMessage]) -> List[Dict[str, Any]]:
        """
        Convert canonical messages to Anthropic content blocks format.

        Anthropic format:
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "...", "cache_control": {...}},
                    {"type": "image", "source": {...}}
                ]
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "..."},
                    {"type": "text", "text": "..."},
                    {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
                ]
            }
        ]
        """
        result = []

        for msg in messages:
            # Skip system messages - Anthropic handles them separately
            if msg.role == "system":
                continue

            content = self._build_content_blocks(msg)

            if content:  # Only add if there's content
                result.append({
                    "role": msg.role,
                    "content": content
                })

        return result

    def _build_content_blocks(self, msg: CanonicalMessage) -> List[Dict[str, Any]]:
        """Build Anthropic content blocks from a canonical message."""
        content = []

        # Add thinking blocks first (for assistant messages with extended thinking)
        # These need to come from provider_metadata if preserved
        if msg.provider_metadata.get("raw_blocks"):
            for block in msg.provider_metadata["raw_blocks"]:
                # Raw blocks are already in Anthropic format
                content.append(block)

        # Add images
        for img in msg.images:
            prepared = self.prepare_image(img)
            if "url" in prepared:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": prepared["url"]
                    }
                })
            else:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": prepared.get("mime_type", "image/png"),
                        "data": prepared["data"]
                    }
                })

        # Add text content
        if msg.content:
            text_block = {"type": "text", "text": msg.content}

            # Add cache_control if cache_hint is set and content is large enough
            # Anthropic requires minimum ~1024 tokens for caching
            if msg.cache_hint and len(msg.content) >= 1024:
                text_block["cache_control"] = {"type": "ephemeral"}

            content.append(text_block)

        # Add tool calls (for assistant messages)
        for tc in msg.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments
            })

        # Add tool results
        for tr in msg.tool_results:
            content.append({
                "type": "tool_result",
                "tool_use_id": tr.tool_call_id,
                "content": tr.result,
                "is_error": tr.is_error
            })

        return content

    def from_response(self, response: Any) -> CanonicalResponse:
        """
        Convert Anthropic response to canonical format.

        Handles:
        - Text content blocks
        - Tool use blocks
        - Thinking blocks (extended thinking)
        - Server tool use (web search)
        """
        text = ""
        thinking = ""
        tool_calls = []
        raw_blocks = []  # Preserve for multi-turn

        for block in response.content:
            if block.type == "thinking":
                # Extended thinking block
                thinking += block.thinking if hasattr(block, 'thinking') else ""
                raw_blocks.append(block)  # Preserve with signature

            elif hasattr(block, 'text') and block.text:
                text += block.text

            elif block.type == "tool_use":
                tool_calls.append(CanonicalToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input or {}
                ))

            elif block.type == "server_tool_use":
                # Web search - log but don't treat as regular tool
                self.log(f"Web search triggered: {block.name}")

            elif block.type == "web_search_tool_result":
                # Web search results - already incorporated in response
                result_count = len(block.content) if hasattr(block, 'content') else 0
                self.log(f"Web search returned {result_count} results")

        # Determine if this is a final response
        is_final = response.stop_reason == "end_turn"

        # Extract usage if available
        usage = {}
        if hasattr(response, 'usage'):
            usage_obj = response.usage
            usage = {
                "input_tokens": getattr(usage_obj, 'input_tokens', 0),
                "output_tokens": getattr(usage_obj, 'output_tokens', 0),
                "cache_creation_input_tokens": getattr(usage_obj, 'cache_creation_input_tokens', 0),
                "cache_read_input_tokens": getattr(usage_obj, 'cache_read_input_tokens', 0),
            }

        return CanonicalResponse(
            text=text,
            tool_calls=tool_calls,
            thinking=thinking,
            is_final=is_final,
            raw_provider_blocks=raw_blocks,
            usage=usage
        )

    def add_tool_results(
        self,
        messages: List[Dict[str, Any]],
        response: CanonicalResponse,
        tool_results: List[CanonicalToolResult]
    ) -> List[Dict[str, Any]]:
        """
        Add tool results to messages for next Anthropic API call.

        Anthropic requires:
        1. Assistant message with tool_use blocks (and thinking blocks first if present)
        2. User message with tool_result blocks
        """
        # Build assistant message content
        assistant_content = []

        # Add raw thinking blocks first (includes signature field for verification)
        for block in response.raw_provider_blocks:
            assistant_content.append(block)

        # Add tool_use blocks
        for tc in response.tool_calls:
            assistant_content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments
            })

        # Add assistant message
        messages.append({"role": "assistant", "content": assistant_content})

        # Build tool_result blocks
        result_blocks = []
        for tr in tool_results:
            result_blocks.append({
                "type": "tool_result",
                "tool_use_id": tr.tool_call_id,
                "content": tr.result,
                "is_error": tr.is_error
            })

        # Add user message with tool results
        messages.append({"role": "user", "content": result_blocks})

        return messages

    # =========================================================================
    # TOOL CONVERSION
    # =========================================================================

    def to_tools(self, tools: List[CanonicalTool]) -> List[Dict[str, Any]]:
        """
        Convert canonical tools to Anthropic format.

        Anthropic format:
        {
            "name": "tool_name",
            "description": "What the tool does",
            "input_schema": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters
            }
            for tool in tools
        ]

    def to_tools_from_functions(self, functions: List[Callable]) -> List[Dict[str, Any]]:
        """
        Convert Python functions directly to Anthropic tool format.

        This is a convenience method that mirrors the existing build_anthropic_tools.
        """
        from backend.llm_adapters.tool_schemas import build_anthropic_tools
        return build_anthropic_tools(functions)

    def get_web_search_tool(self, max_uses: int = 5) -> Dict[str, Any]:
        """
        Get Anthropic web search tool definition.

        Args:
            max_uses: Maximum number of web searches per request

        Returns:
            Anthropic web search tool definition
        """
        return {
            "type": self.WEB_SEARCH_TOOL_TYPE,
            "name": self.WEB_SEARCH_TOOL_NAME,
            "max_uses": max_uses
        }

    # =========================================================================
    # SYSTEM PROMPT HANDLING
    # =========================================================================

    def get_system_prompt_config(
        self,
        system_prompt: str,
        cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get system prompt in Anthropic array format with optional caching.

        Anthropic supports system prompt as array:
        system=[{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}]

        Args:
            system_prompt: The system prompt text
            cache: Whether to enable caching (5-minute ephemeral cache)

        Returns:
            List with single text block, optionally with cache_control
        """
        block = {"type": "text", "text": system_prompt}

        if cache:
            block["cache_control"] = {"type": "ephemeral"}

        return [block]

    # =========================================================================
    # HISTORY CONVERSION
    # =========================================================================

    def to_history(self, messages: List[CanonicalMessage]) -> List[Dict[str, Any]]:
        """
        Serialize canonical messages for storage.

        Note: We use the canonical format for storage, not Anthropic format.
        This allows history to be portable across providers.
        """
        return [msg.to_dict() for msg in messages]

    def from_history(self, history: List[Dict[str, Any]]) -> List[CanonicalMessage]:
        """
        Deserialize messages from stored format.
        """
        return [CanonicalMessage.from_dict(h) for h in history]

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def build_cached_user_message(
        self,
        context: str,
        prompt: str,
        images: List[ImageData] = None,
        cache_context: bool = True
    ) -> CanonicalMessage:
        """
        Build a user message with proper caching structure.

        For Anthropic, we want to cache the context but not the prompt.
        This is achieved by creating a single message with both parts
        where the context has cache_hint=True.

        Args:
            context: Notebook context (cacheable)
            prompt: User's question (not cached)
            images: Optional images
            cache_context: Whether to cache the context

        Returns:
            CanonicalMessage with proper structure for Anthropic caching
        """
        # If we want fine-grained caching, we need to return messages separately
        # But for simplicity, combine them with cache hint on the whole thing
        full_content = f"{context}\n\n{prompt}" if context else prompt

        return CanonicalMessage(
            role="user",
            content=full_content,
            images=images or [],
            cache_hint=cache_context and len(context) >= 1024
        )

    def build_multi_part_message(
        self,
        parts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Build a multi-part content block list.

        Useful for creating messages with separate cached and non-cached parts.

        Args:
            parts: List of {"text": str, "cache": bool} dicts

        Returns:
            Anthropic content blocks
        """
        content = []
        for part in parts:
            block = {"type": "text", "text": part["text"]}
            if part.get("cache") and len(part["text"]) >= 1024:
                block["cache_control"] = {"type": "ephemeral"}
            content.append(block)
        return content

    def log_cache_usage(self, response: Any) -> None:
        """Log cache usage statistics from Anthropic response."""
        if hasattr(response, 'usage'):
            usage = response.usage
            cache_creation = getattr(usage, 'cache_creation_input_tokens', 0)
            cache_read = getattr(usage, 'cache_read_input_tokens', 0)
            input_tokens = getattr(usage, 'input_tokens', 0)
            output_tokens = getattr(usage, 'output_tokens', 0)

            if cache_creation > 0 or cache_read > 0:
                self.log(f"💾 Cache: write={cache_creation}, read={cache_read}, input={input_tokens}, output={output_tokens}")
                if cache_read > 0:
                    savings_pct = (cache_read * 0.9) / max(input_tokens, 1) * 100
                    self.log(f"💰 Cache savings: ~{savings_pct:.1f}% on input tokens")
