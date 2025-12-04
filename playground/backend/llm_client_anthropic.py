"""
Anthropic LLM Client - Claude implementation

Implements the BaseLLMClient interface for Anthropic models (Claude 3, etc.).
Supports both automatic and manual (approval-based) function calling.
Includes web search tool for real-time web information.
"""

import json
import copy
from typing import List, Dict, Any, Optional, Union
import anthropic
from anthropic import Anthropic

from backend.llm_client_base import BaseLLMClient
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

    def send_message(self, message: str) -> Union[str, Dict[str, Any]]:
        """
        Send a message to Anthropic.

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
            log_debug_message(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Add user message to history
            self.history.append({
                "role": "user",
                "content": message
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

    def execute_approved_tools(self, approved_tool_calls: List[Dict[str, Any]]) -> str:
        """
        Execute approved tool calls and get the final response.

        Args:
            approved_tool_calls: List of approved tools to execute
                                [{"id": "...", "name": "...", "arguments": {...}}, ...]

        Returns:
            The final response text after tool execution
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

            # Continue with auto execution from here
            final_response = self._auto_execute_tools(messages)

            # Clear pending state
            self._pending_messages = []
            self._pending_tool_calls = []

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

    def ai_cell_completion(self, prompt: str) -> str:
        """
        AI Cell completion - with web search but no notebook tools.
        Used for inline Q&A in AI cells.

        Args:
            prompt: The full prompt including notebook context and user question

        Returns:
            The response text from the LLM (may include web search results)
        """
        try:
            log_debug_message(f"🤖 Anthropic AI Cell completion starting...")

            # Anthropic has web search via tool - use it if enabled
            tools = []
            if self.enable_web_search:
                tools.append({
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 3
                })

            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
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

    def ai_cell_with_tools(self, prompt: str, max_iterations: int = 10) -> str:
        """
        AI Cell completion with tool calling support.
        Uses automatic function calling for kernel inspection and sandbox tools.

        Args:
            prompt: The full prompt including notebook context and user question
            max_iterations: Maximum number of tool-calling iterations

        Returns:
            The final response text from the LLM
        """
        try:
            log_debug_message(f"🤖 Anthropic AI Cell with tools starting...")

            # Build AI Cell tool schemas (kernel inspection + sandbox only, no web search)
            # AI Cell focuses on notebook context - web search disabled to encourage
            # better use of kernel inspection and sandbox tools
            ai_cell_tools = self._build_ai_cell_tools()
            ai_cell_tool_map = {func.__name__: func for func in AI_CELL_TOOLS}

            messages = [{"role": "user", "content": prompt}]

            for iteration in range(max_iterations):
                log_debug_message(f"🔄 AI Cell iteration {iteration + 1}/{max_iterations}")

                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=4096,
                    messages=messages,
                    tools=ai_cell_tools,
                )

                # Check stop reason
                if response.stop_reason == "end_turn":
                    # No more tool calls, extract final text
                    result = ""
                    for block in response.content:
                        if hasattr(block, 'text') and block.text:
                            result += block.text
                    log_debug_message(f"🤖 Anthropic AI Cell response: {len(result)} chars")
                    return result

                # Process tool calls
                tool_calls = []
                text_response = ""

                for block in response.content:
                    if hasattr(block, 'text') and block.text:
                        text_response += block.text
                    elif block.type == "tool_use":
                        tool_calls.append(block)

                if not tool_calls:
                    return text_response

                # Add assistant's response to messages
                messages.append({"role": "assistant", "content": response.content})

                # Execute tools and add results
                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call.name
                    tool_args = tool_call.input or {}

                    log_debug_message(f"🔧 AI Cell executing: {tool_name}({tool_args})")

                    if tool_name in ai_cell_tool_map:
                        try:
                            result = ai_cell_tool_map[tool_name](**tool_args)
                            tool_result = json.dumps(result)
                        except Exception as e:
                            tool_result = json.dumps({"error": str(e)})
                    else:
                        tool_result = json.dumps({"error": f"Unknown tool: {tool_name}"})

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": tool_result
                    })

                messages.append({"role": "user", "content": tool_results})

            # Max iterations reached
            return "I've analyzed your notebook but reached the maximum number of tool calls. Please ask a more specific question."

        except Exception as e:
            log_debug_message(f"Anthropic ai_cell_with_tools error: {e}")
            import traceback
            log_debug_message(f"Traceback: {traceback.format_exc()}")
            raise

    def _build_ai_cell_tools(self) -> List[Dict[str, Any]]:
        """Build tool schemas for AI Cell tools only"""
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
