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
import copy
from typing import List, Dict, Any, Optional, Union, Callable
from openai import OpenAI

from backend.llm_clients.base import BaseLLMClient, ImageData, prepare_image, LLMResponse, ToolCall, ToolResult, MAX_TOOL_ITERATIONS
from backend.llm_clients.tool_schemas import build_openai_tools
from backend.utils.util_func import log
from backend.llm_tools import TOOL_FUNCTIONS, AI_CELL_TOOLS
import backend.config as cfg


# =============================================================================
# SECTION 1: MODULE-LEVEL SETUP
# =============================================================================
# Constants, tool definitions, and module-level helpers

# Web search tool for OpenAI
WEB_SEARCH_TOOL = {
    "type": "web_search_preview",
    "search_context_size": "medium"  # Options: "low", "medium", "high"
}


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

    def __init__(self, api_key: str, model_name: str = None, auto_function_calling: Optional[bool] = None, enable_web_search: bool = True):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model_name: Model to use (default: gpt-4o)
            auto_function_calling: Override config setting. If None, uses cfg.AUTO_FUNCTION_CALLING
            enable_web_search: Enable web search tool for real-time web info (default: True)
        """
        super().__init__()  # Initialize base class (cancellation support)

        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name or cfg.OPENAI_MODEL
        self.enable_web_search = enable_web_search

        # Build base tools list (without web search - added dynamically per request)
        self.tools = build_openai_tools(TOOL_FUNCTIONS)

        log(f"OpenAI web search: {'enabled' if enable_web_search else 'disabled'} (added dynamically when needed)")

        self.history: List[Dict[str, Any]] = []

        # Use config value if not explicitly set
        self.auto_function_calling = auto_function_calling if auto_function_calling is not None else cfg.AUTO_FUNCTION_CALLING
        log(f"OpenAI client initialized")
        log(f"Config: tool_mode={cfg.TOOL_EXECUTION_MODE}, auto_func={self.auto_function_calling} (request may override)")
        log(f"Web search enabled: {self.enable_web_search}")

        # Store pending state for manual mode
        self._pending_messages: List[Dict[str, Any]] = []
        self._pending_tool_calls: List[Dict[str, Any]] = []

        # Cache AI Cell tools (built once)
        self._ai_cell_tools_cache: Optional[List[Dict[str, Any]]] = None
        self._ai_cell_tool_map_cache: Optional[Dict[str, Callable]] = None

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
        Send a message to OpenAI.

        Args:
            notebook_context: Formatted notebook context
            user_prompt: User's question/prompt
            images: Optional list of images for visual analysis

        Returns:
            str: Final response text (if auto mode or no tools needed)
            dict: {"pending_tool_calls": [...], "response_text": "..."} (if manual mode with tools)
        """
        try:
            log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            log(f"📨 OpenAI chat_panel_send()")
            log(f"   Context: {len(notebook_context)} chars")
            log(f"   User prompt: {len(user_prompt)} chars")
            if images:
                log(f"   Images: {len(images)} attached")
            log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Combine context and user_prompt for OpenAI
            if notebook_context:
                message = f"{notebook_context}\n\n{user_prompt}"
            else:
                message = user_prompt

            # Build content with optional images
            content = self._build_content_with_images(message, images)

            # Add user message to history
            self.history.append({
                "role": "user",
                "content": content
            })

            # Build messages with system prompt
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT}
            ] + self.history

            # Get tools for this request (conditionally includes web search)
            request_tools = self._get_tools_for_request(message, user_prompt)

            if self.auto_function_calling:
                # Auto mode: loop until final response
                log(f"🤖 OpenAI AUTO mode - executing tools automatically")
                return self._auto_execute_tools(messages, request_tools)
            else:
                # Manual mode: return pending tools for approval
                log(f"🤖 OpenAI MANUAL mode - returning tools for approval")
                return self._get_pending_tools(messages, request_tools)

        except Exception as e:
            log(f"❌ OpenAI error: {e}")
            return f"OpenAI Error: {e}"

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
            log(f"🔄 OpenAI iteration {iteration}/{MAX_TOOL_ITERATIONS}")

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=request_tools,
                tool_choice="auto"
            )

            # Log cache usage
            self._log_cache_usage(response)

            response_message = response.choices[0].message

            if response_message.tool_calls:
                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": response_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in response_message.tool_calls
                    ]
                })

                # Execute each tool call
                for tool_call in response_message.tool_calls:
                    func_name = tool_call.function.name
                    func_args = _safe_json_loads(tool_call.function.arguments)
                    log(f"🔧 OpenAI calling tool: {func_name}")
                    result = self._execute_tool(func_name, func_args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
            else:
                # Final response
                final_response = response_message.content or ""
                self.history.append({
                    "role": "assistant",
                    "content": final_response
                })
                log(f"✅ OpenAI response received - {len(final_response)} chars")
                return final_response

        log(f"❌ OpenAI max iterations reached")
        return "Error: Maximum tool calling iterations reached"

    def _get_pending_tools(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Union[str, Dict[str, Any]]:
        """
        Get pending tool calls without executing them.

        Args:
            messages: Conversation messages
            tools: Tools to use for this request (defaults to self.tools if not provided)
        """
        request_tools = tools if tools is not None else self.tools
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=request_tools,
            tool_choice="auto"
        )

        # Log cache usage
        self._log_cache_usage(response)

        response_message = response.choices[0].message

        if response_message.tool_calls:
            # Store state for later execution
            self._pending_messages = copy.deepcopy(messages)
            self._pending_tool_calls = []

            pending_tools = []
            for tc in response_message.tool_calls:
                tool_info = {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": _safe_json_loads(tc.function.arguments)
                }
                pending_tools.append(tool_info)
                self._pending_tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments  # Keep as string for OpenAI
                })

            # Store assistant message for later
            self._pending_messages.append({
                "role": "assistant",
                "content": response_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in response_message.tool_calls
                ]
            })

            tools_names = [t["name"] for t in pending_tools]
            log(f"🔧 OpenAI pending tools: {', '.join(tools_names)}")

            return {
                "pending_tool_calls": pending_tools,
                "response_text": response_message.content or ""
            }
        else:
            # No tools needed
            final_response = response_message.content or ""
            self.history.append({
                "role": "assistant",
                "content": final_response
            })
            log(f"✅ OpenAI response (no tools) - {len(final_response)} chars")
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
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": result
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
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "system", "content": self.SYSTEM_PROMPT}] + messages,
                    tools=self.tools
                )

                choice = response.choices[0]

                if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                    # Model wants more tools - return them for approval
                    # First, add the assistant's tool call message to pending
                    self._pending_messages = messages
                    self._pending_messages.append({
                        "role": "assistant",
                        "content": choice.message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            } for tc in choice.message.tool_calls
                        ]
                    })
                    self._pending_tool_calls = []

                    pending_tools = []
                    for tc in choice.message.tool_calls:
                        tool_info = {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": _safe_json_loads(tc.function.arguments)
                        }
                        pending_tools.append(tool_info)
                        self._pending_tool_calls.append(tool_info)

                    tools_names = [t["name"] for t in pending_tools]
                    log(f"🔧 OpenAI wants more tools (manual mode): {', '.join(tools_names)}")

                    return {
                        "pending_tool_calls": pending_tools,
                        "response_text": choice.message.content or ""
                    }
                else:
                    # Final response - no more tools
                    final_response = choice.message.content or ""

                    self.history.append({
                        "role": "assistant",
                        "content": final_response
                    })

                    # Clear pending state
                    self._pending_messages = []
                    self._pending_tool_calls = []

                    log(f"✅ OpenAI execute_approved_tools final response - {len(final_response)} chars")
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
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            log(f"OpenAI simple_completion error: {e}")
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

        Args:
            notebook_context: Formatted notebook context
            user_prompt: User's question/prompt
            images: Optional list of images to analyze

        Returns:
            The response text from the LLM
        """
        try:
            log(f"🤖 OpenAI AI Cell completion starting...")
            log(f"   Context: {len(notebook_context)} chars")
            log(f"   User prompt: {len(user_prompt)} chars")
            if images:
                log(f"📷 Including {len(images)} image(s)")

            # Combine context and user prompt
            full_prompt = f"{notebook_context}\n\n{user_prompt}" if notebook_context else user_prompt

            # Build content with optional images
            content = self._build_content_with_images(full_prompt, images)

            # OpenAI doesn't have native web search, so just do completion
            # Could integrate with a search API in the future
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": content}],
                max_tokens=4096,
            )

            # Log cache usage
            self._log_cache_usage(response)

            result = response.choices[0].message.content or ""
            log(f"🤖 OpenAI AI Cell response: {len(result)} chars")
            return result

        except Exception as e:
            log(f"OpenAI ai_cell_simple error: {e}")
            raise

    # =========================================================================
    # SECTION 6: AI CELL - Tool Execution Framework
    # =========================================================================
    # These methods implement the unified tool execution interface for AI Cells
    # Used for notebook inspection and code execution tools

    def _get_ai_cell_tools(self) -> List[Dict[str, Any]]:
        """
        Get AI Cell tools in OpenAI format.
        Uses cached tools to avoid rebuilding on each call.
        """
        if self._ai_cell_tools_cache is None:
            self._ai_cell_tools_cache = build_openai_tools(AI_CELL_TOOLS)
        return self._ai_cell_tools_cache

    def _get_ai_cell_tool_map(self) -> Dict[str, Callable]:
        """Get mapping of tool names to callable functions for AI Cell."""
        if self._ai_cell_tool_map_cache is None:
            self._ai_cell_tool_map_cache = {func.__name__: func for func in AI_CELL_TOOLS}
        return self._ai_cell_tool_map_cache

    def _get_web_search_tool(self) -> Optional[Dict[str, Any]]:
        """Get OpenAI web search tool (Bing Search Preview)."""
        if not self.enable_web_search:
            return None
        return WEB_SEARCH_TOOL

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
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=4096,
        )

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

        return LLMResponse(
            text=text,
            tool_calls=tool_calls_list,
            is_final=is_final
        )

    def _add_tool_results_to_messages(self, messages: List[Dict[str, Any]], response: 'LLMResponse', tool_results: List[ToolResult]) -> List[Dict[str, Any]]:
        """
        Add tool results to messages for the next OpenAI API call.

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
            "content": None,
            "tool_calls": assistant_tool_calls
        })

        # Add tool result messages
        for tr in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": tr.tool_call_id,
                "content": tr.result
            })

        return messages

    # =========================================================================
    # SECTION 7: UTILITIES & HELPERS
    # =========================================================================

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool and return the result as a string."""
        log(f"OpenAI executing tool: {tool_name} with args: {arguments}")

        if tool_name not in TOOL_MAP:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            result = TOOL_MAP[tool_name](**arguments)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

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

    def _log_cache_usage(self, response) -> None:
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
                # Calculate savings (cached = 50% of normal for GPT-4o, 75% for GPT-4.1)
                discount = 0.75 if "4.1" in self.model_name else 0.5
                savings_pct = (cached_tokens * discount) / max(input_tokens, 1) * 100
                log(f"💾 OpenAI Cache: cached={cached_tokens}, input={input_tokens}, output={output_tokens}")
                log(f"💰 Cache savings: ~{savings_pct:.1f}% on input tokens ({int(discount*100)}% discount)")
            else:
                log(f"📊 OpenAI Usage: input={input_tokens}, output={output_tokens} (no cache hit)")
