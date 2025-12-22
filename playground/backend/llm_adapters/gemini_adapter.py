"""
Gemini Provider Adapter - Translates between canonical and Gemini formats

Handles Gemini-specific requirements:
1. Content format: types.Content with parts list
2. Role mapping: "assistant" -> "model"
3. Tool definitions: types.Tool with FunctionDeclaration
4. Google Search: types.GoogleSearch() for web search
5. Thinking mode: types.ThinkingConfig for reasoning output
6. System prompt: system_instruction in GenerateContentConfig (not in messages)
"""

from typing import List, Dict, Any, Optional, Callable
import json
import base64

from google.genai import types

from backend.llm_adapters.base import BaseProviderAdapter, register_adapter
from backend.llm_adapters.canonical import (
    CanonicalMessage,
    CanonicalToolCall,
    CanonicalToolResult,
    CanonicalTool,
    CanonicalResponse,
    ImageData,
)


@register_adapter("gemini")
class GeminiAdapter(BaseProviderAdapter):
    """
    Adapter for Google Gemini models.

    Gemini uses types.Content with lists of types.Part for messages.
    Role mapping: "assistant" -> "model"
    """

    @property
    def provider_name(self) -> str:
        return "Gemini"

    # =========================================================================
    # MESSAGE CONVERSION
    # =========================================================================

    def to_messages(self, messages: List[CanonicalMessage]) -> List[types.Content]:
        """
        Convert canonical messages to Gemini Content format.

        Gemini format:
        [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text="..."), ...]
            ),
            types.Content(
                role="model",
                parts=[types.Part.from_text(text="..."), ...]
            )
        ]
        """
        result = []

        for msg in messages:
            # Skip system messages - Gemini handles them via system_instruction
            if msg.role == "system":
                continue

            # Map role: assistant -> model
            role = "model" if msg.role == "assistant" else msg.role

            parts = self._build_parts(msg)

            if parts:  # Only add if there are parts
                result.append(types.Content(role=role, parts=parts))

        return result

    def _build_parts(self, msg: CanonicalMessage) -> List[types.Part]:
        """Build Gemini Part list from a canonical message."""
        parts = []

        # Add images
        for img in msg.images:
            prepared = self.prepare_image(img)
            if "url" in prepared:
                # Gemini supports URL-based images via from_uri
                parts.append(types.Part.from_uri(
                    file_uri=prepared["url"],
                    mime_type="image/jpeg"  # Default, will be auto-detected
                ))
            else:
                # Base64 encoded image - convert to bytes for Gemini
                image_bytes = base64.b64decode(prepared["data"])
                parts.append(types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=prepared.get("mime_type", "image/png")
                ))

        # Add text content
        if msg.content:
            parts.append(types.Part.from_text(text=msg.content))

        # Add tool calls (for model messages)
        for tc in msg.tool_calls:
            parts.append(types.Part.from_function_call(
                name=tc.name,
                args=tc.arguments
            ))

        # Add tool results (for user messages)
        for tr in msg.tool_results:
            # Parse result JSON back to dict for Gemini
            try:
                result_dict = json.loads(tr.result)
            except json.JSONDecodeError:
                result_dict = {"result": tr.result}

            parts.append(types.Part.from_function_response(
                name=tr.name,
                response=result_dict
            ))

        return parts

    def from_response(self, response: Any) -> CanonicalResponse:
        """
        Convert Gemini response to canonical format.

        Handles:
        - Text parts
        - Function call parts
        - Thought parts (thinking mode)
        - Error handling for malformed function calls
        """
        text = ""
        thinking = ""
        tool_calls = []

        # Check for errors first
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, 'finish_reason', None)

            if str(finish_reason) == "FinishReason.MALFORMED_FUNCTION_CALL":
                self.log("MALFORMED_FUNCTION_CALL detected")
                return CanonicalResponse(
                    text="I encountered an error while processing. Please try a more specific question.",
                    tool_calls=[],
                    is_final=True
                )

            # Extract content from candidate
            if hasattr(candidate, 'content') and candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    # Check for thinking/thought part
                    if hasattr(part, 'thought') and part.thought and hasattr(part, 'text') and part.text:
                        thinking += part.text
                    elif hasattr(part, 'text') and part.text:
                        text += part.text
                    elif hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call
                        tool_calls.append(CanonicalToolCall(
                            id=f"{fc.name}_{len(tool_calls)}",  # Gemini doesn't provide IDs
                            name=fc.name,
                            arguments=dict(fc.args) if fc.args else {}
                        ))

        # Also check response.text shortcut
        if not text and hasattr(response, 'text') and response.text:
            text = response.text

        # Also check response.function_calls shortcut (for non-streaming)
        if not tool_calls and hasattr(response, 'function_calls') and response.function_calls:
            for fc in response.function_calls:
                tool_calls.append(CanonicalToolCall(
                    id=f"{fc.name}_{len(tool_calls)}",
                    name=fc.name,
                    arguments=dict(fc.args) if fc.args else {}
                ))

        # is_final when there are no tool calls
        is_final = len(tool_calls) == 0

        # Extract usage if available
        usage = {}
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage_obj = response.usage_metadata
            usage = {
                "input_tokens": getattr(usage_obj, 'prompt_token_count', 0) or 0,
                "output_tokens": getattr(usage_obj, 'candidates_token_count', 0) or 0,
                "cached_tokens": getattr(usage_obj, 'cached_content_token_count', 0) or 0,
            }

        return CanonicalResponse(
            text=text,
            tool_calls=tool_calls,
            thinking=thinking,
            is_final=is_final,
            usage=usage
        )

    def add_tool_results(
        self,
        messages: List[types.Content],
        response: CanonicalResponse,
        tool_results: List[CanonicalToolResult]
    ) -> List[types.Content]:
        """
        Add tool results to messages for next Gemini API call.

        Gemini requires:
        1. Model message with function_call parts
        2. User message with function_response parts
        """
        # Build model message with function calls
        function_call_parts = []
        for tc in response.tool_calls:
            function_call_parts.append(types.Part.from_function_call(
                name=tc.name,
                args=tc.arguments
            ))

        messages.append(types.Content(role="model", parts=function_call_parts))

        # Build user message with function responses
        function_response_parts = []
        for tr in tool_results:
            # Parse result JSON back to dict for Gemini
            try:
                result_dict = json.loads(tr.result)
            except json.JSONDecodeError:
                result_dict = {"result": tr.result}

            function_response_parts.append(types.Part.from_function_response(
                name=tr.name,
                response=result_dict
            ))

        messages.append(types.Content(role="user", parts=function_response_parts))

        return messages

    # =========================================================================
    # TOOL CONVERSION
    # =========================================================================

    def to_tools(self, tools: List[CanonicalTool]) -> List[types.Tool]:
        """
        Convert canonical tools to Gemini format.

        Gemini format:
        [types.Tool(function_declarations=[
            FunctionDeclaration(name="...", description="...", parameters={...})
        ])]
        """
        declarations = []
        for tool in tools:
            declarations.append(types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters
            ))

        return [types.Tool(function_declarations=declarations)]

    def to_tools_from_functions(self, functions: List[Callable]) -> List[types.Tool]:
        """
        Convert Python functions directly to Gemini tool format.

        This is a convenience method that mirrors the existing approach.
        """
        from backend.llm_adapters.tool_schemas import build_gemini_tool_schema

        declarations = []
        for func in functions:
            schema = build_gemini_tool_schema(func)
            declarations.append(types.FunctionDeclaration(
                name=schema["name"],
                description=schema["description"],
                parameters=schema["parameters"]
            ))

        return [types.Tool(function_declarations=declarations)]

    def get_web_search_tool(self) -> types.Tool:
        """
        Get Gemini web search tool (Google Search).

        Returns:
            Gemini Google Search tool definition
        """
        return types.Tool(google_search=types.GoogleSearch())

    # =========================================================================
    # SYSTEM PROMPT HANDLING
    # =========================================================================

    def get_system_prompt_config(self, system_prompt: str, **kwargs) -> str:
        """
        Get system prompt for Gemini.

        Gemini uses system_instruction parameter in GenerateContentConfig,
        which is just a string (not structured like Anthropic).

        Args:
            system_prompt: The system prompt text

        Returns:
            The system prompt string
        """
        return system_prompt

    def get_thinking_config(self, budget_tokens: int = 8192) -> types.ThinkingConfig:
        """
        Get Gemini thinking configuration.

        Args:
            budget_tokens: Maximum tokens for thinking

        Returns:
            ThinkingConfig for Gemini 2.5+ models
        """
        return types.ThinkingConfig(
            thinking_budget=budget_tokens,
            include_thoughts=True
        )

    # =========================================================================
    # HISTORY CONVERSION
    # =========================================================================

    def to_history(self, messages: List[CanonicalMessage]) -> List[Dict[str, Any]]:
        """
        Serialize canonical messages for storage in Gemini format.

        Gemini history format:
        [{"role": "user"|"model", "parts": ["text", ...]}]
        """
        result = []
        for msg in messages:
            if msg.role == "system":
                continue

            role = "model" if msg.role == "assistant" else msg.role
            parts = []

            if msg.content:
                parts.append(msg.content)

            if parts:
                result.append({
                    "role": role,
                    "parts": parts
                })

        return result

    def from_history(self, history: List[Dict[str, Any]]) -> List[CanonicalMessage]:
        """
        Deserialize messages from Gemini stored format.
        """
        result = []
        for h in history:
            role = h.get("role", "user")
            if role == "model":
                role = "assistant"

            # Support both "parts" (Gemini format) and "content" (standard format)
            parts = h.get("parts", [])
            if isinstance(parts, list) and len(parts) > 0:
                content = parts[0] if isinstance(parts[0], str) else parts[0].get("text", "")
            elif "content" in h:
                content = h.get("content", "")
            else:
                content = str(parts)

            result.append(CanonicalMessage(role=role, content=content))

        return result

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def build_content_with_images(
        self,
        text: str,
        images: Optional[List[ImageData]] = None
    ) -> List[types.Part]:
        """
        Build message content with optional images for Gemini.

        Args:
            text: The text message
            images: Optional list of images

        Returns:
            List of Gemini Part objects
        """
        parts = []

        # Add images first
        if images:
            for img in images:
                prepared = self.prepare_image(img)
                if "url" in prepared:
                    parts.append(types.Part.from_uri(
                        file_uri=prepared["url"],
                        mime_type="image/jpeg"
                    ))
                else:
                    image_bytes = base64.b64decode(prepared["data"])
                    parts.append(types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=prepared.get("mime_type", "image/png")
                    ))

        # Add text last
        parts.append(types.Part.from_text(text=text))

        return parts

    def log_cache_usage(self, response: Any, model_name: str = "") -> None:
        """
        Log cache usage statistics from Gemini response.

        Gemini 2.5 has implicit caching with 90% discount.
        Gemini 2.0 has 75% discount.
        """
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
            output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
            cached_tokens = getattr(usage, 'cached_content_token_count', 0) or 0

            if cached_tokens > 0:
                # Gemini 2.5: 90% discount, Gemini 2.0: 75% discount
                discount = 0.90 if "2.5" in model_name else 0.75
                savings_pct = (cached_tokens * discount) / max(input_tokens, 1) * 100
                self.log(f"💾 Cache: cached={cached_tokens}, input={input_tokens}, output={output_tokens}")
                self.log(f"💰 Cache savings: ~{savings_pct:.1f}% ({int(discount*100)}% discount)")
            else:
                self.log(f"📊 Usage: input={input_tokens}, output={output_tokens} (no cache hit)")
