"""
OpenAI Provider Adapter - Translates between canonical and OpenAI formats

Handles OpenAI-specific requirements:
1. Message format: {"role": "user"|"assistant"|"system"|"tool", "content": "..."}
2. Tool calls: {"id": "...", "type": "function", "function": {"name": "...", "arguments": "{...}"}}
3. Tool results: {"role": "tool", "tool_call_id": "...", "content": "..."}
4. Tools: {"type": "function", "function": {"name", "description", "parameters"}}
5. Web search: {"type": "web_search_preview", "search_context_size": "medium"}
6. Images: Content array with {"type": "image_url", "image_url": {"url": "...", "detail": "auto"}}

Note: Ollama uses OpenAI-compatible API, so this adapter works for both.
"""

from typing import List, Dict, Any, Optional, Callable, Union
import json

from backend.llm_adapters.base import BaseProviderAdapter, register_adapter
from backend.llm_adapters.canonical import (
    CanonicalMessage,
    CanonicalToolCall,
    CanonicalToolResult,
    CanonicalTool,
    CanonicalResponse,
    ImageData,
)


@register_adapter("openai")
class OpenAIAdapter(BaseProviderAdapter):
    """
    Adapter for OpenAI models (GPT-4, etc.).

    OpenAI uses a simple dict format for messages with role and content.
    Tool calls are embedded in assistant messages, tool results are separate messages.

    Also works with Ollama since it uses OpenAI-compatible API.
    """

    # Web search tool configuration (update here if OpenAI changes API)
    WEB_SEARCH_TOOL_TYPE = "web_search_preview"
    WEB_SEARCH_CONTEXT_SIZE = "medium"  # Options: "low", "medium", "high"

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    # =========================================================================
    # MESSAGE CONVERSION
    # =========================================================================

    def to_messages(self, messages: List[CanonicalMessage]) -> List[Dict[str, Any]]:
        """
        Convert canonical messages to OpenAI format.

        OpenAI format:
        [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..." or [...content blocks...]},
            {"role": "assistant", "content": "...", "tool_calls": [...]},
            {"role": "tool", "tool_call_id": "...", "content": "..."}
        ]
        """
        result = []

        for msg in messages:
            message = self._build_message(msg)
            if message:
                result.append(message)

        return result

    def _build_message(self, msg: CanonicalMessage) -> Optional[Dict[str, Any]]:
        """Build an OpenAI message from a canonical message."""
        if msg.role == "system":
            return {"role": "system", "content": msg.content}

        elif msg.role == "user":
            # Check if we need content blocks (images)
            if msg.images:
                content = self._build_content_with_images(msg.content, msg.images)
                return {"role": "user", "content": content}
            elif msg.tool_results:
                # Tool results come as separate messages in OpenAI
                # This shouldn't normally happen in canonical format, but handle it
                return None  # Skip - tool results handled separately
            else:
                return {"role": "user", "content": msg.content}

        elif msg.role == "assistant":
            message = {"role": "assistant", "content": msg.content or None}

            # Add tool calls if present
            if msg.tool_calls:
                message["tool_calls"] = []
                for tc in msg.tool_calls:
                    message["tool_calls"].append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    })

            return message

        elif msg.role == "tool":
            # Tool result messages
            if msg.tool_results:
                # Return first tool result as a message
                # Multiple tool results should be multiple messages
                tr = msg.tool_results[0]
                return {
                    "role": "tool",
                    "tool_call_id": tr.tool_call_id,
                    "content": tr.result
                }

        return None

    def _build_content_with_images(
        self,
        text: str,
        images: List[ImageData]
    ) -> List[Dict[str, Any]]:
        """Build content array with images for OpenAI."""
        content = []

        # Add images first
        for img in images:
            prepared = self.prepare_image(img)
            if "url" in prepared:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": prepared["url"],
                        "detail": "auto"
                    }
                })
            else:
                # Base64 encoded image - OpenAI uses data URL format
                data_url = f"data:{prepared.get('mime_type', 'image/png')};base64,{prepared['data']}"
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": data_url,
                        "detail": "auto"
                    }
                })

        # Add text last
        content.append({
            "type": "text",
            "text": text
        })

        return content

    def from_response(self, response: Any) -> CanonicalResponse:
        """
        Convert OpenAI response to canonical format.

        Handles:
        - Text content
        - Tool calls
        - Usage statistics with caching info
        """
        message = response.choices[0].message

        # Extract text
        text = message.content or ""

        # Extract tool calls
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments JSON
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}

                tool_calls.append(CanonicalToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args
                ))

        # is_final when there are no tool calls
        is_final = len(tool_calls) == 0

        # Extract usage if available
        usage = {}
        if hasattr(response, 'usage') and response.usage:
            usage_obj = response.usage
            usage = {
                "input_tokens": getattr(usage_obj, 'prompt_tokens', 0),
                "output_tokens": getattr(usage_obj, 'completion_tokens', 0),
            }
            # Check for cached tokens
            if hasattr(usage_obj, 'prompt_tokens_details') and usage_obj.prompt_tokens_details:
                usage["cached_tokens"] = getattr(usage_obj.prompt_tokens_details, 'cached_tokens', 0)

        return CanonicalResponse(
            text=text,
            tool_calls=tool_calls,
            is_final=is_final,
            usage=usage
        )

    def add_tool_results(
        self,
        messages: List[Dict[str, Any]],
        response: CanonicalResponse,
        tool_results: List[CanonicalToolResult]
    ) -> List[Dict[str, Any]]:
        """
        Add tool results to messages for next OpenAI API call.

        OpenAI requires:
        1. Assistant message with tool_calls
        2. Tool messages with results (one per tool call)
        """
        # Build assistant message with tool calls
        assistant_tool_calls = []
        for tc in response.tool_calls:
            assistant_tool_calls.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments)
                }
            })

        messages.append({
            "role": "assistant",
            "content": response.text or None,
            "tool_calls": assistant_tool_calls
        })

        # Add tool result messages (one per result)
        for tr in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": tr.tool_call_id,
                "content": tr.result
            })

        return messages

    # =========================================================================
    # TOOL CONVERSION
    # =========================================================================

    def to_tools(self, tools: List[CanonicalTool]) -> List[Dict[str, Any]]:
        """
        Convert canonical tools to OpenAI format.

        OpenAI format:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "What the tool does",
                "parameters": {...}
            }
        }
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }
            for tool in tools
        ]

    def to_tools_from_functions(self, functions: List[Callable]) -> List[Dict[str, Any]]:
        """
        Convert Python functions directly to OpenAI tool format.
        """
        from backend.llm_adapters.tool_schemas import build_openai_tools
        return build_openai_tools(functions)

    def get_web_search_tool(self) -> Dict[str, Any]:
        """
        Get OpenAI web search tool definition.

        Returns:
            OpenAI web search tool (Bing Search Preview)
        """
        return {
            "type": self.WEB_SEARCH_TOOL_TYPE,
            "search_context_size": self.WEB_SEARCH_CONTEXT_SIZE
        }

    # =========================================================================
    # SYSTEM PROMPT HANDLING
    # =========================================================================

    def get_system_prompt_config(self, system_prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Get system prompt as OpenAI message.

        OpenAI includes system prompt as the first message.

        Args:
            system_prompt: The system prompt text

        Returns:
            System message dict
        """
        return {"role": "system", "content": system_prompt}

    # =========================================================================
    # HISTORY CONVERSION
    # =========================================================================

    def to_history(self, messages: List[CanonicalMessage]) -> List[Dict[str, Any]]:
        """
        Serialize canonical messages for storage in OpenAI format.

        OpenAI history format:
        [{"role": "user"|"assistant", "content": "..."}]
        """
        result = []
        for msg in messages:
            if msg.role == "system":
                continue  # System messages usually not stored in history

            role = msg.role
            content = msg.content

            if content:
                result.append({
                    "role": role,
                    "content": content
                })

        return result

    def from_history(self, history: List[Dict[str, Any]]) -> List[CanonicalMessage]:
        """
        Deserialize messages from OpenAI stored format.

        Also handles Gemini format for cross-provider compatibility.
        """
        result = []
        for h in history:
            role = h.get("role", "user")

            # Handle Gemini's "model" role
            if role == "model":
                role = "assistant"

            # Support both "parts" (Gemini format) and "content" (OpenAI format)
            if "parts" in h:
                parts = h["parts"]
                if isinstance(parts, list) and len(parts) > 0:
                    content = parts[0] if isinstance(parts[0], str) else parts[0].get("text", "")
                else:
                    content = str(parts)
            else:
                content = h.get("content", "")

            result.append(CanonicalMessage(role=role, content=content))

        return result

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def build_content_with_images(
        self,
        text: str,
        images: Optional[List[ImageData]] = None
    ) -> Union[str, List[Dict[str, Any]]]:
        """
        Build message content with optional images for OpenAI.

        Args:
            text: The text message
            images: Optional list of images

        Returns:
            String (text only) or list of content blocks (with images)
        """
        if not images:
            return text

        return self._build_content_with_images(text, images)

    def log_cache_usage(self, response: Any, model_name: str = "") -> None:
        """
        Log cache usage statistics from OpenAI response.

        OpenAI automatically caches prompts >= 1024 tokens.
        GPT-4o: 50% discount, GPT-4.1: 75% discount on cached tokens.
        """
        if hasattr(response, 'usage') and response.usage:
            usage = response.usage
            input_tokens = getattr(usage, 'prompt_tokens', 0)
            output_tokens = getattr(usage, 'completion_tokens', 0)

            # Check for cached tokens in prompt_tokens_details
            cached_tokens = 0
            if hasattr(usage, 'prompt_tokens_details') and usage.prompt_tokens_details:
                cached_tokens = getattr(usage.prompt_tokens_details, 'cached_tokens', 0)

            if cached_tokens > 0:
                # Calculate savings (cached = 50% for GPT-4o, 75% for GPT-4.1)
                discount = 0.75 if "4.1" in model_name else 0.5
                savings_pct = (cached_tokens * discount) / max(input_tokens, 1) * 100
                self.log(f"💾 Cache: cached={cached_tokens}, input={input_tokens}, output={output_tokens}")
                self.log(f"💰 Cache savings: ~{savings_pct:.1f}% ({int(discount*100)}% discount)")
            else:
                self.log(f"📊 Usage: input={input_tokens}, output={output_tokens} (no cache hit)")

