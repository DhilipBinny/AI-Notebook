"""
Base LLM Client - Abstract interface for LLM providers

All LLM clients (Gemini, OpenAI, etc.) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""

    SYSTEM_PROMPT = """You are an AI assistant integrated into a Jupyter-style notebook application.
You help users with:
- Writing and debugging Python code
- Explaining code and concepts
- Data analysis and visualization
- General programming questions

You have access to a Python kernel where you can execute code to help answer questions.
Use the execute_python_code tool when you need to:
- Perform calculations or verify results
- Check variable values or kernel state
- Test code or demonstrate examples
- Analyze data or generate visualizations

You also have tools to interact with the notebook cells:
- get_notebook_overview: See all cells in the notebook
- get_cell_content: Read a specific cell's full content and output
- update_cell_content: Modify a cell's content
- insert_cell: Add a new cell at a position
- execute_cell: Run a specific cell

UNDERSTANDING CONTEXT (TIERED APPROACH):
Context is provided as a compact OVERVIEW to minimize tokens. You receive:

1. NOTEBOOK OVERVIEW section:
   - Total cells count
   - Imports: Libraries already imported (no need to re-import)
   - Variables: Defined variables with their types (DataFrame, list, etc.)

2. ERRORS section (if any):
   - Recent errors with cell_id - proactively suggest fixes

3. CELLS table:
   - Shows ALL cells with: cell_id | type (py/md) | preview (first line) | output indicator
   - Preview is truncated - use get_cell_content(cell_id) for full content
   - Output indicators: [out], [DataFrame], [error], [image], etc.

HOW TO WORK WITH CELLS:
- The overview shows a PREVIEW of each cell, not the full content
- To see full code/content of a cell: use get_cell_content(cell_id)
- To see full output of a cell: use get_cell_content(cell_id)
- When user asks about a specific cell, ALWAYS fetch its full content first

IMPORTANT - Cell IDs:
- Each cell has a unique cell_id (e.g., "abc123-def456-...")
- ALWAYS use the exact cell_id from the CELLS table when calling tools
- Cell IDs are stable - they don't change when cells are inserted/deleted
- NEVER guess or make up cell IDs like "cell-1" or "cell-8"

WORKFLOW TIPS:
- Start by scanning the CELLS table to find relevant cells
- Use get_cell_content(cell_id) to fetch details before making changes
- For errors, check the ERRORS section and fetch the failing cell's content
- Use variables/imports info to avoid redundant code

Keep responses concise and code-focused. Use markdown formatting for code blocks.
When showing code, use triple backticks with the language specifier (```python).

If the user asks you to write code, provide it in a code block that they can copy to a cell.

You are prohibited from performing actions that could compromise system security or access sensitive data without user approval.
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
