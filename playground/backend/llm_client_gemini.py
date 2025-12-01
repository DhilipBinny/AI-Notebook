"""
Gemini LLM Client - Google's Generative AI implementation

Implements the BaseLLMClient interface for Gemini models.
Supports both automatic and manual (approval-based) function calling.
"""

import json
import google.generativeai as genai
from google.generativeai import types
from typing import List, Dict, Any, Optional, Tuple

from backend.llm_client_base import BaseLLMClient
from backend.utils.util_func import log_response_details, log_debug_message
from backend.llm_tools import TOOL_FUNCTIONS
import backend.config as cfg


# Build tool map for manual execution
TOOL_MAP = {func.__name__: func for func in TOOL_FUNCTIONS}


class GeminiClient(BaseLLMClient):
    """Gemini LLM client with tool calling support"""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", auto_function_calling: Optional[bool] = None):
        """
        Initialize Gemini client.

        Args:
            api_key: Gemini API key
            model_name: Model to use (default: gemini-2.5-flash)
            auto_function_calling: Override config setting. If None, uses cfg.AUTO_FUNCTION_CALLING
        """
        genai.configure(api_key=api_key)

        # Use config value if not explicitly set
        self.auto_function_calling = auto_function_calling if auto_function_calling is not None else cfg.AUTO_FUNCTION_CALLING

        # Convert tool functions to Gemini format using types.Tool
        self.gemini_tools = [types.Tool(function_declarations=[
            types.FunctionDeclaration.from_function(func) for func in TOOL_FUNCTIONS
        ])]

        # Debug: Print tool names
        tool_names = [func.__name__ for func in TOOL_FUNCTIONS]
        log_debug_message(f"Gemini client initialized with tools: {tool_names}")
        log_debug_message(f"Auto function calling: {self.auto_function_calling}")

        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=self.SYSTEM_PROMPT,
            tools=self.gemini_tools
        )

        self._start_chat()

    def _start_chat(self, history: List = None):
        """Start a new chat session with appropriate settings"""
        self.chat = self.model.start_chat(
            history=history or [],
            enable_automatic_function_calling=self.auto_function_calling
        )
        # Only log when history is loaded (avoid duplicate logs)
        if history:
            log_debug_message(f"Gemini chat started with {len(history)} history messages")

    def send_message(self, message: str) -> str | Dict[str, Any]:
        """
        Send a message to Gemini.

        When auto_function_calling=True:
            Returns the final response text (tools executed automatically)

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
            log_debug_message(f"Sending message to Gemini (history length: {len(self.chat.history)})")
            response = self.chat.send_message(message)
            print("==> Gemini response: ", response)

            # If auto mode, tools are already executed - just return text
            if self.auto_function_calling:
                log_response_details(message, response)
                return response.text

            # Manual mode: Check if model wants to call tools
            pending_tools = []
            response_text = ""

            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call
                        log_debug_message(f"Pending function call: {fc.name}")
                        pending_tools.append({
                            "id": f"{fc.name}_{len(pending_tools)}",
                            "name": fc.name,
                            "arguments": dict(fc.args) if fc.args else {}
                        })
                    elif hasattr(part, 'text') and part.text:
                        response_text += part.text

            if pending_tools:
                # Return pending tools for approval
                return {
                    "pending_tool_calls": pending_tools,
                    "response_text": response_text
                }
            else:
                # No tools, just return text
                log_response_details(message, response)
                return response_text or response.text

        except Exception as e:
            log_debug_message(f"Gemini error: {e}")
            return f"Gemini Error: {e}"

    def execute_approved_tools(self, approved_tool_calls: List[Dict[str, Any]]) -> str:
        """
        Execute approved tool calls and get the final response from Gemini.

        Args:
            approved_tool_calls: List of approved tools to execute
                                [{"name": "...", "arguments": {...}}, ...]

        Returns:
            The final response text after tool execution
        """
        try:
            # Execute each tool and collect results
            tool_results = []
            for tool_call in approved_tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("arguments", {})

                log_debug_message(f"Executing approved tool: {tool_name} with args: {tool_args}")

                if tool_name in TOOL_MAP:
                    try:
                        result = TOOL_MAP[tool_name](**tool_args)
                        tool_results.append({
                            "name": tool_name,
                            "result": result
                        })
                        log_debug_message(f"Tool {tool_name} result: {result}")
                    except Exception as e:
                        tool_results.append({
                            "name": tool_name,
                            "result": {"error": str(e)}
                        })
                else:
                    tool_results.append({
                        "name": tool_name,
                        "result": {"error": f"Unknown tool: {tool_name}"}
                    })

            # Send tool results back to Gemini one by one
            # Following the exact pattern from the working code
            response = None
            for tr in tool_results:
                # Convert result to JSON string to avoid nested dict issues
                result_value = tr["result"]
                log_debug_message(f"Raw result type: {type(result_value)}, value: {str(result_value)[:200]}")

                if isinstance(result_value, (dict, list)):
                    result_value = json.dumps(result_value)
                else:
                    result_value = str(result_value)

                log_debug_message(f"Sending function response for {tr['name']}")

                # Send each function response individually (exact format from working code)
                response = self.chat.send_message(
                    genai.protos.Content(
                        parts=[genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=tr["name"],
                                response={'result': result_value}
                            )
                        )]
                    )
                )
                log_debug_message(f"Response received for {tr['name']}")
                log_debug_message(f"Response object: {response}")
                log_debug_message(f"Response candidates: {response.candidates}")

            # Check if response has more function calls or text
            log_debug_message(f"Final response parts: {response.parts if response else 'No response'}")

            # Get text from response and check for additional function calls
            final_text = ""
            pending_tools = []
            if response and response.parts:
                for part in response.parts:
                    if hasattr(part, 'text') and part.text:
                        final_text += part.text
                    elif hasattr(part, 'function_call') and part.function_call:
                        # Model wants to call another function
                        fc = part.function_call
                        log_debug_message(f"Model wants to call another function: {fc.name}")
                        pending_tools.append({
                            "id": f"{fc.name}_{len(pending_tools)}",
                            "name": fc.name,
                            "arguments": dict(fc.args) if fc.args else {}
                        })

            log_debug_message(f"Final text: {final_text[:200] if final_text else 'No text'}...")

            # If there are more pending tools, return them for approval
            if pending_tools:
                log_debug_message(f"Returning {len(pending_tools)} additional pending tools")
                return {
                    "pending_tool_calls": pending_tools,
                    "response_text": final_text,
                    "tool_results": tool_results  # Include tool results for step tracking
                }

            # Return response with tool results for tracking
            return {
                "response_text": final_text if final_text else "Tool executed successfully.",
                "tool_results": tool_results
            }

        except Exception as e:
            log_debug_message(f"Error executing approved tools: {e}")
            return f"Error executing tools: {e}"

    def clear_history(self) -> None:
        """Clear conversation history by starting a new chat"""
        self._start_chat()

    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history in Gemini format"""
        return self.chat.history

    def set_history(self, history_list: List[Dict[str, Any]]) -> None:
        """
        Set conversation history.

        Args:
            history_list: List in Gemini format:
                         [{"role": "user"/"model", "parts": ["..."]}]
        """
        self._start_chat(history=history_list)

    @property
    def provider_name(self) -> str:
        return "Gemini"

    def chat_completion(self, prompt: str, max_tokens: int = 1000) -> str:
        """
        Simple chat completion without tools.
        Used for summarization and other simple LLM tasks.

        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens in response (not used by Gemini directly)

        Returns:
            The response text from the LLM
        """
        try:
            # Create a simple model without tools for completion
            simple_model = genai.GenerativeModel(cfg.GEMINI_MODEL)
            response = simple_model.generate_content(prompt)
            return response.text
        except Exception as e:
            log_debug_message(f"Gemini chat_completion error: {e}")
            raise
