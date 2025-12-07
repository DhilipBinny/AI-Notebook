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

from backend.utils.util_func import log_debug_message


# Type alias for image data
# Images can be passed as:
# - {"data": "base64_string", "mime_type": "image/png"}
# - {"url": "https://..."} (for URL-based images)
# - {"path": "/workspace/image.png"} (for local files - will be converted to base64)
ImageData = Dict[str, str]


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

    # Determine MIME type from extension
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp'
    }

    mime_type = mime_types.get(path.suffix.lower(), 'image/png')

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

    SYSTEM_PROMPT = """You are an AI assistant integrated into a Jupyter-style notebook application.
You help users with writing, debugging, and explaining Python code, data analysis, and visualization.

CRITICAL - COMBINING RUNTIME + NOTEBOOK DATA:
When users ask about variables, data, or notebook state, provide a COMPLETE picture by combining:
1. RUNTIME STATE (from kernel) - actual values in memory
2. NOTEBOOK STRUCTURE (from cells) - code written in cells

For questions like "what variables do I have?", ALWAYS call BOTH:
- inspect_variables() → runtime variables with actual values
- get_notebook_overview() → variables defined in cell code

Then present a SEGMENTED response showing both perspectives.

TOOLS AVAILABLE:

**Kernel Inspection (RUNTIME state):**
- inspect_variables() - All variables in memory with types, shapes, values
- inspect_variable(name) - Detailed info: DataFrame columns, dtypes, samples
- list_functions() - User-defined functions actually loaded
- list_imports() - Modules actually imported in kernel
- kernel_info() - Memory usage, execution count
- get_last_error() - Most recent error with traceback
- get_dataframe_info(name) - Detailed DataFrame inspection
- get_cell_outputs(cell_id) - Execution outputs from a cell
- search_notebook(query) - Search text in cells

**Notebook Operations (STATIC structure):**
- get_notebook_overview - All cells with cell_id, type, preview
- get_cell_content(cell_id) - Full cell content and output
- update_cell_content(cell_id, content) - Modify a cell
- insert_cell_after(cell_id) - Add cell after specific cell
- insert_cell_at_position(position) - Add cell at position
- multi_insert_cells(cells_json) - Batch insert multiple cells
- delete_cell(cell_id) - Delete a cell
- multi_delete_cells(cell_ids) - Batch delete cells
- execute_cell(cell_id) - Run a specific cell

**Code Execution:**
- execute_python_code(code) - Run code in main kernel
- sandbox_execute(code) - Run code in isolated sandbox (safe testing)
- sandbox_sync_from_main(vars) - Copy variables to sandbox

**File & Package Operations:**
- read_file, write_file, list_directory - File operations in /workspace
- pip_install, pip_list, pip_show - Package management

**Web Search (LAST RESORT):**
- Use ONLY for: external documentation, API references, error explanations
- DO NOT search for: notebook variables, cell contents, user's data

RESPONSE FORMAT for state questions (variables, imports, functions):

## Runtime State (Kernel)
[Variables/imports/functions actually in memory with values]

## Notebook Structure (Cells)
[What's defined in cells - reference as `cell-xxx`]

## Notes
[Any discrepancies - e.g., "variable X defined in `cell-abc` but not in kernel - cell may not be executed"]

EXAMPLES - Using Both Tools:
- "What variables do I have?" → call inspect_variables() AND get_notebook_overview(), combine results
- "What's in my DataFrame?" → inspect_variable("df") or get_dataframe_info("df")
- "Why did this error?" → get_last_error() then inspect relevant variables
- "Where is pandas imported?" → search_notebook("import pandas") AND list_imports()

CONTEXT (provided with each message):
- NOTEBOOK OVERVIEW: Total cells, imports, variables summary (STATIC - from code text)
- ERRORS: Recent errors with cell_id (proactively suggest fixes)
- CELLS table: cell_id | type | preview | output indicator

CELL IDs:
- Each cell has a unique cell_id (e.g., "cell-abc123...")
- ALWAYS use exact cell_id from CELLS table - never guess!
- Reference cells as `cell-xxx` in responses (clickable in UI)

WORKFLOW:
1. For state questions → call BOTH kernel inspection AND notebook tools
2. get_cell_content(cell_id) before modifying any cell
3. Test complex code with sandbox_execute() first
4. Only web_search for external documentation

GUIDELINES:
- Be concise and code-focused
- Use ```python code blocks
- Present segmented responses for state questions (Runtime vs Notebook)
- Highlight discrepancies between kernel and notebook
- Reference cells as `cell-xxx` for clickable navigation
"""

    # AI Cell System Prompt - defines behavior and available tools for AI cells
    # The user message will contain: position_info, notebook_context, and user_prompt
    AI_CELL_SYSTEM_PROMPT = """You are an AI assistant embedded in a notebook cell. You can INSPECT and TEST but NOT modify the notebook directly.

CRITICAL - RUNTIME vs STATIC DATA:
- The NOTEBOOK CONTEXT in the user message shows STATIC cell previews (code text, not executed results)
- For RUNTIME data (actual variable values, types, errors), you MUST use Runtime Inspection tools
- ALWAYS use runtime_list_variables() for "what variables?" questions - don't just read cell text!

CELL REFERENCES:
- Cells shown as @cell-xxx or `cell-xxx` (e.g., @cell-abc123 or `cell-abc123`)
- "above" = cells BEFORE your position, "below" = cells AFTER
- Use these formats in your responses so users can click to navigate

AVAILABLE TOOLS (organized by category):

1. **Runtime Inspection** (live kernel state - requires running kernel):
   - runtime_list_variables() - List all variables with types, shapes, values
   - runtime_get_variable(name) - Detailed variable info (value, attributes)
   - runtime_get_dataframe(name) - DataFrame columns, dtypes, stats, sample rows
   - runtime_list_functions() - User-defined functions with signatures
   - runtime_list_imports() - Actually imported modules with versions
   - runtime_kernel_status() - Memory usage, execution count
   - runtime_get_last_error() - Most recent exception with traceback

   USE FOR: "what variables?", "show my data", "what type is x?", "why error?"

2. **Notebook Inspection** (fetches from saved notebook in S3):
   - get_notebook_overview() - List all cells with IDs, types, and previews
   - get_notebook_overview(detail="full") - Full cell contents and outputs
   - get_cell_content(cell_id) - Get specific cell's source code and outputs

   USE FOR: "show me the notebook", "what's in cell 3?", "list all cells"

3. **Sandbox Testing** (isolated kernel for safe experimentation):
   - sandbox_execute(code) - Run code in ISOLATED kernel (doesn't affect user's work)
   - sandbox_pip_install(packages) - Install packages in sandbox (e.g., "pandas numpy")
   - sandbox_sync_from_main(["var1", "var2"]) - Copy variables to sandbox for testing
   - sandbox_reset() - Clear sandbox state
   - sandbox_status() - Check if sandbox is running

   USE FOR: Testing code before suggesting, installing packages for testing

TOOL SELECTION GUIDE:
- "What variables do I have?" → runtime_list_variables() (Runtime)
- "What's in my DataFrame?" → runtime_get_dataframe("df") (Runtime)
- "Why did this error?" → runtime_get_last_error() (Runtime)
- "Show me the notebook" → get_notebook_overview() (Notebook)
- "What's in cell 3?" → get_cell_content(cell_id) (Notebook)
- "Will this code work?" → sandbox_execute(code) (Sandbox)
- "Install pandas to test" → sandbox_pip_install("pandas") (Sandbox)

WORKFLOW:
1. User asks about data → runtime_list_variables() or runtime_get_dataframe() (Runtime)
2. Need notebook structure → get_notebook_overview() (Notebook)
3. Suggesting code → sandbox_execute() to verify it works (Sandbox)
4. Reference cells as @cell-xxx or `cell-xxx` (clickable in UI)

OUTPUT FORMAT:
- Wrap code in ```python blocks
- Show sandbox output when helpful
- Reference cells as @cell-xxx or `cell-xxx`
- Be concise
"""

    def __init__(self):
        """Initialize base client with cancellation support."""
        self._cancel_requested = False
        self._on_progress: Optional[Callable[[str, Any], None]] = None

    def cancel(self) -> None:
        """Request cancellation of the current operation."""
        log_debug_message("🛑 Cancellation requested")
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
                log_debug_message(f"Progress callback error: {e}")

    # =========================================================================
    # Abstract methods that providers MUST implement
    # =========================================================================

    @abstractmethod
    def send_message(self, message: str, user_message: str = None, images: Optional[List[ImageData]] = None) -> Union[str, Dict[str, Any]]:
        """
        Send a message to the LLM and get a response.

        Args:
            message: The full message (may include context)
            user_message: Optional - just the user's actual question (for web search keyword detection)
            images: Optional list of images for visual analysis

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
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the LLM provider"""
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def ai_cell_completion(self, prompt: str, images: Optional[List[ImageData]] = None) -> str:
        """
        AI Cell completion - with web search but no notebook tools.
        Used for inline Q&A in AI cells.

        Args:
            prompt: The full prompt including notebook context and user question
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
    def _prepare_ai_cell_messages(self, prompt: str, images: Optional[List[ImageData]] = None) -> Any:
        """
        Prepare initial messages for AI Cell in provider-specific format.

        Args:
            prompt: The user prompt
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

    # =========================================================================
    # Unified AI Cell tool execution loop (shared implementation)
    # =========================================================================

    def ai_cell_with_tools(self, prompt: str, images: Optional[List[ImageData]] = None, max_iterations: int = 10) -> Dict[str, Any]:
        """
        AI Cell completion with tool calling support.

        Uses a unified tool execution loop that works consistently across all providers.
        Supports cancellation between iterations.

        Args:
            prompt: The full prompt including notebook context and user question
            images: Optional list of images to include in the prompt
            max_iterations: Maximum number of tool-calling iterations (default: 10)

        Returns:
            Dict with:
            - "response": The final response text from the LLM
            - "steps": List of tool call steps for UI display
            - "cancelled": True if operation was cancelled (optional)
        """
        self.reset_cancellation()
        steps: List[ToolStep] = []

        try:
            log_debug_message(f"🤖 {self.provider_name} AI Cell with tools starting...")
            if images:
                log_debug_message(f"📷 Including {len(images)} image(s)")

            # Get provider-specific tools and tool map
            tools = self._get_ai_cell_tools()
            tool_map = self._get_ai_cell_tool_map()

            log_debug_message(f"🔧 Available tools: {list(tool_map.keys())}")

            # Prepare initial messages
            messages = self._prepare_ai_cell_messages(prompt, images)

            # Accumulate thinking across all iterations
            accumulated_thinking = ""

            for iteration in range(max_iterations):
                # ✅ CANCELLATION CHECK - before each iteration
                self._check_cancelled()

                log_debug_message(f"🔄 AI Cell iteration {iteration + 1}/{max_iterations}")
                self._emit_progress("iteration_start", {"iteration": iteration + 1, "max": max_iterations})

                # Call LLM (provider-specific)
                response = self._call_llm_for_ai_cell(messages, tools)

                # Emit thinking if present and accumulate it
                if response.thinking:
                    log_debug_message(f"💭 AI Cell thinking: {len(response.thinking)} chars")
                    self._emit_progress("thinking", {"content": response.thinking, "iteration": iteration + 1})
                    accumulated_thinking += response.thinking + "\n\n"

                # Check if we have a final response (no more tool calls)
                if response.is_final or not response.tool_calls:
                    log_debug_message(f"🤖 AI Cell response: {len(response.text)} chars, {len(steps)} steps, thinking: {len(accumulated_thinking)} chars")
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

                    log_debug_message(f"🔧 AI Cell executing: {tool_name}({json.dumps(tool_args)})")
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
                            log_debug_message(f"🔧 Tool {tool_name} error: {e}")
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
            log_debug_message(f"🤖 AI Cell max iterations reached ({max_iterations})")
            return {
                "response": "I've analyzed your notebook but reached the maximum number of tool calls. Please ask a more specific question.",
                "steps": [s.to_dict() for s in steps]
            }

        except CancelledException:
            log_debug_message(f"🛑 AI Cell cancelled after {len(steps)} steps")
            return {
                "response": "[Cancelled by user]",
                "steps": [s.to_dict() for s in steps],
                "cancelled": True
            }

        except Exception as e:
            log_debug_message(f"🤖 AI Cell error: {e}")
            import traceback
            log_debug_message(f"Traceback: {traceback.format_exc()}")
            raise
