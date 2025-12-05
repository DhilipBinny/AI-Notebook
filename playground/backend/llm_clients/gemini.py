"""
Gemini LLM Client - Google's Generative AI implementation (new google.genai SDK)

Implements the BaseLLMClient interface for Gemini models.
Supports both automatic and manual (approval-based) function calling.
Uses a two-phase approach for web search:
  - Phase 1: Detect if search is needed and perform search with native Google Search
  - Phase 2: Execute function tools with search context injected
"""

import json
from google import genai
from google.genai import types
from typing import List, Dict, Any, Optional, Union

from backend.llm_clients.base import BaseLLMClient
from backend.utils.util_func import log_response_details, log_debug_message
from backend.llm_tools import TOOL_FUNCTIONS, AI_CELL_TOOLS
import backend.config as cfg


# Build tool map for manual execution
# Filter out web_search since we handle it natively
TOOL_FUNCTIONS_NO_SEARCH = [f for f in TOOL_FUNCTIONS if f.__name__ != 'web_search']
TOOL_MAP = {func.__name__: func for func in TOOL_FUNCTIONS_NO_SEARCH}

# AI Cell tool map (inspection + sandbox only)
AI_CELL_TOOL_MAP = {func.__name__: func for func in AI_CELL_TOOLS}

# Keywords that suggest web search is needed
SEARCH_KEYWORDS = [
    'search', 'find', 'look up', 'lookup', 'google', 'web',
    'latest', 'recent', 'current', 'today', 'now', 'news',
    'what is the', 'who is', 'when is', 'where is',
    'weather', 'stock', 'price', 'score',
    '2024', '2025',  # Recent dates
]


class GeminiClient(BaseLLMClient):
    """Gemini LLM client with tool calling and Google Search support (two-phase approach)"""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", auto_function_calling: Optional[bool] = None, enable_web_search: bool = True):
        """
        Initialize Gemini client.

        Args:
            api_key: Gemini API key
            model_name: Model to use (default: gemini-2.5-flash)
            auto_function_calling: Override config setting. If None, uses cfg.AUTO_FUNCTION_CALLING
            enable_web_search: Enable Google Search grounding for real-time web info (default: True)
        """
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.enable_web_search = enable_web_search

        # Use config value if not explicitly set
        self.auto_function_calling = auto_function_calling if auto_function_calling is not None else cfg.AUTO_FUNCTION_CALLING

        log_debug_message(f"Gemini tools configured with {len(TOOL_FUNCTIONS_NO_SEARCH)} functions (excluding web_search)")
        tool_names = [func.__name__ for func in TOOL_FUNCTIONS_NO_SEARCH]
        log_debug_message(f"Gemini client initialized with tools: {tool_names}")
        log_debug_message(f"Auto function calling: {self.auto_function_calling}")
        log_debug_message(f"Web search enabled (two-phase): {self.enable_web_search}")

        # Initialize chat history
        self.history: List[Dict[str, Any]] = []
        self._start_chat()

    def _build_config(self) -> types.GenerateContentConfig:
        """Build the GenerateContentConfig with tools and system instruction (NO search tool)"""
        if self.auto_function_calling:
            # For automatic function calling, pass Python functions directly
            config = types.GenerateContentConfig(
                system_instruction=self.SYSTEM_PROMPT,
                tools=TOOL_FUNCTIONS_NO_SEARCH,  # Exclude web_search
            )
        else:
            # For manual mode, use FunctionDeclarations
            tools_list = [types.Tool(function_declarations=[
                self._func_to_declaration(func) for func in TOOL_FUNCTIONS_NO_SEARCH
            ])]
            config = types.GenerateContentConfig(
                system_instruction=self.SYSTEM_PROMPT,
                tools=tools_list,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )

        return config

    def _build_search_config(self) -> types.GenerateContentConfig:
        """Build config for search-only requests (with Google Search grounding, NO function tools)"""
        return types.GenerateContentConfig(
            system_instruction="You are a helpful assistant. Search the web and provide relevant, accurate information based on the search results.",
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )

    def _needs_web_search(self, message: str, user_message_only: str = None) -> bool:
        """
        Determine if the message likely needs web search.

        Args:
            message: The full message (used for search query if triggered)
            user_message_only: Optional - just the user's question (used for keyword detection)
                               If not provided, uses the full message for detection
        """
        if not self.enable_web_search:
            log_debug_message("🔍 Web search: DISABLED")
            return False

        # Use user_message_only for keyword detection if provided
        # This prevents false triggers from notebook context containing keywords like "find", "search", etc.
        check_text = (user_message_only if user_message_only else message).lower()

        # Check for search keywords
        for keyword in SEARCH_KEYWORDS:
            if keyword in check_text:
                log_debug_message(f"🔍 Web search: TRIGGERED (keyword: '{keyword}')")
                return True

        log_debug_message("🔍 Web search: NOT NEEDED (no keywords matched)")
        return False

    def _do_google_search(self, query: str) -> str:
        """
        Perform a web search using Gemini's native Google Search grounding.
        This is a separate API call without function tools.

        Args:
            query: The search query

        Returns:
            Search results as formatted text
        """
        try:
            log_debug_message(f"🌐 [PHASE 1] Google Search START - Query: {query[:50]}...")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=f"Search the web and provide comprehensive information about: {query}",
                config=self._build_search_config()
            )

            # Extract search results and grounding metadata
            result_text = response.text if response.text else ""

            # Check for grounding metadata (sources)
            sources = []
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    metadata = candidate.grounding_metadata
                    if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                        for chunk in metadata.grounding_chunks[:5]:  # Limit to 5 sources
                            if hasattr(chunk, 'web') and chunk.web:
                                sources.append({
                                    'title': chunk.web.title if hasattr(chunk.web, 'title') else '',
                                    'uri': chunk.web.uri if hasattr(chunk.web, 'uri') else ''
                                })

            # Format the search results
            formatted_result = f"=== WEB SEARCH RESULTS ===\n{result_text}\n"

            if sources:
                formatted_result += "\n=== SOURCES ===\n"
                for i, source in enumerate(sources, 1):
                    formatted_result += f"{i}. {source['title']}: {source['uri']}\n"

            formatted_result += "=== END SEARCH RESULTS ===\n"

            log_debug_message(f"🌐 [PHASE 1] Google Search DONE - {len(result_text)} chars, {len(sources)} sources")
            return formatted_result

        except Exception as e:
            log_debug_message(f"🌐 [PHASE 1] Google Search FAILED - {e}")
            return f"[Web search failed: {str(e)}]"

    def _func_to_declaration(self, func) -> types.FunctionDeclaration:
        """Convert a Python function to a FunctionDeclaration"""
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

        return types.FunctionDeclaration(
            name=func_name,
            description=description.strip(),
            parameters={
                "type": "object",
                "properties": properties,
                "required": required
            }
        )

    def _start_chat(self, history: List = None):
        """Start a new chat session with appropriate settings"""
        chat_history = []

        # Convert history to the format expected by the new SDK
        if history:
            for msg in history:
                role = msg.get("role", "user")
                if role == "model":
                    role = "model"
                parts = msg.get("parts", [])
                if isinstance(parts, list) and len(parts) > 0:
                    text = parts[0] if isinstance(parts[0], str) else parts[0].get("text", "")
                else:
                    text = str(parts)

                chat_history.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=text)]
                    )
                )
            log_debug_message(f"Gemini chat started with {len(chat_history)} history messages")

        self.chat = self.client.chats.create(
            model=self.model_name,
            config=self._build_config(),
            history=chat_history if chat_history else None
        )

    def send_message(self, message: str, user_message: str = None) -> Union[str, Dict[str, Any]]:
        """
        Send a message to Gemini using two-phase approach.

        Phase 1: If search is needed, perform Google Search (separate call)
        Phase 2: Send message with search context to main chat (with function tools)

        Args:
            message: The full message (may include context)
            user_message: Optional - just the user's actual question (for web search keyword detection)

        Returns:
            str: Final response text (if auto mode or no tools needed)
            dict: {"pending_tool_calls": [...], "response_text": "..."} (if manual mode with tools)
        """
        try:
            log_debug_message(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            log_debug_message(f"📨 Gemini send_message() - User: {message[:60]}...")
            log_debug_message(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Phase 1: Check if web search is needed (use user_message for keyword detection)
            search_context = ""
            if self._needs_web_search(message, user_message):
                # Use user_message for search query if available, otherwise use full message
                search_query = user_message if user_message else message
                search_context = self._do_google_search(search_query)

            # Phase 2: Send to main chat with function tools
            if search_context:
                # Inject search results into the message
                enhanced_message = f"{search_context}\n\nUser question: {message}\n\nPlease answer based on the search results above and your knowledge."
                log_debug_message(f"🤖 [PHASE 2] Sending to Gemini WITH search context")
            else:
                enhanced_message = message
                log_debug_message(f"🤖 [PHASE 2] Sending to Gemini (no search)")

            response = self.chat.send_message(message=enhanced_message)
            log_debug_message(f"✅ Gemini response received")

            # Debug: Log response details
            log_debug_message(f"Response text: {response.text[:100] if response.text else 'None'}...")
            log_debug_message(f"Response candidates: {len(response.candidates) if hasattr(response, 'candidates') and response.candidates else 0}")

            # Check if there were function calls in auto mode
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                log_debug_message(f"Candidate finish_reason: {candidate.finish_reason if hasattr(candidate, 'finish_reason') else 'unknown'}")
                if hasattr(candidate, 'content') and candidate.content and candidate.content.parts:
                    log_debug_message(f"Candidate parts count: {len(candidate.content.parts)}")
                    for i, part in enumerate(candidate.content.parts):
                        log_debug_message(f"Part {i} type: {type(part).__name__}")
                        if hasattr(part, 'text') and part.text:
                            log_debug_message(f"Part {i} text: {part.text[:50]}...")
                        if hasattr(part, 'function_call') and part.function_call:
                            log_debug_message(f"🔧 Part {i} function_call: {part.function_call.name}")
                        if hasattr(part, 'function_response') and part.function_response:
                            log_debug_message(f"🔧 Part {i} function_response: {part.function_response.name}")
                else:
                    log_debug_message(f"Candidate has no content parts")

            # If auto mode, tools are already executed - just return text
            if self.auto_function_calling:
                log_debug_message(f"Auto mode - returning text")
                # Check for MALFORMED_FUNCTION_CALL and try to extract any text
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = candidate.finish_reason if hasattr(candidate, 'finish_reason') else None
                    if str(finish_reason) == "FinishReason.MALFORMED_FUNCTION_CALL":
                        log_debug_message(f"⚠️ MALFORMED_FUNCTION_CALL detected - Gemini generated invalid function call")
                        # Try to extract any partial text or error info
                        if hasattr(candidate, 'content') and candidate.content and candidate.content.parts:
                            for part in candidate.content.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    fc = part.function_call
                                    log_debug_message(f"⚠️ Malformed call was: {fc.name}({fc.args})")
                        # Check if there's grounding metadata with the error
                        if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                            log_debug_message(f"⚠️ Grounding metadata: {candidate.grounding_metadata}")
                        # Try to get any text from the response
                        if hasattr(response, 'text') and response.text:
                            return response.text
                        return "I encountered an error while trying to execute the requested action. Please try a simpler request - for example, ask me to add a markdown cell before a specific cell number."

                # Handle case where tools were executed but no text was returned
                if not response.text:
                    # Check if any tools were executed by looking at chat history
                    log_debug_message(f"⚠️ No text in response, but tools may have been executed")
                    return "I've completed the requested actions. Please check your notebook for the changes."

                return response.text or ""

            # Manual mode: Check if model wants to call tools
            pending_tools = []
            response_text = ""

            # Check for function calls in the response
            if response.function_calls:
                for fc in response.function_calls:
                    log_debug_message(f"Pending function call: {fc.name}")
                    pending_tools.append({
                        "id": f"{fc.name}_{len(pending_tools)}",
                        "name": fc.name,
                        "arguments": dict(fc.args) if fc.args else {}
                    })

            # Get text from response
            if response.text:
                response_text = response.text

            if pending_tools:
                # Store pending state for later execution
                self._pending_function_calls = response.function_calls
                return {
                    "pending_tool_calls": pending_tools,
                    "response_text": response_text
                }
            else:
                return response_text or response.text

        except Exception as e:
            log_debug_message(f"Gemini error: {e}")
            import traceback
            log_debug_message(f"Traceback: {traceback.format_exc()}")
            return f"Gemini Error: {e}"

    def execute_approved_tools(self, approved_tool_calls: List[Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
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
            function_responses = []

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

                        # Convert result to string for the response
                        if isinstance(result, (dict, list)):
                            result_str = json.dumps(result)
                        else:
                            result_str = str(result)

                        function_responses.append(
                            types.FunctionResponse(
                                name=tool_name,
                                response={"result": result_str}
                            )
                        )
                    except Exception as e:
                        error_result = {"error": str(e)}
                        tool_results.append({
                            "name": tool_name,
                            "result": error_result
                        })
                        function_responses.append(
                            types.FunctionResponse(
                                name=tool_name,
                                response={"error": str(e)}
                            )
                        )
                else:
                    error_result = {"error": f"Unknown tool: {tool_name}"}
                    tool_results.append({
                        "name": tool_name,
                        "result": error_result
                    })
                    function_responses.append(
                        types.FunctionResponse(
                            name=tool_name,
                            response={"error": f"Unknown tool: {tool_name}"}
                        )
                    )

            # Send tool results back to Gemini
            log_debug_message(f"Sending {len(function_responses)} function responses to Gemini")
            response = self.chat.send_message(function_responses)
            log_debug_message(f"Response after tool execution: {response}")

            # Check for additional function calls
            pending_tools = []
            final_text = ""

            if response.function_calls:
                for fc in response.function_calls:
                    log_debug_message(f"Model wants to call another function: {fc.name}")
                    pending_tools.append({
                        "id": f"{fc.name}_{len(pending_tools)}",
                        "name": fc.name,
                        "arguments": dict(fc.args) if fc.args else {}
                    })

            if response.text:
                final_text = response.text

            log_debug_message(f"Final text: {final_text[:200] if final_text else 'No text'}...")

            # If there are more pending tools, return them for approval
            if pending_tools:
                log_debug_message(f"Returning {len(pending_tools)} additional pending tools")
                return {
                    "pending_tool_calls": pending_tools,
                    "response_text": final_text,
                    "tool_results": tool_results
                }

            # Return response with tool results for tracking
            return {
                "response_text": final_text if final_text else "Tool executed successfully.",
                "tool_results": tool_results
            }

        except Exception as e:
            log_debug_message(f"Error executing approved tools: {e}")
            import traceback
            log_debug_message(f"Traceback: {traceback.format_exc()}")
            return f"Error executing tools: {e}"

    def clear_history(self) -> None:
        """Clear conversation history by starting a new chat"""
        self.history = []
        self._start_chat()

    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history in Gemini format"""
        # Convert from new SDK format to legacy format for compatibility
        history = []
        if hasattr(self.chat, '_curated_history'):
            for content in self.chat._curated_history:
                role = content.role
                parts = []
                for part in content.parts:
                    if hasattr(part, 'text') and part.text:
                        parts.append(part.text)
                if parts:
                    history.append({
                        "role": role,
                        "parts": parts
                    })
        return history

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
            max_tokens: Maximum tokens in response

        Returns:
            The response text from the LLM
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens
                )
            )
            return response.text
        except Exception as e:
            log_debug_message(f"Gemini chat_completion error: {e}")
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
            log_debug_message(f"🤖 Gemini AI Cell completion starting...")

            # Check if web search might help
            search_context = ""
            if self._needs_web_search(prompt):
                search_context = self._do_google_search(prompt)

            # Build the final prompt with search context if available
            if search_context:
                enhanced_prompt = f"{search_context}\n\n{prompt}"
                log_debug_message(f"🤖 AI Cell: Using web search context")
            else:
                enhanced_prompt = prompt

            # Use simple generate_content (no tools, no chat session)
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=enhanced_prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=4096  # Allow longer responses for AI cells
                )
            )

            result = response.text or ""
            log_debug_message(f"🤖 Gemini AI Cell response: {len(result)} chars")
            return result

        except Exception as e:
            log_debug_message(f"Gemini ai_cell_completion error: {e}")
            raise

    def ai_cell_with_tools(self, prompt: str, max_iterations: int = 10) -> str:
        """
        AI Cell completion with tool calling support.
        Focuses on kernel inspection and sandbox tools only (no web search).

        Args:
            prompt: The full prompt including notebook context and user question
            max_iterations: Maximum number of tool-calling iterations

        Returns:
            The final response text from the LLM
        """
        try:
            log_debug_message(f"🤖 Gemini AI Cell with tools starting...")
            log_debug_message(f"🔧 Available tools: {list(AI_CELL_TOOL_MAP.keys())}")

            # AI Cell focuses on notebook context and tools - no web search
            # This ensures the LLM uses kernel inspection and sandbox tools effectively
            final_prompt = prompt

            # Create chat session with AI Cell tools (inspection + sandbox only)
            ai_cell_config = types.GenerateContentConfig(
                system_instruction="You are an AI assistant in a notebook cell. Use kernel inspection tools to understand the notebook state and sandbox tools to test code safely. Focus on the notebook context provided.",
                tools=AI_CELL_TOOLS,  # Kernel inspection + sandbox tools only
            )

            chat = self.client.chats.create(
                model=self.model_name,
                config=ai_cell_config,
            )

            # Send the message - tools will be auto-executed
            log_debug_message(f"🤖 Sending AI Cell message with auto tool execution...")
            response = chat.send_message(message=final_prompt)

            # In auto mode, tools are already executed - just return text
            result = response.text or ""

            # Handle edge cases
            if not result:
                # Check for malformed function calls or other issues
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = candidate.finish_reason if hasattr(candidate, 'finish_reason') else None
                    if str(finish_reason) == "FinishReason.MALFORMED_FUNCTION_CALL":
                        log_debug_message(f"⚠️ AI Cell: MALFORMED_FUNCTION_CALL detected")
                        result = "I encountered an error while trying to analyze your notebook. Please try a more specific question."

                if not result:
                    result = "I've analyzed your notebook using the available tools. Please let me know if you need more specific information."

            log_debug_message(f"🤖 Gemini AI Cell with tools response: {len(result)} chars")
            return result

        except Exception as e:
            log_debug_message(f"Gemini ai_cell_with_tools error: {e}")
            import traceback
            log_debug_message(f"Traceback: {traceback.format_exc()}")
            raise
