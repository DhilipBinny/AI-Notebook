"""
Ollama LLM Client - Ollama API implementation (OpenAI-compatible)

Extends the OpenAI client since Ollama provides an OpenAI-compatible API.
No API key required - just needs the Ollama server URL.

Note: Tool/function calling support depends on the Ollama model.
Models like llama3.1, mistral, and qwen2.5 support tools.
"""

import json
from typing import List, Dict, Any, Optional, Union
from openai import OpenAI

from backend.llm_client_openai import OpenAIClient, _build_openai_tools, TOOL_MAP
from backend.llm_client_base import BaseLLMClient
from backend.utils.util_func import log_debug_message
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

    def send_message(self, message: str) -> Union[str, Dict[str, Any]]:
        """
        Send a message to Ollama.

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
                    func_args = json.loads(tool_call.function.arguments)
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
