"""
Gemini LLM Client - Google's Generative AI implementation (new google.genai SDK)

Implements the BaseLLMClient interface for Gemini models.
Supports both automatic and manual (approval-based) function calling.
Uses a two-phase approach for web search:
  - Phase 1: Detect if search is needed and perform search with native Google Search
  - Phase 2: Execute function tools with search context injected

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
import base64
from google import genai
from google.genai import types
from typing import List, Dict, Any, Optional, Union, Callable

from backend.llm_clients.base import BaseLLMClient, ImageData, prepare_image, LLMResponse, ToolCall, ToolResult, CancelledException
from backend.llm_adapters.tool_schemas import build_gemini_tool_schema
from backend.utils.util_func import log
from backend.llm_tools import TOOL_FUNCTIONS, AI_CELL_TOOLS, ALL_AI_CELL_TOOLS, ALL_AI_CELL_TOOL_MAP
import backend.config as cfg

# Import the adapter for gradual migration
from backend.llm_adapters import GeminiAdapter, CanonicalToolResult, CanonicalResponse


# =============================================================================
# SECTION 1: MODULE-LEVEL SETUP
# =============================================================================
# Constants, tool definitions, and module-level helpers

# Build tool map for manual execution
# Filter out web_search since we handle it natively
TOOL_FUNCTIONS_NO_SEARCH = [f for f in TOOL_FUNCTIONS if f.__name__ != 'web_search']
TOOL_MAP = {func.__name__: func for func in TOOL_FUNCTIONS_NO_SEARCH}

# AI Cell tool map (inspection + sandbox only)
AI_CELL_TOOL_MAP = {func.__name__: func for func in AI_CELL_TOOLS}


class GeminiClient(BaseLLMClient):
    """Gemini LLM client with tool calling and Google Search support (two-phase approach)"""

    # =========================================================================
    # SECTION 2: INITIALIZATION & CONFIGURATION
    # =========================================================================

    def __init__(self, api_key: str, model_name: str = None, auto_function_calling: Optional[bool] = None, enable_web_search: bool = True):
        """
        Initialize Gemini client.

        Args:
            api_key: Gemini API key
            model_name: Model to use (default: gemini-2.5-flash)
            auto_function_calling: Override config setting. If None, uses cfg.AUTO_FUNCTION_CALLING
            enable_web_search: Enable Google Search grounding for real-time web info (default: True)
        """
        super().__init__()  # Initialize base class (cancellation support)

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name or cfg.GEMINI_MODEL
        self.enable_web_search = enable_web_search

        # Initialize the adapter for format translation
        self.adapter = GeminiAdapter()

        # Use config value if not explicitly set
        self.auto_function_calling = auto_function_calling if auto_function_calling is not None else cfg.AUTO_FUNCTION_CALLING

        log(f"Gemini tools configured with {len(TOOL_FUNCTIONS_NO_SEARCH)} functions (excluding web_search)")
        tool_names = [func.__name__ for func in TOOL_FUNCTIONS_NO_SEARCH]
        log(f"Gemini client initialized with tools: {tool_names}")
        log(f"Config: tool_mode={cfg.TOOL_EXECUTION_MODE}, auto_func={self.auto_function_calling} (request may override)")
        log(f"Web search: {'enabled (two-phase for chat, grounding for AI cell)' if self.enable_web_search else 'disabled'}")

        # Initialize chat history
        self.history: List[Dict[str, Any]] = []
        self._gemini_start_chat()

        # Cache AI Cell tools (built once)
        self._ai_cell_tools_cache: Optional[List[types.Tool]] = None
        self._ai_cell_tool_map_cache: Optional[Dict[str, Callable]] = None

    def _gemini_build_config(self) -> types.GenerateContentConfig:
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
                self._gemini_func_to_declaration(func) for func in TOOL_FUNCTIONS_NO_SEARCH
            ])]
            config = types.GenerateContentConfig(
                system_instruction=self.SYSTEM_PROMPT,
                tools=tools_list,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )

        return config

    def _gemini_build_search_config(self) -> types.GenerateContentConfig:
        """Build config for search-only requests (with Google Search grounding, NO function tools)"""
        return types.GenerateContentConfig(
            system_instruction="You are a helpful assistant. Search the web and provide relevant, accurate information based on the search results.",
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )

    def _gemini_start_chat(self, history: List = None):
        """Start a new chat session with appropriate settings"""
        chat_history = []

        # Convert history to the format expected by the new SDK
        if history:
            for msg in history:
                role = msg.get("role", "user")
                if role == "assistant":
                    role = "model"  # Convert OpenAI/Anthropic format to Gemini format
                # Support both "parts" (Gemini format) and "content" (standard format)
                parts = msg.get("parts", [])
                if isinstance(parts, list) and len(parts) > 0:
                    text = parts[0] if isinstance(parts[0], str) else parts[0].get("text", "")
                elif "content" in msg:
                    text = msg.get("content", "")
                else:
                    text = str(parts)

                chat_history.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=text)]
                    )
                )
            log(f"Gemini chat started with {len(chat_history)} history messages")

        self.chat = self.client.chats.create(
            model=self.model_name,
            config=self._gemini_build_config(),
            history=chat_history if chat_history else None
        )

    def _gemini_func_to_declaration(self, func) -> types.FunctionDeclaration:
        """Convert a Python function to a FunctionDeclaration using shared schema builder"""
        schema = build_gemini_tool_schema(func)
        return types.FunctionDeclaration(
            name=schema["name"],
            description=schema["description"],
            parameters=schema["parameters"]
        )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens using Gemini's native API.

        Args:
            text: The text to count tokens for

        Returns:
            Token count, or 0 if counting fails
        """
        try:
            token_count = self.client.models.count_tokens(
                model=self.model_name,
                contents=text
            )
            return token_count.total_tokens
        except Exception:
            return 0

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
        Send a message to Gemini using two-phase approach.

        Phase 1: If search is needed, perform Google Search (separate call)
        Phase 2: Send message with search context to main chat (with function tools)

        Args:
            notebook_context: Formatted notebook context
            user_prompt: User's question/prompt
            images: Optional list of images for visual analysis

        Note: Gemini automatically caches repeated content, so we just combine
        notebook_context and user_prompt into a single message.

        Returns:
            str: Final response text (if auto mode or no tools needed)
            dict: {"pending_tool_calls": [...], "response_text": "..."} (if manual mode with tools)
        """
        try:
            from backend.utils.util_func import log_chat
            mode = "auto" if self.auto_function_calling else "manual"

            # Count tokens using self.count_tokens()
            full_text = f"{notebook_context}\n\n{user_prompt}" if notebook_context else user_prompt
            input_tokens = self.count_tokens(full_text)

            log_chat(
                provider="Gemini",
                model=self.model_name,
                mode=mode,
                context_chars=len(notebook_context),
                prompt_chars=len(user_prompt),
                images=len(images) if images else 0,
                web_search=self.enable_web_search,
                input_tokens=input_tokens
            )

            # Emit thinking progress
            self._emit_progress("thinking", {"message": "Processing your request..."})

            # Combine context and user_prompt for Gemini (automatic caching handles efficiency)
            if notebook_context:
                message = f"{notebook_context}\n\n{user_prompt}"
            else:
                message = user_prompt

            # Phase 1: Check if web search is needed (Gemini uses two-phase: search then complete)
            search_context = ""
            if self._needs_web_search(user_prompt):
                self._emit_progress("thinking", {"message": "Searching the web..."})
                search_context = self._gemini_do_google_search(user_prompt)

            # Phase 2: Send to main chat with function tools
            if search_context:
                # Inject search results into the message
                enhanced_message = f"{search_context}\n\nUser question: {message}\n\nPlease answer based on the search results above and your knowledge."
                log("🤖 [PHASE 2] Sending to Gemini WITH search context")
            else:
                enhanced_message = message
                log("🤖 [PHASE 2] Sending to Gemini (no search)")

            # Build content with optional images
            content = self._build_content_with_images(enhanced_message, images)

            self._emit_progress("thinking", {"message": "Waiting for AI response..."})

            try:
                response = self.chat.send_message(message=content)
                log("✅ Gemini response received")
                self._emit_progress("thinking", {"message": "Processing response..."})
            except KeyError as e:
                # Gemini SDK throws KeyError when it tries to call a hallucinated tool
                # that doesn't exist in our function_map
                tool_name = str(e).strip("'")
                log(f"⚠️ Gemini tried to call non-existent tool: {tool_name}")
                # Restart chat to clear the bad state and try without the hallucinated tool
                self._gemini_start_chat()
                # Add a hint about available tools
                retry_message = f"{enhanced_message}\n\n(Note: Use only the available tools. There is no '{tool_name}' tool.)"
                content = self._build_content_with_images(retry_message, images)
                response = self.chat.send_message(message=content)
                log("✅ Gemini retry response received")

            # Log cache usage
            self._log_cache_usage(response)

            # Debug: Log response details
            log(f"Response text: {response.text[:100] if response.text else 'None'}...")
            log(f"Response candidates: {len(response.candidates) if hasattr(response, 'candidates') and response.candidates else 0}")

            # Check if there were function calls in auto mode
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                log(f"Candidate finish_reason: {candidate.finish_reason if hasattr(candidate, 'finish_reason') else 'unknown'}")
                if hasattr(candidate, 'content') and candidate.content and candidate.content.parts:
                    log(f"Candidate parts count: {len(candidate.content.parts)}")
                    for i, part in enumerate(candidate.content.parts):
                        log(f"Part {i} type: {type(part).__name__}")
                        if hasattr(part, 'text') and part.text:
                            log(f"Part {i} text: {part.text[:50]}...")
                        if hasattr(part, 'function_call') and part.function_call:
                            log(f"🔧 Part {i} function_call: {part.function_call.name}")
                        if hasattr(part, 'function_response') and part.function_response:
                            log(f"🔧 Part {i} function_response: {part.function_response.name}")
                else:
                    log("Candidate has no content parts")

            # If auto mode, tools are already executed - just return text
            if self.auto_function_calling:
                log("Auto mode - returning text")
                # Check for MALFORMED_FUNCTION_CALL and retry without tools
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = candidate.finish_reason if hasattr(candidate, 'finish_reason') else None
                    if str(finish_reason) == "FinishReason.MALFORMED_FUNCTION_CALL":
                        log("⚠️ MALFORMED_FUNCTION_CALL detected - retrying without tools")
                        # Restart chat and retry with simpler prompt
                        self._gemini_start_chat()
                        simple_prompt = f"Please answer this question directly based on the context provided. Do not use any tools.\n\n{enhanced_message}"
                        try:
                            # Make a simple call without expecting tool use
                            simple_response = self.chat.send_message(message=simple_prompt)
                            if simple_response.text:
                                log("✅ Retry without tools succeeded")
                                return simple_response.text
                        except Exception as retry_err:
                            log(f"⚠️ Retry failed: {retry_err}")
                        # If retry also failed, return helpful message
                        return "I couldn't process that request. Based on the notebook context, pandas is not currently imported in any cell. You can check the imports by looking at the code cells that start with 'from' or 'import'."

                # Handle case where tools were executed but no text was returned
                if not response.text:
                    # Check if any tools were executed by looking at chat history
                    log("⚠️ No text in response, but tools may have been executed")
                    return "I've completed the requested actions. Please check your notebook for the changes."

                return response.text or ""

            # Manual mode: Check if model wants to call tools
            pending_tools = []
            response_text = ""

            # Check for function calls in the response
            if response.function_calls:
                for fc in response.function_calls:
                    log(f"Pending function call: {fc.name}")
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
            log(f"Gemini error: {e}")
            import traceback
            log(f"Traceback: {traceback.format_exc()}")
            error_msg = str(e)
            if "key" in error_msg.lower() or "auth" in error_msg.lower() or "AIza" in error_msg:
                return "Gemini API error. Please check your API key configuration."
            return "Gemini Error: An unexpected error occurred. Please try again."

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

                log(f"Executing approved tool: {tool_name} with args: {tool_args}")

                if tool_name in TOOL_MAP:
                    try:
                        result = TOOL_MAP[tool_name](**tool_args)
                        tool_results.append({
                            "name": tool_name,
                            "result": result
                        })
                        log(f"Tool {tool_name} result: {result}")

                        # Convert result to string for the response
                        if isinstance(result, (dict, list)):
                            result_str = json.dumps(result)
                        else:
                            result_str = str(result)

                        function_responses.append(
                            types.Part.from_function_response(
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
                            types.Part.from_function_response(
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
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"error": f"Unknown tool: {tool_name}"}
                        )
                    )

            # Send tool results back to Gemini
            log(f"Sending {len(function_responses)} function responses to Gemini")
            response = self.chat.send_message(function_responses)

            # Log cache usage
            self._log_cache_usage(response)

            log(f"Response after tool execution: {response}")

            # Check for additional function calls
            pending_tools = []
            final_text = ""

            if response.function_calls:
                for fc in response.function_calls:
                    log(f"Model wants to call another function: {fc.name}")
                    pending_tools.append({
                        "id": f"{fc.name}_{len(pending_tools)}",
                        "name": fc.name,
                        "arguments": dict(fc.args) if fc.args else {}
                    })

            if response.text:
                final_text = response.text

            log(f"Final text: {final_text[:200] if final_text else 'No text'}...")

            # If there are more pending tools, return them for approval
            if pending_tools:
                log(f"Returning {len(pending_tools)} additional pending tools")
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
            log(f"Error executing approved tools: {e}")
            import traceback
            log(f"Traceback: {traceback.format_exc()}")
            return f"Error executing tools: {e}"

    # =========================================================================
    # SECTION 4: HISTORY MANAGEMENT
    # =========================================================================

    def clear_history(self) -> None:
        """Clear conversation history by starting a new chat"""
        self.history = []
        self._gemini_start_chat()

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
        self._gemini_start_chat(history=history_list)

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
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens
                )
            )
            # Log cache usage
            self._log_cache_usage(response)
            return response.text
        except Exception as e:
            log(f"Gemini simple_completion error: {e}")
            raise

    # =========================================================================
    # SECTION 6: AI CELL - Tool Execution Framework
    # =========================================================================
    # These methods implement the unified tool execution interface for AI Cells
    # Used for notebook inspection and code execution tools

    def _get_ai_cell_tools(self, allowed_tools: Optional[List[str]] = None) -> List[types.Tool]:
        """
        Get AI Cell tools in Gemini format (FunctionDeclarations for manual execution).
        Uses cached full set, then filters by allowed_tools if provided.
        """
        if self._ai_cell_tools_cache is None:
            declarations = [self._gemini_func_to_declaration(func) for func in ALL_AI_CELL_TOOLS]
            self._ai_cell_tools_cache = declarations
        declarations = self._ai_cell_tools_cache
        if allowed_tools is not None:
            allowed_set = set(allowed_tools)
            declarations = [d for d in declarations if d.name in allowed_set]
        return [types.Tool(function_declarations=declarations)]

    def _get_ai_cell_tool_map(self, allowed_tools: Optional[List[str]] = None) -> Dict[str, Callable]:
        """Get mapping of tool names to callable functions for AI Cell."""
        if self._ai_cell_tool_map_cache is None:
            self._ai_cell_tool_map_cache = dict(ALL_AI_CELL_TOOL_MAP)
        tool_map = self._ai_cell_tool_map_cache
        if allowed_tools is not None:
            allowed_set = set(allowed_tools)
            return {k: v for k, v in tool_map.items() if k in allowed_set}
        return tool_map

    def _prepare_ai_cell_messages(
        self,
        notebook_context: str,
        user_prompt: str,
        images: Optional[List[ImageData]] = None
    ) -> List[types.Content]:
        """
        Prepare initial messages for AI Cell in Gemini format.

        Args:
            notebook_context: Formatted notebook context (Gemini handles caching automatically)
            user_prompt: User's question/prompt
            images: Optional images
        """
        # Combine context and user prompt (Gemini handles caching automatically)
        full_prompt = f"{notebook_context}\n\n{user_prompt}" if notebook_context else user_prompt
        content = self._build_content_with_images(full_prompt, images)

        # Debug logging
        log(f"📋 AI Cell messages: context={len(notebook_context)} chars, user_prompt={len(user_prompt)} chars")
        if images:
            log(f"📷 Sending {len(images)} image(s) to Gemini")

        # Convert content to Gemini Content format
        if isinstance(content, str):
            parts = [types.Part.from_text(text=content)]
        else:
            parts = content  # Already a list of Parts

        return [types.Content(role="user", parts=parts)]

    def _call_llm_for_ai_cell(self, messages: List[types.Content], tools: List[types.Tool]) -> LLMResponse:
        """
        Make an LLM API call for AI Cell tool execution.

        Uses generate_content_stream for cancellation support during LLM response.
        Checks for cancellation between chunks to allow early termination.
        Enables thinking mode for Gemini 2.5 models to show reasoning process.

        Args:
            messages: Gemini Content format
            tools: Gemini Tool format (FunctionDeclarations)

        Returns:
            LLMResponse with text, tool_calls, thinking, and is_final flag
        """
        # Enable thinking for Gemini 2.5 models
        thinking_config = None
        if "2.5" in self.model_name or "2.0" in self.model_name:
            thinking_config = types.ThinkingConfig(
                thinking_budget=8192,  # Allow up to 8K tokens for thinking
                include_thoughts=True  # Include thought summaries in response
            )
            log("💭 Gemini thinking mode enabled (budget: 8192 tokens)")

        config = types.GenerateContentConfig(
            system_instruction=self.AI_CELL_SYSTEM_PROMPT,
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=thinking_config
        )

        # Use streaming to allow cancellation during LLM response
        text = ""
        thinking = ""
        tool_calls = []
        last_finish_reason = None
        last_usage_metadata = None

        try:
            response_stream = self.client.models.generate_content_stream(
                model=self.model_name,
                contents=messages,
                config=config
            )

            for chunk in response_stream:
                # ✅ CANCELLATION CHECK - between each chunk
                self._check_cancelled()

                # Track usage metadata (last chunk has accumulated totals)
                if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                    last_usage_metadata = chunk.usage_metadata

                if chunk.candidates and len(chunk.candidates) > 0:
                    candidate = chunk.candidates[0]

                    # Track finish reason
                    if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                        last_finish_reason = candidate.finish_reason

                    # FIRST: Extract any thinking/text/tool_calls from this chunk (even before error check)
                    if hasattr(candidate, 'content') and candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            # Check if this is a thinking/thought part
                            if hasattr(part, 'thought') and part.thought and hasattr(part, 'text') and part.text:
                                thinking += part.text
                                log(f"💭 Gemini thought chunk: {len(part.text)} chars")
                            elif hasattr(part, 'text') and part.text:
                                text += part.text
                            elif hasattr(part, 'function_call') and part.function_call:
                                fc = part.function_call
                                tool_calls.append(ToolCall(
                                    id=f"{fc.name}_{len(tool_calls)}",  # Gemini doesn't provide IDs
                                    name=fc.name,
                                    arguments=dict(fc.args) if fc.args else {}
                                ))

                    # Check for malformed function call (after extracting any content from this chunk)
                    if str(last_finish_reason) == "FinishReason.MALFORMED_FUNCTION_CALL":
                        log("⚠️ Gemini AI Cell: MALFORMED_FUNCTION_CALL detected")
                        log(f"⚠️ Full candidate: {candidate}")
                        log(f"⚠️ Candidate type: {type(candidate)}")
                        log(f"⚠️ Candidate attributes: {dir(candidate)}")

                        # Try to extract which function was malformed
                        if hasattr(candidate, 'content') and candidate.content:
                            log(f"⚠️ Content: {candidate.content}")
                            log(f"⚠️ Content type: {type(candidate.content)}")
                            if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                log(f"⚠️ Parts count: {len(candidate.content.parts)}")
                                for i, part in enumerate(candidate.content.parts):
                                    log(f"⚠️ Part {i}: {part}")
                                    log(f"⚠️ Part {i} type: {type(part)}")
                                    log(f"⚠️ Part {i} attributes: {dir(part)}")
                                    if hasattr(part, 'function_call') and part.function_call:
                                        fc = part.function_call
                                        log(f"⚠️ Malformed function: {fc.name}")
                                        log(f"⚠️ Malformed args: {fc.args}")
                                    if hasattr(part, 'text') and part.text:
                                        log(f"⚠️ Partial text: {part.text[:500]}")
                            else:
                                log("⚠️ No parts in content")
                        else:
                            log("⚠️ No content in candidate")

                        # Also check for any error message
                        if hasattr(candidate, 'safety_ratings'):
                            log(f"⚠️ Safety ratings: {candidate.safety_ratings}")
                        if hasattr(candidate, 'citation_metadata'):
                            log(f"⚠️ Citation metadata: {candidate.citation_metadata}")

                        # Include any thinking that was captured before the error
                        if thinking:
                            log(f"💭 Gemini thinking before error: {len(thinking)} chars")

                        # Extract usage even on error
                        error_usage = None
                        if last_usage_metadata:
                            error_usage = {
                                "input_tokens": getattr(last_usage_metadata, 'prompt_token_count', 0) or 0,
                                "output_tokens": getattr(last_usage_metadata, 'candidates_token_count', 0) or 0,
                                "cached_tokens": getattr(last_usage_metadata, 'cached_content_token_count', 0) or 0,
                            }
                        return LLMResponse(
                            text="I encountered an error while trying to analyze your notebook. Please try a more specific question.",
                            tool_calls=[],
                            is_final=True,
                            thinking=thinking,  # Include thinking even on error
                            usage=error_usage
                        )

        except CancelledException:
            # Re-raise to be handled by the caller
            raise

        # is_final when there are no tool calls
        is_final = len(tool_calls) == 0

        if thinking:
            log(f"💭 Gemini total thinking: {len(thinking)} chars")

        # Extract usage from last chunk's metadata
        usage = None
        if last_usage_metadata:
            usage = {
                "input_tokens": getattr(last_usage_metadata, 'prompt_token_count', 0) or 0,
                "output_tokens": getattr(last_usage_metadata, 'candidates_token_count', 0) or 0,
                "cached_tokens": getattr(last_usage_metadata, 'cached_content_token_count', 0) or 0,
            }

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            is_final=is_final,
            thinking=thinking,
            usage=usage
        )

    def _add_tool_results_to_messages(self, messages: List[types.Content], response: 'LLMResponse', tool_results: List[ToolResult]) -> List[types.Content]:
        """
        Add tool results to messages for the next Gemini API call.

        Now uses the adapter for centralized format handling.
        """
        from backend.llm_adapters.canonical import CanonicalToolCall as CanonicalTC

        # Convert LLMResponse to CanonicalResponse for adapter
        canonical_response = CanonicalResponse(
            text=response.text,
            tool_calls=[
                CanonicalTC(id=tc.id, name=tc.name, arguments=tc.arguments)
                for tc in response.tool_calls
            ],
            thinking=response.thinking,
            is_final=response.is_final
        )

        # Convert ToolResult to CanonicalToolResult for adapter
        canonical_results = [
            CanonicalToolResult(
                tool_call_id=tr.tool_call_id,
                name=tr.name,
                result=tr.result,
                is_error=tr.is_error
            )
            for tr in tool_results
        ]

        # Use adapter to add tool results (handles Gemini-specific format)
        return self.adapter.add_tool_results(messages, canonical_response, canonical_results)

    # =========================================================================
    # SECTION 7: UTILITIES & HELPERS
    # =========================================================================
    # _needs_web_search() is inherited from BaseLLMClient (Gemini uses it for two-phase search)

    def _gemini_do_google_search(self, query: str) -> str:
        """
        Perform a web search using Gemini's native Google Search grounding.
        This is a separate API call without function tools.

        Args:
            query: The search query

        Returns:
            Search results as formatted text
        """
        try:
            log(f"🌐 [PHASE 1] Google Search START - Query: {query[:50]}...")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=f"Search the web and provide comprehensive information about: {query}",
                config=self._gemini_build_search_config()
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

            log(f"🌐 [PHASE 1] Google Search DONE - {len(result_text)} chars, {len(sources)} sources")
            return formatted_result

        except Exception as e:
            log(f"🌐 [PHASE 1] Google Search FAILED - {e}")
            return f"[Web search failed: {str(e)}]"

    def _build_content_with_images(self, text: str, images: Optional[List[ImageData]] = None) -> Union[str, List[Any]]:
        """
        Build message content with optional images for Gemini API.

        Args:
            text: The text message
            images: Optional list of images

        Returns:
            String (text only) or list of content parts (with images)
        """
        if not images:
            return text

        parts = []

        # Add images first
        for img in images:
            prepared = prepare_image(img)
            if "url" in prepared:
                # Gemini supports URL-based images via from_uri
                parts.append(types.Part.from_uri(
                    file_uri=prepared["url"],
                    mime_type="image/jpeg"  # Default, will be auto-detected
                ))
            else:
                # Base64 encoded image - convert to bytes for Gemini
                image_bytes = base64.b64decode(prepared["data"])
                parts.append(types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=prepared["mime_type"]
                ))

        # Add text last
        parts.append(types.Part.from_text(text=text))

        return parts
