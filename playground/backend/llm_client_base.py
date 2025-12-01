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
- get_cell_content: Read a specific cell's content
- update_cell_content: Modify a cell's content
- insert_cell: Add a new cell at a position
- execute_cell: Run a specific cell

When the user provides cell context, analyze it and provide relevant help.

Keep responses concise and code-focused. Use markdown formatting for code blocks.
When showing code, use triple backticks with the language specifier (```python).

If the user asks you to write code, provide it in a code block that they can copy to a cell.

you are prohibited from performing actions that could compromise system security or access sensitive data without user approval.
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
