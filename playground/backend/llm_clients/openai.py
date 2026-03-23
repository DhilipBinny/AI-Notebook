"""
OpenAI LLM Client - OpenAI API implementation

Implements the BaseLLMClient interface for OpenAI models (GPT-4, etc.).
Supports both automatic and manual (approval-based) function calling.
Includes web search tool for real-time web information.

SECTIONS:
1. Module-Level Setup (imports, constants, tool building)
2. Initialization & Configuration
3. Chat Panel - Main Conversation Interface
4. History Management
5. Simple Completions (No Tools)
6. AI Cell - Tool Execution Framework
7. Utilities & Helpers
"""

import json
from typing import List, Dict, Any, Optional, Union, Callable
from openai import OpenAI

from backend.llm_clients.base import BaseLLMClient, ImageData, prepare_image, LLMResponse, ToolCall, ToolResult
from backend.llm_adapters.tool_schemas import build_openai_tools
from backend.utils.util_func import log
from backend.llm_tools import TOOL_FUNCTIONS, AI_CELL_TOOLS, ALL_AI_CELL_TOOLS, ALL_AI_CELL_TOOL_MAP
import backend.config as cfg

# Import the adapter for gradual migration
from backend.llm_adapters import OpenAIAdapter, CanonicalToolResult, CanonicalResponse


# =============================================================================
# SECTION 1: MODULE-LEVEL SETUP
# =============================================================================
# Constants, tool definitions, and module-level helpers


def _safe_json_loads(json_str: str, default: Dict = None) -> Dict[str, Any]:
    """Safely parse JSON string, returning default on error."""
    if default is None:
        default = {}
    try:
        return json.loads(json_str) if json_str else default
    except json.JSONDecodeError as e:
        log(f"⚠️ JSON parse error: {e} - Input: {json_str[:100]}...")
        return default


# Map function names to actual functions
TOOL_MAP = {func.__name__: func for func in TOOL_FUNCTIONS}


class OpenAIClient(BaseLLMClient):
    """OpenAI LLM client with tool calling and web search support"""

    # =========================================================================
    # SECTION 2: INITIALIZATION & CONFIGURATION
    # =========================================================================

    def __init__(self, api_key: str, model_name: str = None, auto_function_calling: Optional[bool] = None, enable_web_search: bool = True, max_tokens: int = None):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model_name: Model to use (default: gpt-4o)
            auto_function_calling: Override config setting. If None, uses cfg.AUTO_FUNCTION_CALLING
            enable_web_search: Enable web search tool for real-time web info (default: True)
            max_tokens: Max tokens for responses (default: 4096)
        """
        super().__init__()  # Initialize base class (cancellation support)

        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name or cfg.OPENAI_MODEL
        self.enable_web_search = enable_web_search
        self.max_tokens = max_tokens  # None = use model default

        # Initialize the adapter for format translation
        self.adapter = OpenAIAdapter()

        # Build base tools list (without web search - added dynamically per request)
        self.tools = build_openai_tools(TOOL_FUNCTIONS)

        self.history: List[Dict[str, Any]] = []

        # Use config value if not explicitly set
        self.auto_function_calling = auto_function_calling if auto_function_calling is not None else cfg.AUTO_FUNCTION_CALLING

        # Store pending state for manual mode
        self._pending_messages: List[Dict[str, Any]] = []
        self._pending_tool_calls: List[Dict[str, Any]] = []

        # Cache AI Cell tools (built once)
        self._ai_cell_tools_cache: Optional[List[Dict[str, Any]]] = None
        self._ai_cell_tool_map_cache: Optional[Dict[str, Callable]] = None

        log(f"{self._provider_display_name} client initialized: {self.model_name}")
        log(f"Config: tool_mode={cfg.TOOL_EXECUTION_MODE}, auto_func={self.auto_function_calling}, max_tokens={self.max_tokens}")

    @property
    def _provider_display_name(self) -> str:
        """Get display name for logging. Override in subclasses if needed."""
        return self.adapter.provider_name

    def _get_tools_for_request(self, message: str, user_message: str = None) -> List[Dict[str, Any]]:
        """
        Get tools list for this request, always including web search.
        The model decides when to actually call web search.
        """
        tools = self.tools.copy()

        if self.enable_web_search:
            tools.append(self.adapter.get_web_search_tool())

        return tools

    def _call_chat_api(self, messages: Any, tools: Any) -> Any:
        """
        Make OpenAI Chat API call. Used by base class consolidated methods.

        Args:
            messages: OpenAI message format
            tools: OpenAI tool definitions

        Returns:
            Raw OpenAI API response
        """
        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }
        if self.max_tokens:
            kwargs["max_tokens"] = self.max_tokens
        return self.client.chat.completions.create(**kwargs)

    # =========================================================================
    # SECTION 3: CHAT PANEL - Main Conversation Interface
    # =========================================================================
    # These methods handle the main chat panel conversations with full tool support

    def chat_panel_send(
        self,
        notebook_context: str,
        user_prompt: str,
        images: Optional[List[ImageData]] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Send a message to the LLM.

        Args:
            notebook_context: Formatted notebook context
            user_prompt: User's question/prompt
            images: Optional list of images for visual analysis

        Returns:
            str: Final response text (if auto mode or no tools needed)
            dict: {"pending_tool_calls": [...], "response_text": "..."} (if manual mode with tools)
        """
        provider = self._provider_display_name
        try:
            from backend.utils.util_func import log_chat

            mode = "auto" if self.auto_function_calling else "manual"

            # Count tokens using self.count_tokens() (inherited from base class)
            full_text = f"{notebook_context}\n\n{user_prompt}" if notebook_context else user_prompt
            input_tokens = self.count_tokens(full_text)

            log_chat(
                provider=provider,
                model=self.model_name,
                mode=mode,
                context_chars=len(notebook_context),
                prompt_chars=len(user_prompt),
                images=len(images) if images else 0,
                web_search=self.enable_web_search,
                max_tokens=self.max_tokens,
                input_tokens=input_tokens
            )

            # Combine context and user_prompt
            message = f"{notebook_context}\n\n{user_prompt}" if notebook_context else user_prompt

            # Build content with optional images
            content = self._build_content_with_images(message, images)

            # Add user message to history
            self.history.append({"role": "user", "content": content})

            # Build messages with system prompt
            messages = [{"role": "system", "content": self.SYSTEM_PROMPT}] + self.history

            # Get tools for this request (conditionally includes web search)
            request_tools = self._get_tools_for_request(message, user_prompt)

            if self.auto_function_calling:
                log(f"🤖 {provider} AUTO mode - executing tools automatically")
                return self._chat_auto_execute_tools(messages, request_tools, TOOL_MAP)
            else:
                log(f"🤖 {provider} MANUAL mode - returning tools for approval")
                return self._chat_get_pending_tools(messages, request_tools)

        except Exception as e:
            log(f"❌ {provider} error: {e}")
            error_msg = str(e)
            if "key" in error_msg.lower() or "auth" in error_msg.lower() or "sk-" in error_msg:
                return f"{provider} API error. Please check your API key configuration."
            return f"{provider} Error: An unexpected error occurred. Please try again."

    def execute_approved_tools(self, approved_tool_calls: List[Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
        """
        Execute approved tool calls and get the response.

        In manual mode, if the model wants more tools after execution,
        returns them for user approval instead of auto-executing.

        Uses consolidated base class method for tool execution.

        Args:
            approved_tool_calls: List of approved tools to execute
                                [{"id": "...", "name": "...", "arguments": {...}}, ...]

        Returns:
            str: Final response text if no more tools needed
            dict: {"pending_tool_calls": [...], "response_text": "..."} if more tools needed
        """
        return self._chat_execute_approved_tools(approved_tool_calls, TOOL_MAP, self.tools)

    # =========================================================================
    # SECTION 4: HISTORY MANAGEMENT
    # =========================================================================

    def clear_history(self) -> None:
        """Clear conversation history"""
        self.history = []
        self._pending_messages = []
        self._pending_tool_calls = []

    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""
        return self.history

    def set_history(self, history_list: List[Dict[str, Any]]) -> None:
        """Set conversation history."""
        self.history = []
        for msg in history_list:
            role = msg.get("role", "user")
            if role == "model":
                role = "assistant"

            if "parts" in msg:
                content = msg["parts"][0] if msg["parts"] else ""
            else:
                content = msg.get("content", "")

            self.history.append({
                "role": role,
                "content": content
            })

    # =========================================================================
    # SECTION 5: SIMPLE COMPLETIONS (No Tools)
    # =========================================================================
    # These methods are for simple LLM calls without tool execution

    def simple_completion(self, prompt: str, max_tokens: int = 1000) -> str:
        """
        Simple chat completion without tools.
        Used for summarization and other simple LLM tasks.

        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens in response

        Returns:
            The response text from the LLM
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            log(f"OpenAI simple_completion error: {e}")
            raise

    # =========================================================================
    # SECTION 6: AI CELL - Tool Execution Framework
    # =========================================================================
    # These methods implement the unified tool execution interface for AI Cells
    # Used for notebook inspection and code execution tools

    def _get_ai_cell_tools(self, allowed_tools: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get AI Cell tools in OpenAI format.
        Uses cached full set, then filters by allowed_tools if provided.
        """
        if self._ai_cell_tools_cache is None:
            self._ai_cell_tools_cache = build_openai_tools(ALL_AI_CELL_TOOLS)
        tools = self._ai_cell_tools_cache
        if allowed_tools is not None:
            allowed_set = set(allowed_tools)
            tools = [t for t in tools if t.get("function", {}).get("name") in allowed_set]
        return tools

    def _get_ai_cell_tool_map(self, allowed_tools: Optional[List[str]] = None) -> Dict[str, Callable]:
        """Get mapping of tool names to callable functions for AI Cell."""
        if self._ai_cell_tool_map_cache is None:
            self._ai_cell_tool_map_cache = dict(ALL_AI_CELL_TOOL_MAP)
        tool_map = self._ai_cell_tool_map_cache
        if allowed_tools is not None:
            allowed_set = set(allowed_tools)
            return {k: v for k, v in tool_map.items() if k in allowed_set}
        return tool_map

    def _prepare_ai_cell_messages(
        self,
        notebook_context: str,
        user_prompt: str,
        images: Optional[List[ImageData]] = None
    ) -> List[Dict[str, Any]]:
        """
        Prepare initial messages for AI Cell in OpenAI format.

        Args:
            notebook_context: Formatted notebook context
            user_prompt: User's question/prompt
            images: Optional images
        """
        # Combine context and user prompt
        full_prompt = f"{notebook_context}\n\n{user_prompt}" if notebook_context else user_prompt
        content = self._build_content_with_images(full_prompt, images)

        # Debug logging
        log(f"📋 AI Cell messages: context={len(notebook_context)} chars, user_prompt={len(user_prompt)} chars")
        if images:
            log(f"📷 Sending {len(images)} image(s) to OpenAI")

        # Include system prompt as first message
        return [
            {"role": "system", "content": self.AI_CELL_SYSTEM_PROMPT},
            {"role": "user", "content": content}
        ]

    def _call_llm_for_ai_cell(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> LLMResponse:
        """
        Make an LLM API call for AI Cell tool execution.

        Args:
            messages: OpenAI message format
            tools: OpenAI tool format

        Returns:
            LLMResponse with text, tool_calls, and is_final flag
        """
        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }
        if self.max_tokens:
            kwargs["max_tokens"] = self.max_tokens
        response = self.client.chat.completions.create(**kwargs)

        # Log cache usage
        self._log_cache_usage(response)

        message = response.choices[0].message

        # Extract text and tool calls
        text = message.content or ""
        tool_calls_list = []

        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls_list.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=_safe_json_loads(tc.function.arguments)
                ))

        # is_final when there are no tool calls
        is_final = len(tool_calls_list) == 0

        # Extract usage stats
        usage = None
        if hasattr(response, 'usage') and response.usage:
            usage_obj = response.usage
            usage = {
                "input_tokens": getattr(usage_obj, 'prompt_tokens', 0),
                "output_tokens": getattr(usage_obj, 'completion_tokens', 0),
                "cached_tokens": 0,
            }
            if hasattr(usage_obj, 'prompt_tokens_details') and usage_obj.prompt_tokens_details:
                usage["cached_tokens"] = getattr(usage_obj.prompt_tokens_details, 'cached_tokens', 0)

        return LLMResponse(
            text=text,
            tool_calls=tool_calls_list,
            is_final=is_final,
            usage=usage
        )

    def _add_tool_results_to_messages(self, messages: List[Dict[str, Any]], response: 'LLMResponse', tool_results: List[ToolResult]) -> List[Dict[str, Any]]:
        """
        Add tool results to messages for the next OpenAI API call.

        Now uses the adapter for centralized format handling.
        """
        from backend.llm_adapters.canonical import CanonicalToolCall as CanonicalTC

        # Convert LLMResponse to CanonicalResponse for adapter
        canonical_response = CanonicalResponse(
            text=response.text,
            tool_calls=[
                CanonicalTC(id=tc.id, name=tc.name, arguments=tc.arguments)
                for tc in response.tool_calls
            ],
            is_final=response.is_final
        )

        # Convert ToolResult to CanonicalToolResult for adapter
        canonical_results = [
            CanonicalToolResult(
                tool_call_id=tr.tool_call_id,
                name=tr.name,
                result=tr.result,
                is_error=tr.is_error
            )
            for tr in tool_results
        ]

        # Use adapter to add tool results (handles OpenAI-specific format)
        return self.adapter.add_tool_results(messages, canonical_response, canonical_results)

    # =========================================================================
    # SECTION 7: UTILITIES & HELPERS
    # =========================================================================

    def _build_content_with_images(self, text: str, images: Optional[List[ImageData]] = None) -> Union[str, List[Dict[str, Any]]]:
        """
        Build message content with optional images for OpenAI API.

        Args:
            text: The text message
            images: Optional list of images

        Returns:
            String (text only) or list of content blocks (with images)
        """
        if not images:
            return text

        content = []

        # Add images first
        for img in images:
            prepared = prepare_image(img)
            if "url" in prepared:
                # URL-based image
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": prepared["url"],
                        "detail": "auto"
                    }
                })
            else:
                # Base64 encoded image - OpenAI uses data URL format
                data_url = f"data:{prepared['mime_type']};base64,{prepared['data']}"
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
