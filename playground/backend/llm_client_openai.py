"""
OpenAI LLM Client - OpenAI API implementation

Implements the BaseLLMClient interface for OpenAI models (GPT-4, etc.).
Supports both automatic and manual (approval-based) function calling.
Includes web search tool for real-time web information.
"""

import json
from typing import List, Dict, Any, Optional, Union
from openai import OpenAI

from backend.llm_client_base import BaseLLMClient
from backend.utils.util_func import log_debug_message
from backend.llm_tools import TOOL_FUNCTIONS
import backend.config as cfg


# Web search tool for OpenAI
WEB_SEARCH_TOOL = {
    "type": "web_search_preview",
    "search_context_size": "medium"  # Options: "low", "medium", "high"
}


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

    def send_message(self, message: str) -> Union[str, Dict[str, Any]]:
        """
        Send a message to OpenAI.

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
            # Add user message to history
            self.history.append({
                "role": "user",
                "content": message
            })

            # Build messages with system prompt
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT}
            ] + self.history

            if self.auto_function_calling:
                # Auto mode: loop until final response
                return self._auto_execute_tools(messages)
            else:
                # Manual mode: return pending tools for approval
                return self._get_pending_tools(messages)

        except Exception as e:
            return f"OpenAI Error: {e}"

    def _auto_execute_tools(self, messages: List[Dict[str, Any]]) -> str:
        """Execute tools automatically until we get a final response"""
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=self.tools,
                tool_choice="auto"
            )

            response_message = response.choices[0].message
            log_debug_message(f"OpenAI response (iter {iteration}): {response_message}")

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
                    func_args = json.loads(tool_call.function.arguments)
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
                return final_response

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
        log_debug_message(f"OpenAI response (manual mode): {response_message}")

        if response_message.tool_calls:
            # Store state for later execution
            self._pending_messages = messages.copy()
            self._pending_tool_calls = []

            pending_tools = []
            for tc in response_message.tool_calls:
                tool_info = {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments)
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

            messages = self._pending_messages.copy()

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
