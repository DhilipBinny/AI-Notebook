"""
Jupyter Kernel Tool - Allows LLM to execute Python code in the kernel

Uses session-scoped kernel from session_manager.
"""

from backend.session_manager import get_current_session
from backend.utils.util_func import log_debug_message


def _get_session_kernel():
    """Get kernel from current session. Raises if no session."""
    session = get_current_session()
    if not session:
        raise RuntimeError("No active session. Session is required for kernel operations.")
    return session.kernel


def execute_python_code(code: str) -> dict:
    """
    Execute Python code directly in the user's kernel for quick checks and calculations.

    WHEN TO USE THIS TOOL:
    - Quick calculations: "what's 2+2?" → execute_python_code("print(2+2)")
    - Check variable values: "what's in x?" → execute_python_code("print(x)")
    - Verify something works: execute_python_code("len(df)")
    - Answer questions requiring computation

    WHEN NOT TO USE THIS TOOL:
    - To run a notebook cell → use execute_cell(cell_id) instead
    - To test code before suggesting → use sandbox_execute(code) instead
    - To write code into a cell → use update_cell_content() instead

    The code runs in the user's kernel. Variables persist between calls.
    Output is NOT saved to any cell.

    Args:
        code: Python code to execute (single or multiple lines)

    Returns:
        Dictionary with success, output, error, execution_count
    """

    log_debug_message(f"==> execute_python_code: {code} called from LLM")

    kernel = _get_session_kernel()

    # Auto-start kernel if not running
    if not kernel.is_alive():
        if not kernel.start():
            return {
                "success": False,
                "output": "",
                "error": "Failed to start kernel. Please try again.",
                "execution_count": None
            }

    result = kernel.execute(code)

    # Format output for LLM
    output_text = ""
    if result["outputs"]:
        for output in result["outputs"]:
            if output.get("type") == "stream":
                output_text += output.get("text", "")
            elif output.get("type") == "execute_result":
                output_text += output.get("data", {}).get("text/plain", "")
            elif output.get("type") == "display_data":
                output_text += output.get("data", {}).get("text/plain", "")

    return {
        "success": result["success"],
        "output": output_text.strip(),
        "error": str(result["error"]) if result["error"] else None,
        "execution_count": result["execution_count"]
    }
