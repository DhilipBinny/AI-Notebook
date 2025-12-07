"""
OpenAI LLM Client - OpenAI API implementation

Implements the BaseLLMClient interface for OpenAI models (GPT-4, etc.).
Supports both automatic and manual (approval-based) function calling.
Includes web search tool for real-time web information.
"""

import json
import copy
from typing import List, Dict, Any, Optional, Union, Callable
from openai import OpenAI

from backend.llm_clients.base import BaseLLMClient, ImageData, prepare_image, LLMResponse, ToolCall, ToolResult
from backend.utils.util_func import log_debug_message
from backend.llm_tools import TOOL_FUNCTIONS, AI_CELL_TOOLS
import backend.config as cfg


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
        log_debug_message(f"⚠️ JSON parse error: {e} - Input: {json_str[:100]}...")
        return default


# Build OpenAI tool schemas from our function definitions
def _build_openai_tools() -> List[Dict[str, Any]]:
    """Convert our tool functions to OpenAI tool format"""
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
            "type": "function",
            "function": {
                "name": func_name,
                "description": description.strip(),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
        tools.append(tool)

    log_debug_message(f"OpenAI tools: {tools}")

    return tools


# Map function names to actual functions
TOOL_MAP = {func.__name__: func for func in TOOL_FUNCTIONS}


class OpenAIClient(BaseLLMClient):
    """OpenAI LLM client with tool calling and web search support"""

    def __init__(self, api_key: str, model_name: str = "gpt-4o", auto_function_calling: Optional[bool] = None, enable_web_search: bool = True):
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
        self.model_name = model_name
        self.enable_web_search = enable_web_search

        # Build tools list
        self.tools = _build_openai_tools()

        # Add web search tool if enabled
        if self.enable_web_search:
            self.tools.append(WEB_SEARCH_TOOL)
            log_debug_message("OpenAI web search tool enabled")

        self.history: List[Dict[str, Any]] = []

        # Use config value if not explicitly set
        self.auto_function_calling = auto_function_calling if auto_function_calling is not None else cfg.AUTO_FUNCTION_CALLING
        log_debug_message(f"OpenAI client initialized. Auto function calling: {self.auto_function_calling}")
        log_debug_message(f"Web search enabled: {self.enable_web_search}")

        # Store pending state for manual mode
        self._pending_messages: List[Dict[str, Any]] = []
        self._pending_tool_calls: List[Dict[str, Any]] = []

        # Cache AI Cell tools (built once)
        self._ai_cell_tools_cache: Optional[List[Dict[str, Any]]] = None
        self._ai_cell_tool_map_cache: Optional[Dict[str, Callable]] = None

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool and return the result as a string."""
        log_debug_message(f"OpenAI executing tool: {tool_name} with args: {arguments}")

        if tool_name not in TOOL_MAP:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            result = TOOL_MAP[tool_name](**arguments)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def send_message(self, message: str, user_message: str = None, images: Optional[List[ImageData]] = None) -> Union[str, Dict[str, Any]]:
        """
        Send a message to OpenAI.

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
            log_debug_message(f"📨 OpenAI send_message() - User: {message[:60]}...")
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

            # Build messages with system prompt
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT}
            ] + self.history

            if self.auto_function_calling:
                # Auto mode: loop until final response
                log_debug_message(f"🤖 OpenAI AUTO mode - executing tools automatically")
                return self._auto_execute_tools(messages)
            else:
                # Manual mode: return pending tools for approval
                log_debug_message(f"🤖 OpenAI MANUAL mode - returning tools for approval")
                return self._get_pending_tools(messages)

        except Exception as e:
            log_debug_message(f"❌ OpenAI error: {e}")
            return f"OpenAI Error: {e}"

    def _auto_execute_tools(self, messages: List[Dict[str, Any]]) -> str:
        """Execute tools automatically until we get a final response"""
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            log_debug_message(f"🔄 OpenAI iteration {iteration}/{max_iterations}")

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=self.tools,
                tool_choice="auto"
            )

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
                    log_debug_message(f"🔧 OpenAI calling tool: {func_name}")
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
                log_debug_message(f"✅ OpenAI response received - {len(final_response)} chars")
                return final_response

        log_debug_message(f"❌ OpenAI max iterations reached")
        return "Error: Maximum tool calling iterations reached"

    def _get_pending_tools(self, messages: List[Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
        """Get pending tool calls without executing them"""
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=self.tools,
            tool_choice="auto"
        )

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
            log_debug_message(f"🔧 OpenAI pending tools: {', '.join(tools_names)}")

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
            log_debug_message(f"✅ OpenAI response (no tools) - {len(final_response)} chars")
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
                    log_debug_message(f"🔧 OpenAI wants more tools (manual mode): {', '.join(tools_names)}")

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

                    log_debug_message(f"✅ OpenAI execute_approved_tools final response - {len(final_response)} chars")
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
        return "OpenAI"

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
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            log_debug_message(f"OpenAI chat_completion error: {e}")
            raise

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

    def ai_cell_completion(self, prompt: str, images: Optional[List[ImageData]] = None) -> str:
        """
        AI Cell completion - with web search but no notebook tools.
        Used for inline Q&A in AI cells. Supports image inputs.

        Args:
            prompt: The full prompt including notebook context and user question
            images: Optional list of images to analyze

        Returns:
            The response text from the LLM
        """
        try:
            log_debug_message(f"🤖 OpenAI AI Cell completion starting...")
            if images:
                log_debug_message(f"📷 Including {len(images)} image(s)")

            # Build content with optional images
            content = self._build_content_with_images(prompt, images)

            # OpenAI doesn't have native web search, so just do completion
            # Could integrate with a search API in the future
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": content}],
                max_tokens=4096,
            )

            result = response.choices[0].message.content or ""
            log_debug_message(f"🤖 OpenAI AI Cell response: {len(result)} chars")
            return result

        except Exception as e:
            log_debug_message(f"OpenAI ai_cell_completion error: {e}")
            raise

    # =========================================================================
    # Unified tool execution - Abstract method implementations
    # =========================================================================

    def _get_ai_cell_tools(self) -> List[Dict[str, Any]]:
        """
        Get AI Cell tools in OpenAI format.
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
        """Prepare initial messages for AI Cell in OpenAI format."""
        content = self._build_content_with_images(prompt, images)

        # Debug logging
        if images:
            log_debug_message(f"📷 Sending {len(images)} image(s) to OpenAI")
        else:
            log_debug_message(f"📷 Sending text-only content to OpenAI")

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

        message = response.choices[0].message

        # Extract text and tool calls
        text = message.content or ""
        tool_calls = []

        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=_safe_json_loads(tc.function.arguments)
                ))

        # is_final when there are no tool calls
        is_final = len(tool_calls) == 0

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            is_final=is_final
        )

    def _add_tool_results_to_messages(self, messages: List[Dict[str, Any]], response: 'LLMResponse', tool_results: List[ToolResult]) -> List[Dict[str, Any]]:
        """
        Add tool results to messages for the next OpenAI API call.

        OpenAI requires:
        1. Assistant message with tool_calls
        2. Tool messages with results (one per tool call)
        """
        from .base import LLMResponse  # Import here to avoid circular import

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

    def _build_ai_cell_tools_internal(self) -> List[Dict[str, Any]]:
        """Build tool schemas for AI Cell tools only (OpenAI format)."""
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
                "type": "function",
                "function": {
                    "name": func_name,
                    "description": description.strip()[:500],
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            })

        return tools
