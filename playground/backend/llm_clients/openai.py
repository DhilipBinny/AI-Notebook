"""
OpenAI LLM Client - OpenAI API implementation

Implements the BaseLLMClient interface for OpenAI models (GPT-4, etc.).
Supports both automatic and manual (approval-based) function calling.
Includes web search tool for real-time web information.
"""

import json
import copy
from typing import List, Dict, Any, Optional, Union
from openai import OpenAI

from backend.llm_clients.base import BaseLLMClient, ImageData, prepare_image
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

    def ai_cell_with_tools(self, prompt: str, images: Optional[List[ImageData]] = None, max_iterations: int = 10) -> Dict[str, Any]:
        """
        AI Cell completion with tool calling support.
        Uses automatic function calling for kernel inspection and sandbox tools.
        Supports image inputs for visual analysis.

        Args:
            prompt: The full prompt including notebook context and user question
            images: Optional list of images to analyze
            max_iterations: Maximum number of tool-calling iterations

        Returns:
            Dict with "response" (str) and "steps" (list of tool call info)
        """
        steps = []
        try:
            log_debug_message(f"🤖 OpenAI AI Cell with tools starting...")
            if images:
                log_debug_message(f"📷 Including {len(images)} image(s)")

            # Build AI Cell tool schemas
            ai_cell_tools = self._build_ai_cell_tools()
            ai_cell_tool_map = {func.__name__: func for func in AI_CELL_TOOLS}

            # Build content with optional images
            content = self._build_content_with_images(prompt, images)
            messages = [{"role": "user", "content": content}]

            for iteration in range(max_iterations):
                log_debug_message(f"🔄 AI Cell iteration {iteration + 1}/{max_iterations}")

                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=ai_cell_tools,
                    tool_choice="auto",
                    max_tokens=4096,
                )

                message = response.choices[0].message

                # If no tool calls, return the response
                if not message.tool_calls:
                    result = message.content or ""
                    log_debug_message(f"🤖 OpenAI AI Cell response: {len(result)} chars, {len(steps)} steps")
                    return {"response": result, "steps": steps}

                # Execute tool calls
                messages.append(message.model_dump())

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = _safe_json_loads(tool_call.function.arguments)

                    log_debug_message(f"🔧 AI Cell executing: {tool_name}({tool_args})")

                    # Record tool call step
                    steps.append({
                        "type": "tool_call",
                        "name": tool_name,
                        "content": json.dumps(tool_args, indent=2)
                    })

                    if tool_name in ai_cell_tool_map:
                        try:
                            result = ai_cell_tool_map[tool_name](**tool_args)
                            tool_result = json.dumps(result)
                        except Exception as e:
                            tool_result = json.dumps({"error": str(e)})
                    else:
                        tool_result = json.dumps({"error": f"Unknown tool: {tool_name}"})

                    # Record tool result step
                    result_preview = tool_result[:1000] + "..." if len(tool_result) > 1000 else tool_result
                    steps.append({
                        "type": "tool_result",
                        "name": tool_name,
                        "content": result_preview
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    })

            # Max iterations reached
            return {"response": "I've analyzed your notebook but reached the maximum number of tool calls. Please ask a more specific question.", "steps": steps}

        except Exception as e:
            log_debug_message(f"OpenAI ai_cell_with_tools error: {e}")
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
