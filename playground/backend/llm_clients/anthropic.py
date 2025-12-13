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

import json
import copy
from typing import List, Dict, Any, Optional, Union, Callable
from anthropic import Anthropic

from backend.llm_clients.base import BaseLLMClient, ImageData, prepare_image, LLMResponse, ToolCall, ToolResult, MAX_TOOL_ITERATIONS
from backend.llm_clients.tool_schemas import build_anthropic_tools
from backend.utils.util_func import log
from backend.llm_tools import TOOL_FUNCTIONS, AI_CELL_TOOLS
import backend.config as cfg


# =============================================================================
# SECTION 1: MODULE-LEVEL SETUP
# =============================================================================
# Constants, tool definitions, and module-level helpers

# Web search tool definition for Anthropic
WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5  # Limit searches per request
}

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

        # Build base tools list (without web search - added dynamically per request)
        self.tools = build_anthropic_tools(TOOL_FUNCTIONS)

        log(f"Anthropic web search: {'enabled' if enable_web_search else 'disabled'} (added dynamically when needed)")

        self.history: List[Dict[str, Any]] = []

        # Use config value if not explicitly set
        self.auto_function_calling = auto_function_calling if auto_function_calling is not None else cfg.AUTO_FUNCTION_CALLING
        log(f"Anthropic client initialized")
        log(f"Config: tool_mode={cfg.TOOL_EXECUTION_MODE}, auto_func={self.auto_function_calling} (request may override)")
        log(f"Web search enabled: {self.enable_web_search}")

        # Store pending state for manual mode
        self._pending_messages: List[Dict[str, Any]] = []
        self._pending_tool_calls: List[Dict[str, Any]] = []

        # Cache AI Cell tools (built once)
        self._ai_cell_tools_cache: Optional[List[Dict[str, Any]]] = None
        self._ai_cell_tool_map_cache: Optional[Dict[str, Any]] = None

        # Cache system prompts with cache_control (Layer 1 - static, rarely changes)
        self._cached_system_prompt: Optional[List[Dict[str, Any]]] = None
        self._cached_ai_cell_system_prompt: Optional[List[Dict[str, Any]]] = None

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
            tools.append(WEB_SEARCH_TOOL)
            log("🌐 Web search tool added to this request")

        return tools

    def _get_cached_system_prompt(self) -> List[Dict[str, Any]]:
        """
        Get system prompt in array format with cache_control (Layer 1 caching).

        Anthropic supports system prompt as array with cache_control:
        system=[{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}]

        This caches the system prompt for 5 minutes, reducing token costs by 90%
        for repeated requests. System prompts are static and rarely change.

        Returns:
            List with single text block containing system prompt with cache_control
        """
        if self._cached_system_prompt is None:
            self._cached_system_prompt = [
                {
                    "type": "text",
                    "text": self.SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
            log(f"💾 Cached system prompt: {len(self.SYSTEM_PROMPT)} chars")
        return self._cached_system_prompt

    def _get_cached_ai_cell_system_prompt(self) -> List[Dict[str, Any]]:
        """
        Get AI Cell system prompt in array format with cache_control (Layer 1 caching).

        Returns:
            List with single text block containing AI Cell system prompt with cache_control
        """
        if self._cached_ai_cell_system_prompt is None:
            self._cached_ai_cell_system_prompt = [
                {
                    "type": "text",
                    "text": self.AI_CELL_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
            log(f"💾 Cached AI Cell system prompt: {len(self.AI_CELL_SYSTEM_PROMPT)} chars")
        return self._cached_ai_cell_system_prompt

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
        - Layer 1: System prompt (cached via _get_cached_system_prompt)
        - Layer 2: Notebook context (cached here with cache_control)
        - Layer 3: User prompt (never cached)

        Returns:
            str: Final response text (if auto mode or no tools needed)
            dict: {"pending_tool_calls": [...], "response_text": "..."} (if manual mode with tools)
        """
        try:
            log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            log(f"📨 Anthropic chat_panel_send()")
            log(f"   Context: {len(notebook_context)} chars (Layer 2 - cached)")
            log(f"   User prompt: {len(user_prompt)} chars (Layer 3 - not cached)")
            if images:
                log(f"   Images: {len(images)} attached")
            log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

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
                # Auto mode: loop until final response
                log(f"🤖 Anthropic AUTO mode - executing tools automatically")
                return self._auto_execute_tools(messages, request_tools)
            else:
                # Manual mode: return pending tools for approval
                log(f"🤖 Anthropic MANUAL mode - returning tools for approval")
                return self._get_pending_tools(messages, request_tools)

        except Exception as e:
            log(f"❌ Anthropic error: {e}")
            return f"Anthropic Error: {e}"

    def _auto_execute_tools(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> str:
        """
        Execute tools automatically until we get a final response.

        Args:
            messages: Conversation messages
            tools: Tools to use for this request (defaults to self.tools if not provided)
        """
        request_tools = tools if tools is not None else self.tools
        iteration = 0

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1
            log(f"🔄 Anthropic iteration {iteration}/{MAX_TOOL_ITERATIONS}")

            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=self._get_cached_system_prompt(),  # Layer 1: Cached system prompt
                messages=messages,
                tools=request_tools
            )

            # Log cache usage
            self._log_cache_usage(response)

            # Log server tool usage (like web_search)
            for block in response.content:
                if block.type == "server_tool_use":
                    log(f"🌐 Anthropic web search: {block.name}")
                elif block.type == "web_search_tool_result":
                    result_count = len(block.content) if hasattr(block, 'content') else 0
                    log(f"🌐 Anthropic web search returned {result_count} results")

            # Check if stop_reason is tool_use
            if response.stop_reason == "tool_use":
                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Execute each tool call
                for block in response.content:
                    if block.type == "tool_use":
                        func_name = block.name
                        func_args = block.input
                        log(f"🔧 Anthropic calling tool: {func_name}")
                        result = self._execute_tool(func_name, func_args)

                        messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": result
                                }
                            ]
                        })
            else:
                # Final response - extract text from content blocks
                final_response = ""
                for block in response.content:
                    if hasattr(block, 'text') and block.text:
                        final_response += block.text
                self.history.append({
                    "role": "assistant",
                    "content": final_response
                })
                log(f"✅ Anthropic response received - {len(final_response)} chars")
                return final_response

        log(f"❌ Anthropic max iterations reached")
        return "Error: Maximum tool calling iterations reached"

    def _get_pending_tools(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Union[str, Dict[str, Any]]:
        """
        Get pending tool calls without executing them.

        Args:
            messages: Conversation messages
            tools: Tools to use for this request (defaults to self.tools if not provided)
        """
        request_tools = tools if tools is not None else self.tools
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            system=self._get_cached_system_prompt(),  # Layer 1: Cached system prompt
            messages=messages,
            tools=request_tools
        )

        # Log cache usage
        self._log_cache_usage(response)

        # Log server tool usage (like web_search)
        for block in response.content:
            if block.type == "server_tool_use":
                log(f"🌐 Anthropic web search: {block.name}")
            elif block.type == "web_search_tool_result":
                result_count = len(block.content) if hasattr(block, 'content') else 0
                log(f"🌐 Anthropic web search returned {result_count} results")

        if response.stop_reason == "tool_use":
            # Store state for later execution
            self._pending_messages = copy.deepcopy(messages)
            self._pending_tool_calls = []

            # Add assistant message to pending messages
            self._pending_messages.append({
                "role": "assistant",
                "content": response.content
            })

            pending_tools = []
            response_text = ""

            for block in response.content:
                if block.type == "text":
                    response_text += block.text
                elif block.type == "tool_use":
                    tool_info = {
                        "id": block.id,
                        "name": block.name,
                        "arguments": block.input
                    }
                    pending_tools.append(tool_info)
                    self._pending_tool_calls.append(tool_info)

            tools_names = [t["name"] for t in pending_tools]
            log(f"🔧 Anthropic pending tools: {', '.join(tools_names)}")

            return {
                "pending_tool_calls": pending_tools,
                "response_text": response_text
            }
        else:
            # No custom tools needed - extract text from all content blocks
            # (response may include web search results interspersed with text)
            final_response = ""
            for block in response.content:
                if hasattr(block, 'text') and block.text:
                    final_response += block.text
            self.history.append({
                "role": "assistant",
                "content": final_response
            })
            log(f"✅ Anthropic response (no custom tools) - {len(final_response)} chars")
            return final_response

    def execute_approved_tools(self, approved_tool_calls: List[Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
        """
        Execute approved tool calls and get the response.

        In manual mode, if the model wants more tools after execution,
        returns them for user approval instead of auto-executing.

        Args:
            approved_tool_calls: List of approved tools to execute
                                [{"id": "...", "name": "...", "arguments": {...}}, ...]

        Returns:
            str: Final response text if no more tools needed
            dict: {"pending_tool_calls": [...], "response_text": "..."} if more tools needed
        """
        try:
            if not self._pending_messages:
                return "Error: No pending tool calls to execute"

            messages = copy.deepcopy(self._pending_messages)

            # Execute approved tools and add results
            for tool_call in approved_tool_calls:
                tool_id = tool_call.get("id", "")
                tool_name = tool_call["name"]
                tool_args = tool_call.get("arguments", {})

                result = self._execute_tool(tool_name, tool_args)

                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        }
                    ]
                })

            # Check if auto mode or manual mode
            if self.auto_function_calling:
                # Auto mode: loop until final response
                final_response = self._auto_execute_tools(messages)
                self._pending_messages = []
                self._pending_tool_calls = []
                return final_response
            else:
                # Manual mode: make ONE call and check if more tools are needed
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=4096,
                    system=self._get_cached_system_prompt(),  # Layer 1: Cached system prompt
                    messages=messages,
                    tools=self.tools
                )

                if response.stop_reason == "tool_use":
                    # Model wants more tools - return them for approval
                    self._pending_messages = messages
                    self._pending_messages.append({
                        "role": "assistant",
                        "content": response.content
                    })
                    self._pending_tool_calls = []

                    pending_tools = []
                    response_text = ""

                    for block in response.content:
                        if block.type == "text":
                            response_text += block.text
                        elif block.type == "tool_use":
                            tool_info = {
                                "id": block.id,
                                "name": block.name,
                                "arguments": block.input
                            }
                            pending_tools.append(tool_info)
                            self._pending_tool_calls.append(tool_info)

                    tools_names = [t["name"] for t in pending_tools]
                    log(f"🔧 Anthropic wants more tools (manual mode): {', '.join(tools_names)}")

                    return {
                        "pending_tool_calls": pending_tools,
                        "response_text": response_text
                    }
                else:
                    # Final response - no more tools
                    final_response = ""
                    for block in response.content:
                        if hasattr(block, 'text') and block.text:
                            final_response += block.text

                    self.history.append({
                        "role": "assistant",
                        "content": final_response
                    })

                    # Clear pending state
                    self._pending_messages = []
                    self._pending_tool_calls = []

                    log(f"✅ Anthropic execute_approved_tools final response - {len(final_response)} chars")
                    return final_response

        except Exception as e:
            log(f"Error executing approved tools: {e}")
            return f"Error executing tools: {e}"

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
            log(f"🤖 Anthropic AI Cell completion starting...")
            log(f"   Context: {len(notebook_context)} chars (Layer 2 - cached)")
            log(f"   User prompt: {len(user_prompt)} chars (Layer 3 - not cached)")
            if images:
                log(f"📷 Including {len(images)} image(s)")

            # Anthropic has web search via tool - use it if needed based on user prompt
            tools = []
            if self._needs_web_search(user_prompt, user_prompt):
                tools.append({
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 3
                })
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

            # Extract text from response (may have multiple content blocks)
            result = ""
            for block in response.content:
                if hasattr(block, 'text') and block.text:
                    result += block.text

            log(f"🤖 Anthropic AI Cell response: {len(result)} chars")
            return result

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
        """Get Anthropic web search tool definition."""
        if not self.enable_web_search:
            return None
        return {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 3
        }

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
                system=self._get_cached_ai_cell_system_prompt(),  # Layer 1: Cached AI Cell system prompt
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
                system=self._get_cached_ai_cell_system_prompt(),  # Layer 1: Cached AI Cell system prompt
                messages=messages,
                tools=tools,
            )

        # Log cache usage
        self._log_cache_usage(response)

        # Extract text, thinking, and tool calls from response
        text = ""
        thinking = ""
        tool_calls = []
        raw_thinking_blocks = []  # Store raw blocks with signature for conversation history

        for block in response.content:
            if block.type == "thinking":
                # Extended thinking block - store both text and raw block
                thinking += block.thinking if hasattr(block, 'thinking') else ""
                # Store the raw block which includes signature field
                raw_thinking_blocks.append(block)
                log(f"💭 Anthropic thinking block: {len(thinking)} chars")
            elif hasattr(block, 'text') and block.text:
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input or {}
                ))

        # is_final when stop_reason is "end_turn" (not "tool_use")
        is_final = response.stop_reason == "end_turn"

        if thinking:
            log(f"💭 Anthropic total thinking: {len(thinking)} chars, raw blocks: {len(raw_thinking_blocks)}")

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            is_final=is_final,
            thinking=thinking,
            raw_thinking_blocks=raw_thinking_blocks
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
        """
        # Build assistant message content
        # Include raw thinking blocks FIRST (required by Anthropic when thinking is enabled)
        assistant_content = []

        # Add raw thinking blocks first (includes signature field)
        for block in response.raw_thinking_blocks:
            assistant_content.append(block)

        # Then add tool_use blocks
        for tc in response.tool_calls:
            assistant_content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments
            })

        # Add assistant message with tool calls
        messages.append({"role": "assistant", "content": assistant_content})

        # Build tool_result content blocks
        result_blocks = []
        for tr in tool_results:
            result_blocks.append({
                "type": "tool_result",
                "tool_use_id": tr.tool_call_id,
                "content": tr.result,
                "is_error": tr.is_error
            })

        # Add as user message with tool results
        messages.append({"role": "user", "content": result_blocks})

        return messages

    # =========================================================================
    # SECTION 7: UTILITIES & HELPERS
    # =========================================================================

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool and return the result as a string."""
        log(f"Anthropic executing tool: {tool_name} with args: {arguments}")

        if tool_name not in TOOL_MAP:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            result = TOOL_MAP[tool_name](**arguments)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _build_content_with_images(self, text: str, images: Optional[List[ImageData]] = None) -> Union[str, List[Dict[str, Any]]]:
        """
        Build message content with optional images for Anthropic API.

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
        for idx, img in enumerate(images):
            log(f"📷 Processing image {idx + 1}: keys={list(img.keys())}, mime_type={img.get('mime_type', 'N/A')}")
            prepared = prepare_image(img)
            log(f"📷 Prepared image {idx + 1}: keys={list(prepared.keys())}, mime_type={prepared.get('mime_type', 'N/A')}, data_len={len(prepared.get('data', ''))}")
            if "url" in prepared:
                # Anthropic supports URL-based images
                content.append({
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": prepared["url"]
                    }
                })
            else:
                # Base64 encoded image
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": prepared["mime_type"],
                        "data": prepared["data"]
                    }
                })

        log(f"📷 Built content with {len(content)} image blocks + text")

        # Add text last
        content.append({
            "type": "text",
            "text": text
        })

        return content

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
        - Layer 1: System prompt (cached via _get_cached_system_prompt() - not handled here)
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

    def _anthropic_build_cached_content(self, message: str, images: Optional[List[ImageData]] = None) -> List[Dict[str, Any]]:
        """
        Build message content with Layer 2 caching (notebook context).

        Two-Layer Caching Strategy:
        - Layer 1: System prompt (cached separately via _get_cached_system_prompt())
        - Layer 2: Notebook context (cached here - semi-static, changes when cells are edited)
        - Layer 3: User question (never cached - always dynamic)

        This method handles Layer 2: separates notebook context from user question
        and applies cache_control to the context. Combined with Layer 1, this means:
        - First request: System prompt + context are written to cache
        - Subsequent requests (within 5 min, same context): ~90% token cost savings
        - When notebook changes: Only context cache is invalidated, system prompt stays cached

        Uses cache_control: {"type": "ephemeral"} for 5-minute caching.

        Args:
            message: The full message (may include context + user question)
            images: Optional list of images

        Returns:
            List of content blocks with cache_control on notebook context (Layer 2)
        """
        content = []

        # Add images first (if any) - these are typically dynamic, so no caching
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

        # Check if message contains notebook context (look for XML tags or context markers)
        # Context typically starts with <notebook_context> or similar structure
        has_context = "<notebook_context>" in message or "<cells>" in message or "=== NOTEBOOK CONTEXT ===" in message

        if has_context and len(message) >= 1024:  # Min 1024 tokens for caching
            # Split context from user question
            # Look for common separators
            separators = [
                "\n\nUser question:",
                "\n\nQuestion:",
                "\n\n---\n\n",
                "</notebook_context>\n\n",
                "=== USER QUESTION ===",
            ]

            context_part = message
            user_part = ""

            for sep in separators:
                if sep in message:
                    parts = message.split(sep, 1)
                    if len(parts) == 2:
                        context_part = parts[0] + (sep if sep.startswith("</") else "")
                        user_part = parts[1] if not sep.startswith("</") else sep.lstrip("</").split(">")[0] + ">\n\n" + parts[1]
                        break

            if user_part:
                # Add context with cache_control
                content.append({
                    "type": "text",
                    "text": context_part,
                    "cache_control": {"type": "ephemeral"}  # 5-minute cache
                })
                # Add user question without caching (dynamic)
                content.append({
                    "type": "text",
                    "text": user_part
                })
                log(f"💾 Layer 2 cache: notebook context={len(context_part)} chars, user question={len(user_part)} chars (uncached)")
            else:
                # Couldn't split, cache the whole message if it's large enough
                content.append({
                    "type": "text",
                    "text": message,
                    "cache_control": {"type": "ephemeral"}
                })
                log(f"💾 Layer 2 cache: whole message={len(message)} chars (couldn't split context/question)")
        else:
            # No context or too small - just add as text
            content.append({
                "type": "text",
                "text": message
            })

        return content

    def _log_cache_usage(self, response) -> None:
        """Log cache usage statistics from Anthropic response."""
        if hasattr(response, 'usage'):
            usage = response.usage
            cache_creation = getattr(usage, 'cache_creation_input_tokens', 0)
            cache_read = getattr(usage, 'cache_read_input_tokens', 0)
            input_tokens = getattr(usage, 'input_tokens', 0)
            output_tokens = getattr(usage, 'output_tokens', 0)

            if cache_creation > 0 or cache_read > 0:
                log(f"💾 Cache: write={cache_creation}, read={cache_read}, input={input_tokens}, output={output_tokens}")
                if cache_read > 0:
                    # Calculate savings (cache read = 10% of normal cost)
                    savings_pct = (cache_read * 0.9) / max(input_tokens, 1) * 100
                    log(f"💰 Cache savings: ~{savings_pct:.1f}% on input tokens")
