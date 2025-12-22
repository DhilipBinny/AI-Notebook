"""
Base LLM Client - Abstract interface for LLM providers

All LLM clients (Gemini, OpenAI, etc.) must implement this interface.
Supports text and image inputs for multimodal AI interactions.

This module provides:
1. BaseLLMClient - Abstract base class with common functionality
2. Unified AI Cell tool execution loop with cancellation support
3. Standardized response types for tool calls
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Callable
from dataclasses import dataclass, field
import base64
import json
from pathlib import Path

from backend.utils.util_func import log
from backend.prompts import CHAT_PANEL_SYSTEM_PROMPT, AI_CELL_SYSTEM_PROMPT


# Type alias for image data
# Images can be passed as:
# - {"data": "base64_string", "mime_type": "image/png"}
# - {"url": "https://..."} (for URL-based images)
# - {"path": "/workspace/image.png"} (for local files - will be converted to base64)
ImageData = Dict[str, str]


# =============================================================================
# TOOL EXECUTION CONFIGURATION
# =============================================================================
# Import from config (supports environment variable override)
from backend.config import MAX_TOOL_ITERATIONS


# =============================================================================
# WEB SEARCH CONFIGURATION (Weighted Scoring System)
# =============================================================================
# Uses weighted scoring instead of binary keyword matching.
# This handles nuances like "Write code for stock prices" correctly.
#
# Scoring:
#   - Explicit commands (google, search for): +100 (almost always search)
#   - Dynamic/time-sensitive (latest, weather, stock): +15
#   - Informational/docs (who is, what is, docs): +5
#   - Local context (my code, this cell, fix this): -20
#   - Coding intent (write a function, import, def): -10
#
# Threshold: Score >= 10 triggers search
#
# Examples:
#   - "weather in Tokyo" (+15) -> SEARCH
#   - "write code for stock price" (+15 - 10) = 5 -> NO SEARCH (correct!)
#   - "google how to fix my code" (+100 - 20) = 80 -> SEARCH (explicit override)
#   - "who is ceo" (+5) -> NO SEARCH (LLM knows general knowledge)
#   - "who is ceo now" (+5 + 15) = 20 -> SEARCH

import re

# Score threshold for triggering web search
WEB_SEARCH_SCORE_THRESHOLD = 10

# 1. EXPLICIT COMMANDS (Score: +100)
# If these exist, we almost certainly want to search.
REGEX_EXPLICIT_SEARCH = re.compile(
    r'\b(google|bing|search for|look up|lookup|search the web|web search)\b',
    re.IGNORECASE
)

# 2. DYNAMIC/TIME-SENSITIVE (Score: +15)
# Topics that LLMs (trained on old data) typically fail at.
REGEX_DYNAMIC_DATA = re.compile(
    r'\b(latest|current|today|now|news|weather|stock|price|release date|202[4-9]|exchange rate|score)\b',
    re.IGNORECASE
)

# 3. INFORMATIONAL/DOCS (Score: +5)
# Softer signals that suggest looking up facts.
REGEX_INFO_LOOKUP = re.compile(
    r'\b(who is|what is|when is|docs|documentation|api reference|tutorial|how to)\b',
    re.IGNORECASE
)

# 4. LOCAL CONTEXT (Score: -20)
# User refers to existing content in the notebook.
REGEX_LOCAL_CONTEXT = re.compile(
    r'\b(my code|my notebook|this cell|my dataframe|my data|my variable|this variable|'
    r'fix this|debug this|this function|this error|in the notebook|in this notebook|'
    r'in the cell|which cell|imported|defined|declared)\b',
    re.IGNORECASE
)

# 5. CODING INTENT (Score: -10)
# User wants you to WRITE code, not READ about it.
REGEX_CODING_INTENT = re.compile(
    r'\b(def |class |import |return |print\(|write a function|write a script|'
    r'create a function|create a script|implement|write code|generate code)\b',
    re.IGNORECASE
)

# Determine MIME type from extension
MIME_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp'
}

class CancelledException(Exception):
    """Raised when an operation is cancelled by user request."""
    pass


@dataclass
class ToolCall:
    """Standardized tool call representation across providers."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    """Standardized tool result representation."""
    tool_call_id: str
    name: str
    result: str  # JSON string
    is_error: bool = False


@dataclass
class LLMResponse:
    """Standardized LLM response across providers."""
    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    is_final: bool = True  # True if no more tool calls needed
    thinking: str = ""  # LLM's thinking/reasoning process (if enabled)
    # Raw thinking blocks for providers that require them in conversation history
    # (e.g., Anthropic extended thinking needs signature field preserved)
    raw_thinking_blocks: List[Any] = field(default_factory=list)


@dataclass
class ToolStep:
    """A step in the tool execution process (for UI display)."""
    type: str  # "tool_call" or "tool_result"
    name: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"type": self.type, "name": self.name, "content": self.content}


def encode_image_from_path(file_path: str) -> Dict[str, str]:
    """
    Read and base64 encode an image file.

    Args:
        file_path: Path to the image file

    Returns:
        Dict with "data" (base64 string) and "mime_type"
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {file_path}")


    mime_type = MIME_TYPES.get(path.suffix.lower(), 'image/png')

    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('utf-8')

    return {"data": data, "mime_type": mime_type}


def encode_image_from_bytes(image_bytes: bytes, mime_type: str = "image/png") -> Dict[str, str]:
    """
    Base64 encode image bytes.

    Args:
        image_bytes: Raw image bytes
        mime_type: MIME type of the image

    Returns:
        Dict with "data" (base64 string) and "mime_type"
    """
    data = base64.b64encode(image_bytes).decode('utf-8')
    return {"data": data, "mime_type": mime_type}


def prepare_image(image: Dict[str, str]) -> Dict[str, str]:
    """
    Prepare an image for sending to LLM.
    Handles path-based images by converting to base64.

    Args:
        image: Image dict with one of:
               - {"data": "base64...", "mime_type": "image/png"}
               - {"path": "/path/to/image.png"}
               - {"url": "https://..."}

    Returns:
        Normalized image dict with "data" and "mime_type" or "url"
    """
    if "path" in image:
        return encode_image_from_path(image["path"])
    elif "data" in image:
        # Already base64 encoded
        return {
            "data": image["data"],
            "mime_type": image.get("mime_type", "image/png")
        }
    elif "url" in image:
        # URL-based image
        return {"url": image["url"]}
    else:
        raise ValueError("Image must have 'data', 'path', or 'url' key")


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients with unified tool execution."""

    # System prompts imported from backend.prompts module
    SYSTEM_PROMPT = CHAT_PANEL_SYSTEM_PROMPT
    AI_CELL_SYSTEM_PROMPT = AI_CELL_SYSTEM_PROMPT

    def __init__(self):
        """Initialize base client with cancellation support."""
        self._cancel_requested = False
        self._on_progress: Optional[Callable[[str, Any], None]] = None
        self.enable_web_search = True  # Default: web search enabled

    # =========================================================================
    # Web Search Detection (shared implementation)
    # =========================================================================

    def _needs_web_search(self, message: str, user_message_only: str = None) -> bool:
        """
        Determine if the message needs web search using weighted scoring.

        Uses a scoring system instead of binary keyword matching:
        - Explicit commands (google, search for): +100
        - Dynamic/time-sensitive (latest, weather, stock): +15
        - Informational/docs (who is, what is, docs): +5
        - Local context (my code, this cell, fix this): -20
        - Coding intent (write a function, import, def): -10

        Threshold: Score >= 10 triggers search

        Args:
            message: The full message (used for search query if triggered)
            user_message_only: Optional - just the user's question (used for scoring)
                               If not provided, uses the full message.
                               This avoids false triggers from notebook context.

        Returns:
            True if web search should be triggered, False otherwise
        """
        if not self.enable_web_search:
            log("🔍 Web search: DISABLED")
            return False

        # Use user_message_only for scoring if provided
        # This prevents false triggers from notebook context
        text = (user_message_only if user_message_only else message).strip()

        score = 0
        score_breakdown = []

        # --- ADD POINTS ---
        if REGEX_EXPLICIT_SEARCH.search(text):
            score += 100
            score_breakdown.append("+100 explicit")

        if REGEX_DYNAMIC_DATA.search(text):
            score += 15
            score_breakdown.append("+15 dynamic")

        if REGEX_INFO_LOOKUP.search(text):
            score += 5
            score_breakdown.append("+5 info")

        # --- SUBTRACT POINTS ---
        if REGEX_LOCAL_CONTEXT.search(text):
            score -= 20
            score_breakdown.append("-20 local")

        if REGEX_CODING_INTENT.search(text):
            score -= 10
            score_breakdown.append("-10 coding")

        # --- DECISION ---
        weighted_result = score >= WEB_SEARCH_SCORE_THRESHOLD
        breakdown_str = " | ".join(score_breakdown) if score_breakdown else "no matches"

        # Log weighted scoring result
        if weighted_result:
            log(f"🔍 Weighted: TRIGGERED (score={score} [{breakdown_str}])")
        else:
            log(f"🔍 Weighted: NOT NEEDED (score={score} [{breakdown_str}])")

        # Also call LLM classifier for comparison (for tuning purposes)
        llm_result = self._needs_web_search_llm(text)

        # Log comparison
        agreement = "✅ AGREE" if weighted_result == llm_result else "❌ DISAGREE"
        log(f"🔍 Comparison: Weighted={weighted_result}, LLM={llm_result} [{agreement}]")

        # Use weighted scoring result for actual decision (faster, no extra API call cost)
        return weighted_result

    def _needs_web_search_llm(self, user_query: str) -> bool:
        """
        Uses a fast LLM call to decide if external search is truly needed.

        This is an alternative to the weighted scoring approach that uses
        AI to make the decision. More accurate but adds latency.

        Args:
            user_query: The user's question/request

        Returns:
            True if web search should be triggered, False otherwise
        """
        if not self.enable_web_search:
            log("🔍 LLM Web search check: DISABLED")
            return False

        prompt = f"""You are a Router for a Jupyter Notebook AI Assistant.
                Your specific job is to decide: Does this user query require LIVE EXTERNAL WEB SEARCH?

                CONTEXT:
                - The Assistant has direct access to the notebook code, cells, and runtime variables.
                - It can inspect dataframes, list variables, and read errors internally.
                - It can write and debug code using its own internal knowledge.

                RULES - RETURN "NO" (Do NOT Search) for:
                - Questions about "my code", "this cell", "my data", "variable x".
                - Requests to write, fix, or debug Python code (unless asking for external docs).
                - Questions about the notebook structure ("how many cells?").
                - "What is the value of...", "Show me the dataframe...".

                RULES - RETURN "YES" (MUST Search) for:
                - Explicit requests ("google this", "search for").
                - Real-time data ("weather", "stock price", "current date").
                - Up-to-date API documentation or library reference ("latest pandas docs").
                - Facts outside the notebook ("who is the CEO of...", "release date of...").

                User Query: "{user_query}"

                Reply with exactly one word: YES or NO."""

        try:
            # Use simple_completion for a fast, low-token response
            result = self.simple_completion(prompt, max_tokens=5)
            result = result.strip().upper()

            should_search = "YES" in result
            log(f"🔍 LLM Web search check: {'TRIGGERED' if should_search else 'NOT NEEDED'} (LLM said: {result})")
            return should_search

        except Exception as e:
            log(f"🔍 LLM Web search check: ERROR ({e}), returning False")
            # Return False on error (don't trigger search if LLM check fails)
            return False

    def cancel(self) -> None:
        """Request cancellation of the current operation."""
        log("🛑 Cancellation requested")
        self._cancel_requested = True

    def reset_cancellation(self) -> None:
        """Reset the cancellation flag (called at start of operations)."""
        self._cancel_requested = False

    def _check_cancelled(self) -> None:
        """Check if cancellation was requested and raise if so."""
        if self._cancel_requested:
            self._cancel_requested = False
            raise CancelledException("Operation cancelled by user")

    def set_progress_callback(self, callback: Callable[[str, Any], None]) -> None:
        """
        Set a callback for progress updates during tool execution.

        Args:
            callback: Function(event_type, data) called during execution
                     event_type: "iteration_start", "tool_call", "tool_result", "iteration_end"
        """
        self._on_progress = callback

    def _emit_progress(self, event_type: str, data: Any = None) -> None:
        """Emit a progress event if callback is set."""
        if self._on_progress:
            try:
                self._on_progress(event_type, data)
            except Exception as e:
                log(f"Progress callback error: {e}")

    # =========================================================================
    # Token Counting (override in subclass for provider-specific counting)
    # =========================================================================

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text. Override for provider-specific counting.

        Default implementation uses tiktoken with cl100k_base encoding.
        Subclasses can override to use native APIs:
        - Anthropic: client.messages.count_tokens()
        - Gemini: client.models.count_tokens()

        Args:
            text: The text to count tokens for

        Returns:
            Token count, or 0 if counting fails
        """
        try:
            import tiktoken
            model_name = getattr(self, 'model_name', None)
            if model_name:
                # Extract model from provider format (e.g., "openai/gpt-4o" -> "gpt-4o")
                if "/" in model_name:
                    model_name = model_name.split("/")[-1]
                try:
                    encoding = tiktoken.encoding_for_model(model_name)
                except KeyError:
                    encoding = tiktoken.get_encoding("cl100k_base")
            else:
                encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            return 0

    # =========================================================================
    # Abstract methods that providers MUST implement
    # =========================================================================

    @abstractmethod
    def chat_panel_send(
        self,
        notebook_context: str,
        user_prompt: str,
        images: Optional[List[ImageData]] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Send a message to the LLM and get a response.

        Args:
            notebook_context: Formatted notebook context (cacheable - Layer 2)
            user_prompt: User's question/prompt (never cached - Layer 3)
            images: Optional list of images for visual analysis

        The separation of notebook_context and user_prompt allows:
        - Anthropic: Apply cache_control to notebook_context only
        - Gemini: Automatic caching handles both
        - Other providers: Combine as needed

        Returns:
            str: Final response text (if auto_function_calling=True or no tools needed)
            dict: {"pending_tool_calls": [...], "response_text": "..."} (if manual mode with tools)
        """
        pass

    @abstractmethod
    def execute_approved_tools(self, approved_tool_calls: List[Dict[str, Any]]) -> str:
        """
        Execute approved tool calls and get the final response.

        Args:
            approved_tool_calls: List of approved tools to execute
                                [{"id": "...", "name": "...", "arguments": {...}}, ...]

        Returns:
            The final response text after tool execution
        """
        pass

    @abstractmethod
    def clear_history(self) -> None:
        """Clear the conversation history"""
        pass

    @abstractmethod
    def get_history(self) -> List[Dict[str, Any]]:
        """Get the current conversation history"""
        pass

    @abstractmethod
    def set_history(self, history_list: List[Dict[str, Any]]) -> None:
        """
        Set the conversation history.

        Args:
            history_list: List of history entries in provider-neutral format
                         [{"role": "user"/"assistant", "content": "..."}]
        """
        pass

    @property
    def provider_name(self) -> str:
        """Return the name of the LLM provider from adapter."""
        # Delegate to adapter - single source of truth for provider name
        if hasattr(self, 'adapter') and self.adapter:
            return self.adapter.provider_name
        # Fallback: derive from class name (e.g., GeminiClient -> Gemini)
        return self.__class__.__name__.replace("Client", "")

    @abstractmethod
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
        pass

    @abstractmethod
    def ai_cell_simple(
        self,
        notebook_context: str,
        user_prompt: str,
        images: Optional[List[ImageData]] = None
    ) -> str:
        """
        AI Cell completion - with web search but no notebook tools.
        Used for inline Q&A in AI cells.

        Args:
            notebook_context: Formatted notebook context (cacheable - Layer 2)
            user_prompt: User's question/prompt (never cached - Layer 3)
            images: Optional list of images to include in the prompt.

        Returns:
            The response text from the LLM (may include web search results)
        """
        pass

    # =========================================================================
    # Abstract methods for unified tool execution (providers implement these)
    # =========================================================================

    @abstractmethod
    def _call_llm_for_ai_cell(self, messages: Any, tools: List[Any]) -> LLMResponse:
        """
        Make an LLM API call for AI Cell tool execution.

        This is the provider-specific API call. Each provider must implement
        this to translate between their API format and the standardized LLMResponse.

        Args:
            messages: Provider-specific message format (built by _prepare_ai_cell_messages)
            tools: Provider-specific tool format (built by _get_ai_cell_tools)

        Returns:
            LLMResponse with text, tool_calls, and is_final flag
        """
        pass

    @abstractmethod
    def _prepare_ai_cell_messages(
        self,
        notebook_context: str,
        user_prompt: str,
        images: Optional[List[ImageData]] = None
    ) -> Any:
        """
        Prepare initial messages for AI Cell in provider-specific format.

        Args:
            notebook_context: Formatted notebook context (cacheable - Layer 2)
            user_prompt: User's question/prompt (never cached - Layer 3)
            images: Optional images

        Returns:
            Provider-specific message format
        """
        pass

    @abstractmethod
    def _add_tool_results_to_messages(self, messages: Any, response: 'LLMResponse', tool_results: List[ToolResult]) -> Any:
        """
        Add tool results to messages for the next LLM call.

        This is called after tools are executed. Providers should:
        1. Add the assistant's response with tool calls (if required by API)
        2. Add the tool results
        3. For providers with extended thinking, include thinking blocks

        Args:
            messages: Current messages in provider-specific format
            response: The LLM response (includes tool_calls, thinking, text)
            tool_results: List of tool results to add

        Returns:
            Updated messages with tool results
        """
        pass

    @abstractmethod
    def _get_ai_cell_tools(self) -> List[Any]:
        """
        Get AI Cell tools in provider-specific format.

        Returns:
            List of tool definitions in provider format
        """
        pass

    @abstractmethod
    def _get_ai_cell_tool_map(self) -> Dict[str, Callable]:
        """
        Get mapping of tool names to callable functions for AI Cell.

        Returns:
            Dict mapping tool name to function
        """
        pass

    def _get_web_search_tool(self) -> Optional[Any]:
        """
        Get web search tool in provider-specific format.
        Override in subclasses to provide web search capability.

        Returns:
            Web search tool definition, or None if not supported
        """
        return None

    # =========================================================================
    # Abstract method for Chat Panel API calls
    # =========================================================================

    def _call_chat_api(self, messages: Any, tools: Any) -> Any:
        """
        Make a Chat Panel API call to the LLM provider.

        This must be implemented by each provider. Returns the raw API response
        which will be parsed using self.adapter.from_response().

        Args:
            messages: Provider-specific message format
            tools: Provider-specific tool definitions

        Returns:
            Raw API response object
        """
        raise NotImplementedError("Subclasses must implement _call_chat_api")

    def _log_cache_usage(self, response: Any) -> None:
        """
        Log cache usage from API response via adapter.
        Adapter handles provider-specific cache stats extraction.
        """
        if hasattr(self, 'adapter') and self.adapter:
            # Pass model_name for providers that need it (Gemini, OpenAI)
            model = getattr(self, 'model_name', '')
            if hasattr(self.adapter, 'log_cache_usage'):
                try:
                    # Some adapters need model_name, some don't
                    import inspect
                    sig = inspect.signature(self.adapter.log_cache_usage)
                    if 'model_name' in sig.parameters:
                        self.adapter.log_cache_usage(response, model)
                    else:
                        self.adapter.log_cache_usage(response)
                except Exception:
                    pass

    # =========================================================================
    # Consolidated Chat Panel Tool Execution (shared implementation)
    # =========================================================================
    # These methods provide unified tool execution for Anthropic, OpenAI, Ollama.
    # Gemini uses chat sessions differently and may override these.

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any], tool_map: Dict[str, Callable]) -> str:
        """
        Execute a single tool and return the result as JSON string.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            tool_map: Mapping of tool names to callable functions

        Returns:
            JSON string result
        """
        log(f"{self.provider_name} executing tool: {tool_name} with args: {arguments}")

        if tool_name not in tool_map:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            result = tool_map[tool_name](**arguments)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _chat_auto_execute_tools(
        self,
        messages: Any,
        tools: Any,
        tool_map: Dict[str, Callable]
    ) -> str:
        """
        Consolidated auto tool execution loop for chat panel.

        Executes tools automatically until we get a final response.
        Uses adapter for response parsing and tool result formatting.

        Args:
            messages: Provider-specific message format
            tools: Provider-specific tool definitions
            tool_map: Mapping of tool names to callable functions

        Returns:
            Final response text
        """
        from backend.llm_adapters.canonical import CanonicalToolResult

        iteration = 0
        self._emit_progress("thinking", {"message": "Processing your request..."})

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1
            log(f"🔄 {self.provider_name} iteration {iteration}/{MAX_TOOL_ITERATIONS}")

            self._emit_progress("thinking", {"message": "Waiting for AI response..."})

            # Provider-specific API call
            raw_response = self._call_chat_api(messages, tools)

            # Log cache usage if applicable
            self._log_cache_usage(raw_response)

            # Parse response using adapter
            response = self.adapter.from_response(raw_response)

            if response.tool_calls:
                # Build tool results
                tool_results = []
                for tc in response.tool_calls:
                    log(f"🔧 {self.provider_name} calling tool: {tc.name}")
                    self._emit_progress("tool_call", {"name": tc.name, "args": tc.arguments})
                    result_str = self._execute_tool(tc.name, tc.arguments, tool_map)
                    self._emit_progress("tool_result", {"name": tc.name, "result": result_str[:200] if result_str else ""})
                    tool_results.append(CanonicalToolResult(
                        tool_call_id=tc.id,
                        name=tc.name,
                        result=result_str,
                        is_error="error" in result_str.lower()
                    ))

                # Add tool results to messages using adapter
                messages = self.adapter.add_tool_results(messages, response, tool_results)
            else:
                # Final response
                final_response = response.text or ""
                self.history.append({
                    "role": "assistant",
                    "content": final_response
                })
                log(f"✅ {self.provider_name} response received - {len(final_response)} chars")
                return final_response

        log(f"❌ {self.provider_name} max iterations reached")
        return "Error: Maximum tool calling iterations reached"

    def _chat_get_pending_tools(
        self,
        messages: Any,
        tools: Any
    ) -> Union[str, Dict[str, Any]]:
        """
        Consolidated pending tools getter for chat panel (manual mode).

        Gets pending tool calls without executing them.
        Uses adapter for response parsing.

        Args:
            messages: Provider-specific message format
            tools: Provider-specific tool definitions

        Returns:
            str: Final response text if no tools needed
            dict: {"pending_tool_calls": [...], "response_text": "..."} if tools pending
        """
        import copy

        self._emit_progress("thinking", {"message": "Processing your request..."})
        self._emit_progress("thinking", {"message": "Waiting for AI response..."})

        # Provider-specific API call
        raw_response = self._call_chat_api(messages, tools)

        self._emit_progress("thinking", {"message": "Processing response..."})

        # Log cache usage if applicable
        self._log_cache_usage(raw_response)

        # Parse response using adapter
        response = self.adapter.from_response(raw_response)

        if response.tool_calls:
            # Store state for later execution
            self._pending_messages = copy.deepcopy(messages)
            self._pending_response = response  # Store parsed response for later

            # Build pending tools list for UI
            pending_tools = []
            for tc in response.tool_calls:
                pending_tools.append({
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments
                })

            # Add assistant message with tool calls to pending messages
            # (Using adapter to build the message)
            self._pending_messages = self.adapter.add_tool_results(
                self._pending_messages,
                response,
                []  # No results yet - just adding assistant message
            )
            # Remove the empty user message that add_tool_results adds
            if self._pending_messages and self._pending_messages[-1].get("role") == "user":
                self._pending_messages.pop()

            tools_names = [t["name"] for t in pending_tools]
            log(f"🔧 {self.provider_name} pending tools: {', '.join(tools_names)}")

            return {
                "pending_tool_calls": pending_tools,
                "response_text": response.text or ""
            }
        else:
            # No tools needed
            final_response = response.text or ""
            self.history.append({
                "role": "assistant",
                "content": final_response
            })
            log(f"✅ {self.provider_name} response (no tools) - {len(final_response)} chars")
            return final_response

    def _chat_execute_approved_tools(
        self,
        approved_tool_calls: List[Dict[str, Any]],
        tool_map: Dict[str, Callable],
        tools: Any
    ) -> Union[str, Dict[str, Any]]:
        """
        Consolidated approved tools executor for chat panel.

        Execute approved tool calls and get the response.
        In manual mode, returns pending tools if more are needed.

        Args:
            approved_tool_calls: List of approved tools to execute
            tool_map: Mapping of tool names to callable functions
            tools: Provider-specific tool definitions (for subsequent calls)

        Returns:
            str: Final response text if no more tools needed
            dict: {"pending_tool_calls": [...], "response_text": "..."} if more tools needed
        """
        import copy
        from backend.llm_adapters.canonical import CanonicalToolResult

        if not hasattr(self, '_pending_messages') or not self._pending_messages:
            return "Error: No pending tool calls to execute"

        messages = copy.deepcopy(self._pending_messages)

        # Execute approved tools and collect results
        tool_results = []
        for tool_call in approved_tool_calls:
            tool_id = tool_call.get("id", "")
            tool_name = tool_call["name"]
            tool_args = tool_call.get("arguments", {})

            result_str = self._execute_tool(tool_name, tool_args, tool_map)
            tool_results.append(CanonicalToolResult(
                tool_call_id=tool_id,
                name=tool_name,
                result=result_str,
                is_error="error" in result_str.lower()
            ))

        # Add tool results to messages
        # We need the response to include tool calls - use stored pending response
        if hasattr(self, '_pending_response') and self._pending_response:
            messages = self.adapter.add_tool_results(messages, self._pending_response, tool_results)
        else:
            # Fallback: build a minimal response with just the tool call info
            from backend.llm_adapters.canonical import CanonicalToolCall, CanonicalResponse
            minimal_response = CanonicalResponse(
                tool_calls=[
                    CanonicalToolCall(id=tc["id"], name=tc["name"], arguments=tc.get("arguments", {}))
                    for tc in approved_tool_calls
                ]
            )
            messages = self.adapter.add_tool_results(messages, minimal_response, tool_results)

        # Check if auto mode or manual mode
        if self.auto_function_calling:
            # Auto mode: loop until final response
            final_response = self._chat_auto_execute_tools(messages, tools, tool_map)
            self._pending_messages = []
            self._pending_response = None
            return final_response
        else:
            # Manual mode: make ONE call and check if more tools are needed
            raw_response = self._call_chat_api(messages, tools)
            self._log_cache_usage(raw_response)
            response = self.adapter.from_response(raw_response)

            if response.tool_calls:
                # Model wants more tools - return them for approval
                import copy
                self._pending_messages = copy.deepcopy(messages)
                self._pending_response = response

                pending_tools = []
                for tc in response.tool_calls:
                    pending_tools.append({
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments
                    })

                tools_names = [t["name"] for t in pending_tools]
                log(f"🔧 {self.provider_name} wants more tools (manual mode): {', '.join(tools_names)}")

                return {
                    "pending_tool_calls": pending_tools,
                    "response_text": response.text or ""
                }
            else:
                # Final response - no more tools
                final_response = response.text or ""

                self.history.append({
                    "role": "assistant",
                    "content": final_response
                })

                # Clear pending state
                self._pending_messages = []
                self._pending_response = None

                log(f"✅ {self.provider_name} execute_approved_tools final response - {len(final_response)} chars")
                return final_response

    def _append_nudge_to_messages(self, messages: Any, text: str) -> None:
        """
        Appends a user message to nudge the LLM after an empty response.

        This is critical for retries - sending the exact same messages will likely
        produce the exact same (empty) response. Adding a nudge changes the context,
        forcing the LLM to generate a new path.

        Handles different message formats:
        - Gemini: google.genai.types.Content objects with 'parts'
        - Anthropic: Dict with content as list of blocks [{"type": "text", "text": "..."}]
        - OpenAI/Ollama: Dict with content as string

        Args:
            messages: The message list (mutated in place)
            text: The nudge text to append
        """
        if not messages:
            return

        # Check if it's Gemini format (Content objects with 'parts' attribute)
        if hasattr(messages[0], 'parts'):
            try:
                from google.genai import types
                messages.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=text)]
                ))
                log(f"📌 Appended nudge (Gemini format): {text[:50]}...")
            except ImportError:
                log("⚠️ Could not import google.genai for nudge")

        # Dict format - need to detect Anthropic vs OpenAI/Ollama
        elif isinstance(messages[0], dict):
            # Check if this looks like Anthropic format (content is a list of blocks)
            # by examining the most recent user message's content
            is_anthropic_format = False
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    content = msg.get("content")
                    # Anthropic uses list of dicts with "type" key
                    if isinstance(content, list) and len(content) > 0:
                        if isinstance(content[0], dict) and "type" in content[0]:
                            is_anthropic_format = True
                    break

            if is_anthropic_format:
                # Anthropic format: content is list of blocks
                messages.append({
                    "role": "user",
                    "content": [{"type": "text", "text": text}]
                })
                log(f"📌 Appended nudge (Anthropic format): {text[:50]}...")
            else:
                # OpenAI/Ollama format: content is string
                messages.append({"role": "user", "content": text})
                log(f"📌 Appended nudge (OpenAI/Ollama format): {text[:50]}...")

        else:
            log(f"⚠️ Unknown message format, cannot append nudge: {type(messages[0])}")

    # =========================================================================
    # Unified AI Cell tool execution loop (shared implementation)
    # =========================================================================

    def ai_cell_execute(
        self,
        notebook_context: str,
        user_prompt: str,
        images: Optional[List[ImageData]] = None,
        max_iterations: int = None
    ) -> Dict[str, Any]:
        """
        AI Cell completion with tool calling support.

        Uses a unified tool execution loop that works consistently across all providers.
        Supports cancellation between iterations.

        Args:
            notebook_context: Formatted notebook context (cacheable - Layer 2)
            user_prompt: User's question/prompt (never cached - Layer 3)
            images: Optional list of images to include in the prompt
            max_iterations: Maximum number of tool-calling iterations (default: MAX_TOOL_ITERATIONS)

        Returns:
            Dict with:
            - "response": The final response text from the LLM
            - "steps": List of tool call steps for UI display
            - "cancelled": True if operation was cancelled (optional)
        """
        self.reset_cancellation()
        steps: List[ToolStep] = []

        try:
            # Use default if not specified
            if max_iterations is None:
                max_iterations = MAX_TOOL_ITERATIONS

            # Log AI Cell request with token count using self.count_tokens()
            from backend.utils.util_func import log_ai_cell
            full_text = f"{notebook_context}\n\n{user_prompt}" if notebook_context else user_prompt
            input_tokens = self.count_tokens(full_text)

            mode = "auto" if self.auto_function_calling else "manual"
            max_tok = getattr(self, 'max_tokens', None)
            log_ai_cell(
                provider=self.provider_name,
                model=self.model_name,
                mode=mode,
                context_chars=len(notebook_context) if notebook_context else 0,
                prompt_chars=len(user_prompt) if user_prompt else 0,
                images=len(images) if images else 0,
                web_search=getattr(self, 'enable_web_search', False),
                max_tokens=max_tok,
                input_tokens=input_tokens
            )

            # Get provider-specific tools and tool map
            tools = self._get_ai_cell_tools()
            tool_map = self._get_ai_cell_tool_map()

            # Check if web search is needed based on user prompt
            # _needs_web_search now logs both weighted scoring AND LLM classifier comparison
            if self._needs_web_search(user_prompt, user_prompt):
                # Add web search tool - provider-specific implementation
                web_search_tool = self._get_web_search_tool()
                if web_search_tool:
                    tools = tools + [web_search_tool]
                    log("🌐 Web search tool added to AI Cell request")

            log(f"🔧 Available tools: {list(tool_map.keys())}")

            # Prepare initial messages
            messages = self._prepare_ai_cell_messages(notebook_context, user_prompt, images)

            # Accumulate thinking across all iterations
            accumulated_thinking = ""
            empty_response_count = 0  # Track consecutive empty responses
            MAX_EMPTY_RETRIES = 2  # Allow up to 2 retries on empty response

            for iteration in range(max_iterations):
                # ✅ CANCELLATION CHECK - before each iteration
                self._check_cancelled()

                log(f"🔄 AI Cell iteration {iteration + 1}/{max_iterations}")
                self._emit_progress("iteration_start", {"iteration": iteration + 1, "max": max_iterations})

                # Call LLM (provider-specific)
                response = self._call_llm_for_ai_cell(messages, tools)

                # --- Guard against stalled loops (empty responses) ---
                if not response.text and not response.tool_calls and not response.thinking:
                    empty_response_count += 1
                    log(f"⚠️ LLM returned empty response ({empty_response_count}/{MAX_EMPTY_RETRIES})")

                    if empty_response_count >= MAX_EMPTY_RETRIES:
                        # Give up after max retries
                        log("❌ Max empty response retries reached. Giving up.")
                        return {
                            "response": "I couldn't generate a response. The model returned empty content (possibly due to content filtering). Please try rephrasing your question.",
                            "steps": [s.to_dict() for s in steps],
                            "error": "empty_response"
                        }

                    # ✅ THE FIX: Nudge the LLM to force a different response path
                    # Without this, retrying the same request would likely produce the same empty result
                    nudge_text = (
                        "Your previous response was empty or filtered. "
                        "Please provide a valid response with either text content, "
                        "a tool call, or your reasoning. Try a different approach if needed."
                    )
                    self._append_nudge_to_messages(messages, nudge_text)

                    log("🔄 Retrying with nudge injection...")
                    self._emit_progress("retry", {"reason": "empty_response", "attempt": empty_response_count})
                    continue  # Next iteration will use the nudged messages

                # Reset empty count on successful response
                empty_response_count = 0

                # Emit thinking if present and accumulate it
                if response.thinking:
                    log(f"💭 AI Cell thinking: {len(response.thinking)} chars")
                    self._emit_progress("thinking", {"content": response.thinking, "iteration": iteration + 1})
                    accumulated_thinking += response.thinking + "\n\n"

                # Check if we have a final response (no more tool calls)
                if response.is_final or not response.tool_calls:
                    log(f"🤖 AI Cell response: {len(response.text)} chars, {len(steps)} steps, thinking: {len(accumulated_thinking)} chars")
                    self._emit_progress("iteration_end", {"final": True})
                    return {
                        "response": response.text or "I've analyzed your notebook. Please let me know if you need more specific information.",
                        "steps": [s.to_dict() for s in steps],
                        "thinking": accumulated_thinking.strip() if accumulated_thinking else ""
                    }

                # Execute tools
                tool_results: List[ToolResult] = []

                for tool_call in response.tool_calls:
                    # ✅ CANCELLATION CHECK - before each tool
                    self._check_cancelled()

                    tool_name = tool_call.name
                    tool_args = tool_call.arguments

                    log(f"🔧 AI Cell executing: {tool_name}({json.dumps(tool_args)})")
                    self._emit_progress("tool_call", {"name": tool_name, "args": tool_args})

                    # Record tool call step
                    steps.append(ToolStep(
                        type="tool_call",
                        name=tool_name,
                        content=json.dumps(tool_args, indent=2)
                    ))

                    # Execute the tool
                    if tool_name in tool_map:
                        try:
                            result = tool_map[tool_name](**tool_args)
                            result_str = json.dumps(result)
                            is_error = False
                        except Exception as e:
                            log(f"🔧 Tool {tool_name} error: {e}")
                            result_str = json.dumps({"error": str(e)})
                            is_error = True
                    else:
                        result_str = json.dumps({"error": f"Unknown tool: {tool_name}"})
                        is_error = True

                    # Record tool result step (truncate for display)
                    result_preview = result_str[:1000] + "..." if len(result_str) > 1000 else result_str
                    steps.append(ToolStep(
                        type="tool_result",
                        name=tool_name,
                        content=result_preview
                    ))

                    self._emit_progress("tool_result", {"name": tool_name, "result": result_preview})

                    tool_results.append(ToolResult(
                        tool_call_id=tool_call.id,
                        name=tool_name,
                        result=result_str,
                        is_error=is_error
                    ))

                # Add tool results to messages for next iteration
                # Pass response so providers can include thinking blocks (required for Anthropic extended thinking)
                messages = self._add_tool_results_to_messages(messages, response, tool_results)
                self._emit_progress("iteration_end", {"final": False})

            # Max iterations reached
            log(f"🤖 AI Cell max iterations reached ({max_iterations})")
            return {
                "response": "I've analyzed your notebook but reached the maximum number of tool calls. Please ask a more specific question.",
                "steps": [s.to_dict() for s in steps]
            }

        except CancelledException:
            log(f"🛑 AI Cell cancelled after {len(steps)} steps")
            return {
                "response": "[Cancelled by user]",
                "steps": [s.to_dict() for s in steps],
                "cancelled": True
            }

        except Exception as e:
            log(f"🤖 AI Cell error: {e}")
            import traceback
            log(f"Traceback: {traceback.format_exc()}")
            raise
