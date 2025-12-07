"""
Anthropic LLM Client - Claude implementation

Implements the BaseLLMClient interface for Anthropic models (Claude 3, etc.).
Supports both automatic and manual (approval-based) function calling.
Includes web search tool for real-time web information.
"""

import json
import copy
from typing import List, Dict, Any, Optional, Union, Callable
import anthropic
from anthropic import Anthropic

from backend.llm_clients.base import BaseLLMClient, ImageData, prepare_image, LLMResponse, ToolCall, ToolResult
from backend.utils.util_func import log_debug_message
from backend.llm_tools import TOOL_FUNCTIONS, AI_CELL_TOOLS
import backend.config as cfg


# Web search tool definition for Anthropic
WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5  # Limit searches per request
}


# Build Anthropic tool schemas from our function definitions
def _build_anthropic_tools() -> List[Dict[str, Any]]:
    """Convert our tool functions to Anthropic tool format"""
    tools = []

    for func in TOOL_FUNCTIONS:
        # Get function metadata from docstring and annotations
        func_name = func.__name__
        func_doc = func.__doc__ or ""
        annotations = func.__annotations__

        # Parse docstring to get description and parameter descriptions
        doc_lines = func_doc.strip().split('\n')
        description = ""
        param_descriptions = {}
        current_section = None

        for line in doc_lines:
            line = line.strip()
            if line.lower().startswith('args:'):
                current_section = 'args'
                continue
            elif line.lower().startswith('returns:'):
                current_section = 'returns'
                continue
            elif line.lower().startswith('example:'):
                current_section = 'example'
                continue

            if current_section is None and line:
                description += line + " "
            elif current_section == 'args' and ':' in line:
                param_name = line.split(':')[0].strip()
                param_desc = ':'.join(line.split(':')[1:]).strip()
                param_descriptions[param_name] = param_desc

        # Build parameters schema
        properties = {}
        required = []

        for param_name, param_type in annotations.items():
            if param_name == 'return':
                continue

            # Map Python types to JSON schema types
            json_type = "string"
            if param_type == int:
                json_type = "integer"
            elif param_type == float:
                json_type = "number"
            elif param_type == bool:
                json_type = "boolean"
            elif param_type == str:
                json_type = "string"

            properties[param_name] = {
                "type": json_type,
                "description": param_descriptions.get(param_name, f"The {param_name} parameter")
            }

            # Check if parameter has a default value
            defaults = func.__defaults__ or ()
            code = func.__code__
            num_params = code.co_argcount
            num_defaults = len(defaults)
            params_without_defaults = num_params - num_defaults

            param_names = code.co_varnames[:num_params]
            if param_name in param_names:
                param_index = list(param_names).index(param_name)
                if param_index < params_without_defaults:
                    required.append(param_name)

        tool = {
            "name": func_name,
            "description": description.strip(),
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
        tools.append(tool)

    log_debug_message(f"Anthropic tools: {tools}")

    return tools


# Map function names to actual functions
TOOL_MAP = {func.__name__: func for func in TOOL_FUNCTIONS}


class AnthropicClient(BaseLLMClient):
    """Anthropic LLM client with tool calling and web search support"""

    def __init__(self, api_key: str, model_name: str = "claude-3-haiku-20240307", auto_function_calling: Optional[bool] = None, enable_web_search: bool = True):
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
        self.model_name = model_name
        self.enable_web_search = enable_web_search

        # Build tools list - custom tools first
        self.tools = _build_anthropic_tools()

        # Add web search tool if enabled
        if self.enable_web_search:
            self.tools.append(WEB_SEARCH_TOOL)
            log_debug_message("Anthropic web search tool enabled")

        self.history: List[Dict[str, Any]] = []

        # Use config value if not explicitly set
        self.auto_function_calling = auto_function_calling if auto_function_calling is not None else cfg.AUTO_FUNCTION_CALLING
        log_debug_message(f"Anthropic client initialized. Auto function calling: {self.auto_function_calling}")
        log_debug_message(f"Web search enabled: {self.enable_web_search}")

        # Store pending state for manual mode
        self._pending_messages: List[Dict[str, Any]] = []
        self._pending_tool_calls: List[Dict[str, Any]] = []

        # Cache AI Cell tools (built once)
        self._ai_cell_tools_cache: Optional[List[Dict[str, Any]]] = None
        self._ai_cell_tool_map_cache: Optional[Dict[str, Any]] = None

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool and return the result as a string."""
        log_debug_message(f"Anthropic executing tool: {tool_name} with args: {arguments}")

        if tool_name not in TOOL_MAP:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            result = TOOL_MAP[tool_name](**arguments)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def send_message(self, message: str, user_message: str = None, images: Optional[List[ImageData]] = None) -> Union[str, Dict[str, Any]]:
        """
        Send a message to Anthropic.

        Args:
            message: The full message (may include context)
            user_message: Optional - just the user's actual question (unused, for API compatibility)
            images: Optional list of images for visual analysis

        When auto_function_calling=True:
            Executes tools automatically and returns final response text

        When auto_function_calling=False:
            If model wants to call tools: Returns dict with pending_tool_calls
            If no tools needed: Returns the response text

        Args:
            message: The user message

        Returns:
            str: Final response text (if auto mode or no tools needed)
            dict: {"pending_tool_calls": [...], "response_text": "..."} (if manual mode with tools)
        """
        try:
            log_debug_message(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            log_debug_message(f"📨 Anthropic send_message() - User: {message[:60]}...")
            if images:
                log_debug_message(f"📷 Chat panel: {len(images)} image(s) attached")
            log_debug_message(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Build content with optional images
            content = self._build_content_with_images(message, images)

            # Add user message to history
            self.history.append({
                "role": "user",
                "content": content
            })

            # Build messages (Anthropic system prompt is separate)
            messages = self.history

            if self.auto_function_calling:
                # Auto mode: loop until final response
                log_debug_message(f"🤖 Anthropic AUTO mode - executing tools automatically")
                return self._auto_execute_tools(messages)
            else:
                # Manual mode: return pending tools for approval
                log_debug_message(f"🤖 Anthropic MANUAL mode - returning tools for approval")
                return self._get_pending_tools(messages)

        except Exception as e:
            log_debug_message(f"❌ Anthropic error: {e}")
            return f"Anthropic Error: {e}"

    def _auto_execute_tools(self, messages: List[Dict[str, Any]]) -> str:
        """Execute tools automatically until we get a final response"""
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            log_debug_message(f"🔄 Anthropic iteration {iteration}/{max_iterations}")

            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=self.SYSTEM_PROMPT,
                messages=messages,
                tools=self.tools
            )

            # Log server tool usage (like web_search)
            for block in response.content:
                if block.type == "server_tool_use":
                    log_debug_message(f"🌐 Anthropic web search: {block.name}")
                elif block.type == "web_search_tool_result":
                    result_count = len(block.content) if hasattr(block, 'content') else 0
                    log_debug_message(f"🌐 Anthropic web search returned {result_count} results")

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
                        log_debug_message(f"🔧 Anthropic calling tool: {func_name}")
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
                log_debug_message(f"✅ Anthropic response received - {len(final_response)} chars")
                return final_response

        log_debug_message(f"❌ Anthropic max iterations reached")
        return "Error: Maximum tool calling iterations reached"

    def _get_pending_tools(self, messages: List[Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
        """Get pending tool calls without executing them"""
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            system=self.SYSTEM_PROMPT,
            messages=messages,
            tools=self.tools
        )

        # Log server tool usage (like web_search)
        for block in response.content:
            if block.type == "server_tool_use":
                log_debug_message(f"🌐 Anthropic web search: {block.name}")
            elif block.type == "web_search_tool_result":
                result_count = len(block.content) if hasattr(block, 'content') else 0
                log_debug_message(f"🌐 Anthropic web search returned {result_count} results")

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
            log_debug_message(f"🔧 Anthropic pending tools: {', '.join(tools_names)}")

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
            log_debug_message(f"✅ Anthropic response (no custom tools) - {len(final_response)} chars")
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
                    system=self.SYSTEM_PROMPT,
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
                    log_debug_message(f"🔧 Anthropic wants more tools (manual mode): {', '.join(tools_names)}")

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

                    log_debug_message(f"✅ Anthropic execute_approved_tools final response - {len(final_response)} chars")
                    return final_response

        except Exception as e:
            log_debug_message(f"Error executing approved tools: {e}")
            return f"Error executing tools: {e}"

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

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    def chat_completion(self, prompt: str, max_tokens: int = 1000) -> str:
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
            log_debug_message(f"Anthropic chat_completion error: {e}")
            raise

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
            log_debug_message(f"📷 Processing image {idx + 1}: keys={list(img.keys())}, mime_type={img.get('mime_type', 'N/A')}")
            prepared = prepare_image(img)
            log_debug_message(f"📷 Prepared image {idx + 1}: keys={list(prepared.keys())}, mime_type={prepared.get('mime_type', 'N/A')}, data_len={len(prepared.get('data', ''))}")
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

        log_debug_message(f"📷 Built content with {len(content)} image blocks + text")

        # Add text last
        content.append({
            "type": "text",
            "text": text
        })

        return content

    def ai_cell_completion(self, prompt: str, images: Optional[List[ImageData]] = None) -> str:
        """
        AI Cell completion - with web search but no notebook tools.
        Used for inline Q&A in AI cells. Supports image inputs.

        Args:
            prompt: The full prompt including notebook context and user question
            images: Optional list of images to analyze

        Returns:
            The response text from the LLM (may include web search results)
        """
        try:
            log_debug_message(f"🤖 Anthropic AI Cell completion starting...")
            if images:
                log_debug_message(f"📷 Including {len(images)} image(s)")

            # Anthropic has web search via tool - use it if enabled
            tools = []
            if self.enable_web_search:
                tools.append({
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 3
                })

            # Build content with optional images
            content = self._build_content_with_images(prompt, images)

            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                messages=[{"role": "user", "content": content}],
                tools=tools if tools else None,
            )

            # Extract text from response (may have multiple content blocks)
            result = ""
            for block in response.content:
                if hasattr(block, 'text') and block.text:
                    result += block.text

            log_debug_message(f"🤖 Anthropic AI Cell response: {len(result)} chars")
            return result

        except Exception as e:
            log_debug_message(f"Anthropic ai_cell_completion error: {e}")
            raise

    # =========================================================================
    # Unified tool execution - Abstract method implementations
    # =========================================================================

    def _get_ai_cell_tools(self) -> List[Dict[str, Any]]:
        """
        Get AI Cell tools in Anthropic format.
        Uses cached tools to avoid rebuilding on each call.
        """
        if self._ai_cell_tools_cache is None:
            self._ai_cell_tools_cache = self._build_ai_cell_tools_internal()
        return self._ai_cell_tools_cache

    def _get_ai_cell_tool_map(self) -> Dict[str, Callable]:
        """Get mapping of tool names to callable functions for AI Cell."""
        if self._ai_cell_tool_map_cache is None:
            self._ai_cell_tool_map_cache = {func.__name__: func for func in AI_CELL_TOOLS}
        return self._ai_cell_tool_map_cache

    def _prepare_ai_cell_messages(self, prompt: str, images: Optional[List[ImageData]] = None) -> List[Dict[str, Any]]:
        """Prepare initial messages for AI Cell in Anthropic format."""
        content = self._build_content_with_images(prompt, images)

        # Debug: log what we're sending
        if isinstance(content, list):
            log_debug_message(f"📷 Sending {len(content)} content blocks to Anthropic")
            for i, block in enumerate(content):
                block_type = block.get("type", "unknown")
                if block_type == "image":
                    source_type = block.get("source", {}).get("type", "unknown")
                    mime = block.get("source", {}).get("media_type", "N/A")
                    data_len = len(block.get("source", {}).get("data", ""))
                    log_debug_message(f"📷 Block {i}: type=image, source_type={source_type}, mime={mime}, data_len={data_len}")
                else:
                    text_preview = str(block.get("text", ""))[:50]
                    log_debug_message(f"📷 Block {i}: type={block_type}, text_preview='{text_preview}...'")
        else:
            log_debug_message(f"📷 Sending text-only content (no images)")

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
            log_debug_message(f"💭 Anthropic extended thinking enabled for {self.model_name}")
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=16000,  # Need higher limit for thinking
                system=self.AI_CELL_SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
                thinking={
                    "type": "enabled",
                    "budget_tokens": 8192  # Allow up to 8K tokens for thinking
                }
            )
        else:
            log_debug_message(f"💭 Extended thinking not supported for {self.model_name}")
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=self.AI_CELL_SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
            )

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
                log_debug_message(f"💭 Anthropic thinking block: {len(thinking)} chars")
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
            log_debug_message(f"💭 Anthropic total thinking: {len(thinking)} chars, raw blocks: {len(raw_thinking_blocks)}")

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
        from .base import LLMResponse  # Import here to avoid circular import

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

    def _build_ai_cell_tools_internal(self) -> List[Dict[str, Any]]:
        """Build tool schemas for AI Cell tools only (Anthropic format)."""
        tools = []
        for func in AI_CELL_TOOLS:
            func_name = func.__name__
            func_doc = func.__doc__ or ""
            annotations = func.__annotations__

            # Parse docstring
            doc_lines = func_doc.strip().split('\n')
            description = ""
            param_descriptions = {}
            current_section = None

            for line in doc_lines:
                line = line.strip()
                if line.lower().startswith('args:'):
                    current_section = 'args'
                    continue
                elif line.lower().startswith('returns:'):
                    current_section = 'returns'
                    continue
                elif line.lower().startswith('example:'):
                    current_section = 'example'
                    continue

                if current_section is None and line:
                    description += line + " "
                elif current_section == 'args' and ':' in line:
                    param_name = line.split(':')[0].strip()
                    param_desc = ':'.join(line.split(':')[1:]).strip()
                    param_descriptions[param_name] = param_desc

            # Build parameters
            properties = {}
            required = []

            for param_name, param_type in annotations.items():
                if param_name == 'return':
                    continue

                json_type = "string"
                if param_type == int:
                    json_type = "integer"
                elif param_type == float:
                    json_type = "number"
                elif param_type == bool:
                    json_type = "boolean"

                properties[param_name] = {
                    "type": json_type,
                    "description": param_descriptions.get(param_name, f"The {param_name} parameter")
                }

                # Check for required params
                defaults = func.__defaults__ or ()
                code = func.__code__
                num_params = code.co_argcount
                num_defaults = len(defaults)
                params_without_defaults = num_params - num_defaults
                param_names = code.co_varnames[:num_params]

                if param_name in param_names:
                    param_index = list(param_names).index(param_name)
                    if param_index < params_without_defaults:
                        required.append(param_name)

            tools.append({
                "name": func_name,
                "description": description.strip()[:500],
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            })

        return tools
