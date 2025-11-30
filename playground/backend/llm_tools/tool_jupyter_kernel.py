"""
Jupyter Kernel Tool - Allows LLM to execute Python code in the kernel

Uses session-scoped kernel from session_manager.
"""

from backend.session_manager import get_current_session
from backend.utils.util_func import log_debug_message


def _get_session_kernel():
    """Get kernel from current session, or fallback to global kernel"""
    session = get_current_session()
    if session:
        return session.kernel
    # Fallback to global kernel
    from backend.kernel_manager import get_kernel
    return get_kernel()


def execute_python_code(code: str) -> dict:
    """
    Execute Python code in the Jupyter kernel and return results.

    Use this tool when you need to:
    - Perform calculations or data analysis
    - Check current variable values or kernel state
    - Run code to answer questions that require computation
    - Test or verify something programmatically
    - Generate data or visualizations

    The code runs in a persistent Python session, so variables are preserved between calls.

    Args:
        code: Python code to execute. Can be multiple lines. Variables persist between executions.

    Returns:
        Dictionary with execution results including success status, output, errors, and execution count.
    """

    log_debug_message(f"==> execute_python_code: {code} called from LLM")

    kernel = _get_session_kernel()

    # Auto-start kernel if not running
    if not kernel.is_alive():
        kernel.start()

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
