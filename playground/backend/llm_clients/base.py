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
from collections import defaultdict
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

# Tool loop safety guards
MAX_TOOL_RESULT_CHARS = 10_000       # Max chars per individual tool result
MAX_TOTAL_TOOL_RESULTS = 30_000      # Max cumulative tool output per round
TOOL_LOOP_THRESHOLD = 3              # Skip if same tool+args called this many times


# =============================================================================
# WEB SEARCH CONFIGURATION
# =============================================================================
# Strategy per provider:
#   - Anthropic/OpenAI: Always include native web search tool. The model
#     decides when to call it. No pre-filtering needed.
#   - Gemini: Two-phase approach (separate search API call + inject results).
#     Uses weighted scoring to decide IF search is needed before making
#     the extra API call.
#   - Ollama: No web search (local models).
#
# Gemini Scoring (used only by Gemini's two-phase search):
#   - Explicit commands (google, search for): +100
#   - Dynamic/time-sensitive (latest, weather, stock): +15
#   - Informational/docs (who is, what is, docs): +5
#   - Local context (my code, this cell, fix this): -20
#   - Coding intent (write a function, import, def): -10
#   Threshold: Score >= 10 triggers search

import re

WEB_SEARCH_SCORE_THRESHOLD = 10

REGEX_EXPLICIT_SEARCH = re.compile(
    r'\b(google|bing|search for|look up|lookup|search the web|web search)\b',
    re.IGNORECASE
)

REGEX_DYNAMIC_DATA = re.compile(
    r'\b(latest|current|today|now|news|weather|stock price|release date|20\d{2}|exchange rate)\b',
    re.IGNORECASE
)

REGEX_INFO_LOOKUP = re.compile(
    r'\b(who is|what is|when is|when did|docs for|documentation for|api reference|official docs)\b',
    re.IGNORECASE
)

REGEX_LOCAL_CONTEXT = re.compile(
    r'\b(my code|my notebook|this cell|my dataframe|my data|my variable|this variable|'
    r'fix this|debug this|this function|this error|in the notebook|in this notebook|'
    r'in the cell|which cell|imported|defined|declared)\b',
    re.IGNORECASE
)

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
    # Usage statistics: input_tokens, output_tokens, cached_tokens
    usage: Optional[Dict[str, int]] = None


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
        self._last_usage: Optional[Dict[str, Any]] = None  # Usage stats from last call

    def close(self):
        """Close any underlying HTTP clients/connections. Override in subclasses."""
        if hasattr(self, 'client') and hasattr(self.client, 'close'):
            try:
                self.client.close()
            except Exception:
                pass

    # =========================================================================
    # Web Search Detection (shared implementation)
    # =========================================================================

    def _needs_web_search(self, user_message: str) -> bool:
        """
        Weighted scoring to decide if web search is needed.

        Used by Gemini's two-phase search (separate API call).
        Anthropic/OpenAI skip this — they always include web search as a
        tool and let the model decide whether to call it.

        Args:
            user_message: The user's question (not full context)

        Returns:
            True if web search should be triggered
        """
        if not self.enable_web_search:
            return False

        text = user_message.strip()
        score = 0
        parts = []

        if REGEX_EXPLICIT_SEARCH.search(text):
            score += 100
            parts.append("+100 explicit")
        if REGEX_DYNAMIC_DATA.search(text):
            score += 15
            parts.append("+15 dynamic")
        if REGEX_INFO_LOOKUP.search(text):
            score += 5
            parts.append("+5 info")
        if REGEX_LOCAL_CONTEXT.search(text):
            score -= 20
            parts.append("-20 local")
        if REGEX_CODING_INTENT.search(text):
            score -= 10
            parts.append("-10 coding")

        result = score >= WEB_SEARCH_SCORE_THRESHOLD
        breakdown = " | ".join(parts) if parts else "no matches"
        log(f"🔍 Web search scoring: {'TRIGGERED' if result else 'skip'} (score={score} [{breakdown}])")
        return result

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
            Token count (uses char/4 estimate as fallback if tiktoken fails)
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
            # Fallback: ~4 chars per token is a reasonable estimate
            # Returning 0 would hide context overflow issues
            return max(1, len(text) // 4)

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
    def _get_ai_cell_tools(self, allowed_tools: Optional[List[str]] = None) -> List[Any]:
        """
        Get AI Cell tools in provider-specific format.

        Args:
            allowed_tools: If provided, only include tools with these names.

        Returns:
            List of tool definitions in provider format
        """
        pass

    @abstractmethod
    def _get_ai_cell_tool_map(self, allowed_tools: Optional[List[str]] = None) -> Dict[str, Callable]:
        """
        Get mapping of tool names to callable functions for AI Cell.

        Args:
            allowed_tools: If provided, only include tools with these names.

        Returns:
            Dict mapping tool name to function
        """
        pass

    def _get_web_search_tool(self) -> Optional[Any]:
        """
        Get web search tool in provider-specific format via adapter.

        Default implementation delegates to self.adapter.get_web_search_tool().
        Override in subclasses only if special args are needed.

        Returns:
            Web search tool definition, or None if not enabled/supported
        """
        if not getattr(self, 'enable_web_search', False):
            return None
        if hasattr(self, 'adapter') and hasattr(self.adapter, 'get_web_search_tool'):
            return self.adapter.get_web_search_tool()
        return None

    # =========================================================================
    # Abstract method for Chat Panel API calls
    # =========================================================================

    @abstractmethod
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
        pass

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

        # Accumulate usage across iterations
        total_usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}

        # Tool loop detection: track calls by tool+args signature
        tool_call_counts: Dict[str, int] = defaultdict(int)

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

            # Accumulate usage from this iteration
            if response.usage:
                total_usage["input_tokens"] += response.usage.get("input_tokens", 0)
                total_usage["output_tokens"] += response.usage.get("output_tokens", 0)
                total_usage["cached_tokens"] += response.usage.get("cached_tokens", 0)

            if response.tool_calls:
                # Build tool results with safety guards
                tool_results = []
                total_result_chars = 0

                for tc in response.tool_calls:
                    # Loop detection: skip if same tool+args called too many times
                    call_key = f"{tc.name}:{json.dumps(tc.arguments, sort_keys=True)}"
                    tool_call_counts[call_key] += 1
                    if tool_call_counts[call_key] > TOOL_LOOP_THRESHOLD:
                        log(f"⚠️ Tool loop detected: {tc.name} called {tool_call_counts[call_key]} times with same args — skipping")
                        result_str = json.dumps({"error": f"Skipped: {tc.name} already called with these arguments {TOOL_LOOP_THRESHOLD} times. Try a different approach."})
                        self._emit_progress("tool_result", {"name": tc.name, "result": "Skipped (loop detected)"})
                        tool_results.append(CanonicalToolResult(
                            tool_call_id=tc.id, name=tc.name, result=result_str, is_error=True
                        ))
                        continue

                    log(f"🔧 {self.provider_name} calling tool: {tc.name}")
                    self._emit_progress("tool_call", {"name": tc.name, "args": tc.arguments})
                    result_str = self._execute_tool(tc.name, tc.arguments, tool_map)

                    # Truncate oversized individual results
                    if result_str and len(result_str) > MAX_TOOL_RESULT_CHARS:
                        result_str = result_str[:MAX_TOOL_RESULT_CHARS] + f"\n[Truncated — {len(result_str)} total chars]"

                    # Cap cumulative results
                    total_result_chars += len(result_str) if result_str else 0
                    if total_result_chars > MAX_TOTAL_TOOL_RESULTS:
                        result_str = json.dumps({"error": "Result omitted: total tool output limit reached for this round."})

                    self._emit_progress("tool_result", {"name": tc.name, "result": result_str[:200] if result_str else ""})
                    tool_results.append(CanonicalToolResult(
                        tool_call_id=tc.id,
                        name=tc.name,
                        result=result_str,
                        is_error="error" in result_str.lower() if result_str else False
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
                # Store accumulated usage for retrieval
                self._last_usage = {
                    "provider": self.provider_name.lower(),
                    "model": getattr(self, 'model_name', ''),
                    **total_usage,
                }
                log(f"✅ {self.provider_name} response received - {len(final_response)} chars (usage: {total_usage})")
                return final_response

        log(f"❌ {self.provider_name} max iterations reached")
        self._last_usage = {
            "provider": self.provider_name.lower(),
            "model": getattr(self, 'model_name', ''),
            **total_usage,
        }
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

        # Store usage from initial call
        if response.usage:
            self._last_usage = {
                "provider": self.provider_name.lower(),
                "model": getattr(self, 'model_name', ''),
                "input_tokens": response.usage.get("input_tokens", 0),
                "output_tokens": response.usage.get("output_tokens", 0),
                "cached_tokens": response.usage.get("cached_tokens", 0),
            }

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

        # Accumulate usage from previous calls
        prev_usage = getattr(self, '_last_usage', {})
        accumulated_input = prev_usage.get("input_tokens", 0)
        accumulated_output = prev_usage.get("output_tokens", 0)
        accumulated_cached = prev_usage.get("cached_tokens", 0)

        # Check if auto mode or manual mode
        if self.auto_function_calling:
            # Auto mode: loop until final response
            final_response = self._chat_auto_execute_tools(messages, tools, tool_map)
            # _chat_auto_execute_tools already sets _last_usage, merge with previous
            if hasattr(self, '_last_usage') and self._last_usage:
                self._last_usage["input_tokens"] += accumulated_input
                self._last_usage["output_tokens"] += accumulated_output
                self._last_usage["cached_tokens"] += accumulated_cached
            self._pending_messages = []
            self._pending_response = None
            return final_response
        else:
            # Manual mode: make ONE call and check if more tools are needed
            raw_response = self._call_chat_api(messages, tools)
            self._log_cache_usage(raw_response)
            response = self.adapter.from_response(raw_response)

            # Accumulate usage
            if response.usage:
                accumulated_input += response.usage.get("input_tokens", 0)
                accumulated_output += response.usage.get("output_tokens", 0)
                accumulated_cached += response.usage.get("cached_tokens", 0)

            self._last_usage = {
                "provider": self.provider_name.lower(),
                "model": getattr(self, 'model_name', ''),
                "input_tokens": accumulated_input,
                "output_tokens": accumulated_output,
                "cached_tokens": accumulated_cached,
            }

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
        max_iterations: int = None,
        allowed_tools: Optional[List[str]] = None
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
            tools = self._get_ai_cell_tools(allowed_tools=allowed_tools)
            tool_map = self._get_ai_cell_tool_map(allowed_tools=allowed_tools)

            # Add web search tool — model decides when to use it
            web_search_tool = self._get_web_search_tool()
            if web_search_tool:
                tools = tools + [web_search_tool]
                log("🌐 Web search tool included for AI Cell")

            log(f"🔧 Available tools ({len(tool_map)}): {list(tool_map.keys())}")

            # Prepare initial messages
            messages = self._prepare_ai_cell_messages(notebook_context, user_prompt, images)

            # Accumulate thinking and usage across all iterations
            accumulated_thinking = ""
            total_usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}
            empty_response_count = 0  # Track consecutive empty responses
            MAX_EMPTY_RETRIES = 2  # Allow up to 2 retries on empty response

            # Tool loop detection
            tool_call_counts: Dict[str, int] = defaultdict(int)

            for iteration in range(max_iterations):
                # ✅ CANCELLATION CHECK - before each iteration
                self._check_cancelled()

                log(f"🔄 AI Cell iteration {iteration + 1}/{max_iterations}")
                self._emit_progress("iteration_start", {"iteration": iteration + 1, "max": max_iterations})

                # Call LLM (provider-specific)
                response = self._call_llm_for_ai_cell(messages, tools)

                # Accumulate usage from this iteration
                if response.usage:
                    total_usage["input_tokens"] += response.usage.get("input_tokens", 0)
                    total_usage["output_tokens"] += response.usage.get("output_tokens", 0)
                    total_usage["cached_tokens"] += response.usage.get("cached_tokens", 0)

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
                            "error": "empty_response",
                            "usage": {"provider": self.provider_name.lower(), "model": getattr(self, 'model_name', ''), **total_usage},
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
                    log(f"🤖 AI Cell response: {len(response.text)} chars, {len(steps)} steps, thinking: {len(accumulated_thinking)} chars, usage: {total_usage}")
                    self._emit_progress("iteration_end", {"final": True})
                    return {
                        "response": response.text or "I've analyzed your notebook. Please let me know if you need more specific information.",
                        "steps": [s.to_dict() for s in steps],
                        "thinking": accumulated_thinking.strip() if accumulated_thinking else "",
                        "usage": {"provider": self.provider_name.lower(), "model": getattr(self, 'model_name', ''), **total_usage},
                    }

                # Execute tools with safety guards
                tool_results: List[ToolResult] = []
                total_result_chars = 0

                for tool_call in response.tool_calls:
                    # ✅ CANCELLATION CHECK - before each tool
                    self._check_cancelled()

                    tool_name = tool_call.name
                    tool_args = tool_call.arguments

                    # Loop detection
                    call_key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
                    tool_call_counts[call_key] += 1
                    if tool_call_counts[call_key] > TOOL_LOOP_THRESHOLD:
                        log(f"⚠️ Tool loop detected: {tool_name} called {tool_call_counts[call_key]} times — skipping")
                        result_str = json.dumps({"error": f"Skipped: {tool_name} already called with these arguments {TOOL_LOOP_THRESHOLD} times. Try a different approach."})
                        is_error = True
                        steps.append(ToolStep(type="tool_call", name=tool_name, content=json.dumps(tool_args, indent=2)))
                        steps.append(ToolStep(type="tool_result", name=tool_name, content="Skipped (loop detected)"))
                        self._emit_progress("tool_result", {"name": tool_name, "result": "Skipped (loop detected)"})
                        tool_results.append(ToolResult(tool_call_id=tool_call.id, name=tool_name, result=result_str, is_error=True))
                        continue

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

                    # Truncate oversized individual results
                    if len(result_str) > MAX_TOOL_RESULT_CHARS:
                        result_str = result_str[:MAX_TOOL_RESULT_CHARS] + f"\n[Truncated — {len(result_str)} total chars]"

                    # Cap cumulative results
                    total_result_chars += len(result_str)
                    if total_result_chars > MAX_TOTAL_TOOL_RESULTS:
                        result_str = json.dumps({"error": "Result omitted: total tool output limit reached."})

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
                "steps": [s.to_dict() for s in steps],
                "usage": {"provider": self.provider_name.lower(), "model": getattr(self, 'model_name', ''), **total_usage},
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
