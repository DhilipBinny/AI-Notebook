"""
Anthropic LLM Client - Claude implementation

Implements the BaseLLMClient interface for Anthropic models (Claude 3, etc.).
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

from typing import List, Dict, Any, Optional, Union, Callable
from anthropic import Anthropic

from backend.llm_clients.base import BaseLLMClient, ImageData, prepare_image, LLMResponse, ToolCall, ToolResult
from backend.llm_adapters.tool_schemas import build_anthropic_tools
from backend.utils.util_func import log
from backend.llm_tools import TOOL_FUNCTIONS, AI_CELL_TOOLS
import backend.config as cfg

# Import the new adapter for gradual migration
from backend.llm_adapters import AnthropicAdapter, CanonicalToolResult, CanonicalResponse


# =============================================================================
# SECTION 1: MODULE-LEVEL SETUP
# =============================================================================
# Constants, tool definitions, and module-level helpers

# Map function names to actual functions
TOOL_MAP = {func.__name__: func for func in TOOL_FUNCTIONS}


class AnthropicClient(BaseLLMClient):
    """Anthropic LLM client with tool calling and web search support"""

    # =========================================================================
    # SECTION 2: INITIALIZATION & CONFIGURATION
    # =========================================================================

    def __init__(self, api_key: str, model_name: str = None, auto_function_calling: Optional[bool] = None, enable_web_search: bool = True):
        """
        Initialize Anthropic client.

        Args:
            api_key: Anthropic API key
            model_name: Model to use (default: claude-3-haiku-20240307)
            auto_function_calling: Override config setting. If None, uses cfg.AUTO_FUNCTION_CALLING
            enable_web_search: Enable web search tool for real-time web info (default: True)
        """
        super().__init__()  # Initialize base class (cancellation support)

        self.client = Anthropic(api_key=api_key)
        self.model_name = model_name or cfg.ANTHROPIC_MODEL
        self.enable_web_search = enable_web_search

        # Initialize the adapter for format translation
        self.adapter = AnthropicAdapter()

        # Build base tools list (without web search - added dynamically per request)
        self.tools = build_anthropic_tools(TOOL_FUNCTIONS)

        log(f"Anthropic web search: {'enabled' if enable_web_search else 'disabled'} (added dynamically when needed)")

        self.history: List[Dict[str, Any]] = []

        # Use config value if not explicitly set
        self.auto_function_calling = auto_function_calling if auto_function_calling is not None else cfg.AUTO_FUNCTION_CALLING
        log("Anthropic client initialized")
        log(f"Config: tool_mode={cfg.TOOL_EXECUTION_MODE}, auto_func={self.auto_function_calling} (request may override)")
        log(f"Web search enabled: {self.enable_web_search}")

        # Store pending state for manual mode
        self._pending_messages: List[Dict[str, Any]] = []
        self._pending_tool_calls: List[Dict[str, Any]] = []

        # Cache AI Cell tools (built once)
        self._ai_cell_tools_cache: Optional[List[Dict[str, Any]]] = None
        self._ai_cell_tool_map_cache: Optional[Dict[str, Any]] = None

    def _get_tools_for_request(self, message: str, user_message: str = None) -> List[Dict[str, Any]]:
        """
        Get tools list for this request, conditionally adding web search.

        Args:
            message: The full message
            user_message: Optional - just the user's question (for keyword detection)

        Returns:
            List of tools, including web search tool if needed
        """
        tools = self.tools.copy()

        # Add web search tool only if keywords suggest it's needed
        if self._needs_web_search(message, user_message):
            tools.append(self.adapter.get_web_search_tool(max_uses=5))
            log("🌐 Web search tool added to this request")

        return tools

    def _call_chat_api(self, messages: Any, tools: Any) -> Any:
        """
        Make Anthropic Chat API call. Used by base class consolidated methods.

        Args:
            messages: Anthropic message format
            tools: Anthropic tool definitions

        Returns:
            Raw Anthropic API response
        """
        return self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            system=self.adapter.get_system_prompt_config(self.SYSTEM_PROMPT, cache=True),
            messages=messages,
            tools=tools
        )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens using Anthropic's native API.

        Args:
            text: The text to count tokens for

        Returns:
            Token count, or 0 if counting fails
        """
        try:
            token_count = self.client.messages.count_tokens(
                model=self.model_name,
                messages=[{"role": "user", "content": text}]
            )
            return token_count.input_tokens
        except Exception:
            return 0

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
        Send a message to Anthropic with proper caching.

        Args:
            notebook_context: Formatted notebook context (cached - Layer 2)
            user_prompt: User's question/prompt (never cached - Layer 3)
            images: Optional list of images for visual analysis

        Two-Layer Caching:
        - Layer 1: System prompt (Anthropic API-side cache via cache_control)
        - Layer 2: Notebook context (cached here with cache_control)
        - Layer 3: User prompt (never cached)

        Returns:
            str: Final response text (if auto mode or no tools needed)
            dict: {"pending_tool_calls": [...], "response_text": "..."} (if manual mode with tools)
        """
        try:
            from backend.utils.util_func import log_chat
            mode = "auto" if self.auto_function_calling else "manual"

            # Count tokens using self.count_tokens()
            full_text = f"{notebook_context}\n\n{user_prompt}" if notebook_context else user_prompt
            input_tokens = self.count_tokens(full_text)

            log_chat(
                provider="Anthropic",
                model=self.model_name,
                mode=mode,
                context_chars=len(notebook_context),
                prompt_chars=len(user_prompt),
                images=len(images) if images else 0,
                web_search=self.enable_web_search,
                input_tokens=input_tokens
            )

            # Build content with proper caching layers
            content = self._build_cached_message_content(notebook_context, user_prompt, images)

            # Add user message to history
            self.history.append({
                "role": "user",
                "content": content
            })

            # Build messages (Anthropic system prompt is separate)
            messages = self.history

            # Get tools for this request (conditionally includes web search based on user_prompt)
            # Combine context + prompt for web search detection
            full_message = f"{notebook_context}\n\n{user_prompt}" if notebook_context else user_prompt
            request_tools = self._get_tools_for_request(full_message, user_prompt)

            if self.auto_function_calling:
                # Auto mode: loop until final response (uses consolidated base class method)
                log("🤖 Anthropic AUTO mode - executing tools automatically")
                return self._chat_auto_execute_tools(messages, request_tools, TOOL_MAP)
            else:
                # Manual mode: return pending tools for approval (uses consolidated base class method)
                log("🤖 Anthropic MANUAL mode - returning tools for approval")
                return self._chat_get_pending_tools(messages, request_tools)

        except Exception as e:
            log(f"❌ Anthropic error: {e}")
            return f"Anthropic Error: {e}"

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
        """
        Set conversation history.

        Expects Anthropic format: [{"role": "user"|"assistant", "content": ...}]
        """
        self.history = []
        for msg in history_list:
            role = msg.get("role", "user")
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
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            log(f"Anthropic simple_completion error: {e}")
            raise

    def ai_cell_simple(
        self,
        notebook_context: str,
        user_prompt: str,
        images: Optional[List[ImageData]] = None
    ) -> str:
        """
        AI Cell completion - with web search but no notebook tools.
        Used for inline Q&A in AI cells. Supports image inputs.
        Uses prompt caching for notebook context.

        Args:
            notebook_context: Formatted notebook context (cacheable - Layer 2)
            user_prompt: User's question/prompt (never cached - Layer 3)
            images: Optional list of images to analyze

        Returns:
            The response text from the LLM (may include web search results)
        """
        try:
            log("🤖 Anthropic AI Cell completion starting...")
            log(f"   Context: {len(notebook_context)} chars (Layer 2 - cached)")
            log(f"   User prompt: {len(user_prompt)} chars (Layer 3 - not cached)")
            if images:
                log(f"📷 Including {len(images)} image(s)")

            # Anthropic has web search via tool - use adapter for consistent definition
            tools = []
            if self._needs_web_search(user_prompt, user_prompt):
                tools.append(self.adapter.get_web_search_tool(max_uses=3))
                log("🌐 Web search tool added to AI Cell request")

            # Build content with proper caching layers (clean approach - no splitting)
            content = self._build_cached_message_content(notebook_context, user_prompt, images)

            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                messages=[{"role": "user", "content": content}],
                tools=tools if tools else None,
            )

            # Log cache usage
            self._log_cache_usage(response)

            # Use adapter to parse response
            canonical = self.adapter.from_response(response)

            log(f"🤖 Anthropic AI Cell response: {len(canonical.text)} chars")
            return canonical.text

        except Exception as e:
            log(f"Anthropic ai_cell_simple error: {e}")
            raise

    # =========================================================================
    # SECTION 6: AI CELL - Tool Execution Framework
    # =========================================================================
    # These methods implement the unified tool execution interface for AI Cells
    # Used for notebook inspection and code execution tools

    def _get_ai_cell_tools(self) -> List[Dict[str, Any]]:
        """
        Get AI Cell tools in Anthropic format.
        Uses cached tools to avoid rebuilding on each call.
        """
        if self._ai_cell_tools_cache is None:
            self._ai_cell_tools_cache = build_anthropic_tools(AI_CELL_TOOLS)
        return self._ai_cell_tools_cache

    def _get_ai_cell_tool_map(self) -> Dict[str, Callable]:
        """Get mapping of tool names to callable functions for AI Cell."""
        if self._ai_cell_tool_map_cache is None:
            self._ai_cell_tool_map_cache = {func.__name__: func for func in AI_CELL_TOOLS}
        return self._ai_cell_tool_map_cache

    def _get_web_search_tool(self) -> Optional[Dict[str, Any]]:
        """Get Anthropic web search tool definition via adapter."""
        if not self.enable_web_search:
            return None
        return self.adapter.get_web_search_tool(max_uses=3)

    def _prepare_ai_cell_messages(
        self,
        notebook_context: str,
        user_prompt: str,
        images: Optional[List[ImageData]] = None
    ) -> List[Dict[str, Any]]:
        """
        Prepare initial messages for AI Cell in Anthropic format with proper caching.

        Args:
            notebook_context: Formatted notebook context (cacheable - Layer 2)
            user_prompt: User's question/prompt (never cached - Layer 3)
            images: Optional images
        """
        # Use the clean caching method - no splitting needed!
        content = self._build_cached_message_content(notebook_context, user_prompt, images)

        # Debug: log what we're sending
        log(f"📋 AI Cell messages: {len(content)} content blocks")
        for i, block in enumerate(content):
            block_type = block.get("type", "unknown")
            if block_type == "image":
                source_type = block.get("source", {}).get("type", "unknown")
                mime = block.get("source", {}).get("media_type", "N/A")
                data_len = len(block.get("source", {}).get("data", ""))
                log(f"   Block {i}: type=image, source_type={source_type}, mime={mime}, data_len={data_len}")
            else:
                has_cache = "cache_control" in block
                text_preview = str(block.get("text", ""))[:50]
                log(f"   Block {i}: type={block_type}, cached={has_cache}, preview='{text_preview}...'")

        return [{"role": "user", "content": content}]

    def _call_llm_for_ai_cell(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> LLMResponse:
        """
        Make an LLM API call for AI Cell tool execution.
        Enables extended thinking for Claude models that support it.

        Args:
            messages: Anthropic message format
            tools: Anthropic tool format

        Returns:
            LLMResponse with text, tool_calls, thinking, and is_final flag
        """
        # Check if model supports extended thinking
        # Supported: claude-sonnet-4-5, claude-sonnet-4, claude-opus-4, etc.
        thinking_enabled = any(x in self.model_name for x in ["sonnet-4", "opus-4", "sonnet-3-7", "haiku-4"])

        if thinking_enabled:
            log(f"💭 Anthropic extended thinking enabled for {self.model_name}")
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=16000,  # Need higher limit for thinking
                system=self.adapter.get_system_prompt_config(self.AI_CELL_SYSTEM_PROMPT, cache=True),  # Layer 1: Cached AI Cell system prompt
                messages=messages,
                tools=tools,
                thinking={
                    "type": "enabled",
                    "budget_tokens": 8192  # Allow up to 8K tokens for thinking
                }
            )
        else:
            log(f"💭 Extended thinking not supported for {self.model_name}")
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=self.adapter.get_system_prompt_config(self.AI_CELL_SYSTEM_PROMPT, cache=True),  # Layer 1: Cached AI Cell system prompt
                messages=messages,
                tools=tools,
            )

        # Log cache usage
        self._log_cache_usage(response)

        # Use adapter to parse response (centralized parsing logic)
        canonical = self.adapter.from_response(response)

        # Convert canonical tool calls back to LLMResponse format for backward compatibility
        tool_calls = [
            ToolCall(id=tc.id, name=tc.name, arguments=tc.arguments)
            for tc in canonical.tool_calls
        ]

        if canonical.thinking:
            log(f"💭 Anthropic total thinking: {len(canonical.thinking)} chars, raw blocks: {len(canonical.raw_provider_blocks)}")

        return LLMResponse(
            text=canonical.text,
            tool_calls=tool_calls,
            is_final=canonical.is_final,
            thinking=canonical.thinking,
            raw_thinking_blocks=canonical.raw_provider_blocks,
            usage=canonical.usage if canonical.usage else None
        )

    def _add_tool_results_to_messages(self, messages: List[Dict[str, Any]], response: 'LLMResponse', tool_results: List[ToolResult]) -> List[Dict[str, Any]]:
        """
        Add tool results to messages for the next Anthropic API call.

        Anthropic requires:
        1. Assistant message with tool_use blocks (from last response)
        2. User message with tool_result blocks

        When extended thinking is enabled:
        - Assistant message MUST start with thinking blocks
        - Thinking blocks MUST include the signature field (for verification)
        - We pass the raw thinking blocks which include the signature

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
            thinking=response.thinking,
            is_final=response.is_final,
            raw_provider_blocks=response.raw_thinking_blocks
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

        # Use adapter to add tool results (handles Anthropic-specific format)
        return self.adapter.add_tool_results(messages, canonical_response, canonical_results)

    # =========================================================================
    # SECTION 7: UTILITIES & HELPERS
    # =========================================================================

    def _build_cached_message_content(
        self,
        notebook_context: str,
        user_prompt: str,
        images: Optional[List[ImageData]] = None
    ) -> List[Dict[str, Any]]:
        """
        Build message content with proper Layer 2 caching (clean approach).

        Since we receive notebook_context and user_prompt separately (from context_manager),
        we can apply caching without any string splitting!

        Two-Layer Caching Strategy:
        - Layer 1: System prompt (Anthropic API-side cache via cache_control - not handled here)
        - Layer 2: Notebook context (cached here with cache_control)
        - Layer 3: User prompt (never cached)

        Args:
            notebook_context: Formatted notebook context (cacheable)
            user_prompt: User's question/prompt (never cached)
            images: Optional list of images (never cached)

        Returns:
            List of content blocks with cache_control on notebook_context
        """
        content = []

        # Add images first (if any) - these are dynamic, so no caching
        if images:
            for idx, img in enumerate(images):
                prepared = prepare_image(img)
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
                            "media_type": prepared["mime_type"],
                            "data": prepared["data"]
                        }
                    })

        # Add notebook context with cache_control if it exists and is large enough
        # Anthropic requires minimum ~1024 tokens for caching
        if notebook_context and len(notebook_context) >= 1024:
            content.append({
                "type": "text",
                "text": notebook_context,
                "cache_control": {"type": "ephemeral"}  # 5-minute cache (Layer 2)
            })
            log(f"💾 Layer 2 cache: notebook_context={len(notebook_context)} chars (cached)")
        elif notebook_context:
            # Context exists but too small to cache
            content.append({
                "type": "text",
                "text": notebook_context
            })
            log(f"📝 Layer 2: notebook_context={len(notebook_context)} chars (too small to cache)")

        # Add user prompt without caching (always dynamic - Layer 3)
        content.append({
            "type": "text",
            "text": user_prompt
        })
        log(f"📝 Layer 3: user_prompt={len(user_prompt)} chars (never cached)")

        return content
