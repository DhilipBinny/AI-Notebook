"""
Ollama LLM Client - Ollama API implementation (OpenAI-compatible)

Extends the OpenAI client since Ollama provides an OpenAI-compatible API.
No API key required - just needs the Ollama server URL.

Note: Tool/function calling support depends on the Ollama model.
Models like llama3.1, mistral, and qwen2.5 support tools.
"""

import json
import copy
from typing import List, Dict, Any, Optional, Union
from openai import OpenAI

from backend.llm_clients.openai import OpenAIClient, _build_openai_tools, TOOL_MAP, _safe_json_loads
from backend.llm_clients.base import BaseLLMClient, ImageData, prepare_image
from backend.utils.util_func import log_debug_message
from backend.llm_tools import AI_CELL_TOOLS
import backend.config as cfg


class OllamaClient(BaseLLMClient):
    """Ollama LLM client - uses OpenAI-compatible API with tool support"""

    def __init__(self, base_url: str, model_name: str = "qwen2.5-coder:7b", auto_function_calling: Optional[bool] = None):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama server URL (e.g., "http://192.168.0.136:11434/v1")
            model_name: Model to use (default: qwen2.5-coder:7b)
            auto_function_calling: Override config setting. If None, uses cfg.AUTO_FUNCTION_CALLING
        """
        # Initialize OpenAI client with Ollama endpoint
        self.client = OpenAI(
            base_url=base_url,
            api_key="ollama"  # Dummy key - Ollama doesn't validate it
        )
        self.model_name = model_name
        self.base_url = base_url
        self.tools = _build_openai_tools()
        self.history: List[Dict[str, Any]] = []

        # Use config value if not explicitly set
        self.auto_function_calling = auto_function_calling if auto_function_calling is not None else cfg.AUTO_FUNCTION_CALLING

        # Store pending state for manual mode
        self._pending_messages: List[Dict[str, Any]] = []
        self._pending_tool_calls: List[Dict[str, Any]] = []

        log_debug_message(f"Ollama client initialized: {base_url} with model {model_name}")
        log_debug_message(f"Auto function calling: {self.auto_function_calling}")
        log_debug_message(f"Tools available: {[t['function']['name'] for t in self.tools]}")

    def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool and return the result as JSON string"""
        log_debug_message(f"Ollama executing tool: {tool_name} with args: {arguments}")

        if tool_name not in TOOL_MAP:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            result = TOOL_MAP[tool_name](**arguments)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def send_message(self, message: str, user_message: str = None) -> Union[str, Dict[str, Any]]:
        """
        Send a message to Ollama.

        Args:
            message: The full message (may include context)
            user_message: Optional - just the user's actual question (unused, for API compatibility)

        When auto_function_calling=True:
            Executes tools automatically and returns final response text

        When auto_function_calling=False:
            If model wants to call tools: Returns dict with pending_tool_calls
            If no tools needed: Returns the response text
        """
        try:
            log_debug_message(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            log_debug_message(f"📨 Ollama send_message() - User: {message[:60]}...")
            log_debug_message(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

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
                log_debug_message(f"🤖 Ollama AUTO mode - executing tools automatically")
                return self._auto_execute_tools(messages)
            else:
                log_debug_message(f"🤖 Ollama MANUAL mode - returning tools for approval")
                return self._get_pending_tools(messages)

        except Exception as e:
            log_debug_message(f"❌ Ollama error: {e}")
            return f"Ollama Error: {e}"

    def _auto_execute_tools(self, messages: List[Dict[str, Any]]) -> str:
        """Execute tools automatically until we get a final response"""
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            log_debug_message(f"🔄 Ollama iteration {iteration}/{max_iterations}")

            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto"
                )
            except Exception as e:
                # If tools fail (model doesn't support), try without tools
                log_debug_message(f"⚠️ Ollama tool calling failed, trying without tools: {e}")
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages
                )

            response_message = response.choices[0].message

            if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
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
                    log_debug_message(f"🔧 Ollama calling tool: {func_name}")

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
                log_debug_message(f"✅ Ollama response received - {len(final_response)} chars")
                return final_response

        log_debug_message(f"❌ Ollama max iterations reached")
        return "Error: Maximum tool calling iterations reached"

    def _get_pending_tools(self, messages: List[Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
        """Get pending tool calls without executing them"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=self.tools,
                tool_choice="auto"
            )
        except Exception as e:
            log_debug_message(f"⚠️ Ollama tool calling failed, trying without tools: {e}")
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )

        response_message = response.choices[0].message

        if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
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
                    "arguments": tc.function.arguments
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
            log_debug_message(f"🔧 Ollama pending tools: {', '.join(tools_names)}")

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
            log_debug_message(f"✅ Ollama response (no tools) - {len(final_response)} chars")
            return final_response

    def execute_approved_tools(self, approved_tool_calls: List[Dict[str, Any]]) -> str:
        """Execute approved tool calls and get the final response."""
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
        self.history = []
        self._pending_messages = []
        self._pending_tool_calls = []

    def get_history(self):
        return self.history

    def set_history(self, history_list) -> None:
        self.history = []
        for msg in history_list:
            role = msg.get("role", "user")
            if role == "model":
                role = "assistant"
            if "parts" in msg:
                content = msg["parts"][0] if msg["parts"] else ""
            else:
                content = msg.get("content", "")
            self.history.append({"role": role, "content": content})

    @property
    def provider_name(self) -> str:
        return "Ollama"

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
            log_debug_message(f"Ollama chat_completion error: {e}")
            raise

    def _build_content_with_images(self, text: str, images: Optional[List[ImageData]] = None) -> Union[str, List[Dict[str, Any]]]:
        """
        Build message content with optional images for Ollama (OpenAI-compatible API).
        Note: Requires vision-capable model like llava, bakllava.

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
                        "url": prepared["url"]
                    }
                })
            else:
                # Base64 encoded image - Ollama uses data URL format like OpenAI
                data_url = f"data:{prepared['mime_type']};base64,{prepared['data']}"
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": data_url
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
        AI Cell completion - no web search for Ollama (local model).
        Used for inline Q&A in AI cells. Supports image inputs.

        Note: Image support requires a vision-capable model (e.g., llava, bakllava).

        Args:
            prompt: The full prompt including notebook context and user question
            images: Optional list of images to analyze

        Returns:
            The response text from the LLM
        """
        try:
            log_debug_message(f"🤖 Ollama AI Cell completion starting...")
            if images:
                log_debug_message(f"📷 Including {len(images)} image(s) - requires vision model (llava, etc.)")

            # Build content with optional images
            content = self._build_content_with_images(prompt, images)

            # Ollama is local, no web search capability
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": content}],
                max_tokens=4096,
            )

            result = response.choices[0].message.content or ""
            log_debug_message(f"🤖 Ollama AI Cell response: {len(result)} chars")
            return result

        except Exception as e:
            log_debug_message(f"Ollama ai_cell_completion error: {e}")
            raise

    def ai_cell_with_tools(self, prompt: str, images: Optional[List[ImageData]] = None, max_iterations: int = 10) -> str:
        """
        AI Cell completion with tool calling support.
        Uses automatic function calling for kernel inspection and sandbox tools.
        Supports image inputs for visual analysis.

        Note: Tool support depends on the Ollama model (llama3.1, mistral, qwen2.5 support tools).
              Image support requires a vision model (llava, bakllava).

        Args:
            prompt: The full prompt including notebook context and user question
            images: Optional list of images to analyze
            max_iterations: Maximum number of tool-calling iterations

        Returns:
            The final response text from the LLM
        """
        try:
            log_debug_message(f"🤖 Ollama AI Cell with tools starting...")
            if images:
                log_debug_message(f"📷 Including {len(images)} image(s) - requires vision model")

            # Build AI Cell tool schemas
            ai_cell_tools = self._build_ai_cell_tools()
            ai_cell_tool_map = {func.__name__: func for func in AI_CELL_TOOLS}

            # Build content with optional images
            content = self._build_content_with_images(prompt, images)
            messages = [{"role": "user", "content": content}]

            for iteration in range(max_iterations):
                log_debug_message(f"🔄 AI Cell iteration {iteration + 1}/{max_iterations}")

                try:
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        tools=ai_cell_tools,
                        max_tokens=4096,
                    )
                except Exception as e:
                    # If model doesn't support tools, fall back to simple completion
                    if "tools" in str(e).lower() or "function" in str(e).lower():
                        log_debug_message(f"⚠️ Ollama model doesn't support tools, falling back to simple completion")
                        return self.ai_cell_completion(prompt)
                    raise

                message = response.choices[0].message

                # If no tool calls, return the response
                if not message.tool_calls:
                    result = message.content or ""
                    log_debug_message(f"🤖 Ollama AI Cell response: {len(result)} chars")
                    return result

                # Execute tool calls
                messages.append(message.model_dump())

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = _safe_json_loads(tool_call.function.arguments)

                    log_debug_message(f"🔧 AI Cell executing: {tool_name}({tool_args})")

                    if tool_name in ai_cell_tool_map:
                        try:
                            result = ai_cell_tool_map[tool_name](**tool_args)
                            tool_result = json.dumps(result)
                        except Exception as e:
                            tool_result = json.dumps({"error": str(e)})
                    else:
                        tool_result = json.dumps({"error": f"Unknown tool: {tool_name}"})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    })

            # Max iterations reached
            return "I've analyzed your notebook but reached the maximum number of tool calls. Please ask a more specific question."

        except Exception as e:
            log_debug_message(f"Ollama ai_cell_with_tools error: {e}")
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
