"""
Base LLM Client - Abstract interface for LLM providers

All LLM clients (Gemini, OpenAI, etc.) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""

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

    @abstractmethod
    def send_message(self, message: str) -> Union[str, Dict[str, Any]]:
        """
        Send a message to the LLM and get a response.

        Args:
            message: The user message (may include context)

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
    def ai_cell_completion(self, prompt: str) -> str:
        """
        AI Cell completion - with web search but no notebook tools.
        Used for inline Q&A in AI cells.

        Args:
            prompt: The full prompt including notebook context and user question

        Returns:
            The response text from the LLM (may include web search results)
        """
        pass

    @abstractmethod
    def ai_cell_with_tools(self, prompt: str, max_iterations: int = 10) -> str:
        """
        AI Cell completion with tool calling support.
        Used for inline Q&A with kernel inspection and sandbox execution.

        The AI cell has access to:
        - Kernel inspection tools (inspect_variables, inspect_variable, list_functions, list_imports, kernel_info)
        - Sandbox tools (sandbox_execute, sandbox_reset, sandbox_sync_from_main, sandbox_status)

        Tools are automatically executed in a loop until the LLM produces a final response.

        Args:
            prompt: The full prompt including notebook context and user question
            max_iterations: Maximum number of tool-calling iterations (default: 10)

        Returns:
            The final response text from the LLM after all tool executions
        """
        pass
