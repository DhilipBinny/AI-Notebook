"""
Sandbox Kernel Tools - Allows AI to experiment with code in an isolated environment

The sandbox is a separate Jupyter kernel that:
- Is isolated from the user's main kernel
- Can be reset at any time
- Can optionally sync variables from the main kernel
- Has a timeout to prevent runaway code

This allows the AI to:
- Test code suggestions before giving them to the user
- Verify code works correctly
- Show actual output instead of guessing
- Experiment without affecting the user's work

Uses a per-session sandbox kernel managed alongside the main kernel.
"""

from typing import Optional, Dict, Any, List
from backend.session_manager import get_current_session
from backend.kernel_manager import NotebookKernel
from backend.utils.util_func import log_debug_message


# Store sandbox kernels per session
_sandbox_kernels: Dict[str, NotebookKernel] = {}


def _get_sandbox_kernel() -> Optional[NotebookKernel]:
    """Get or create sandbox kernel for current session"""
    session = get_current_session()
    if not session:
        return None

    session_id = session.session_id

    if session_id not in _sandbox_kernels:
        _sandbox_kernels[session_id] = NotebookKernel()

    return _sandbox_kernels[session_id]


def _get_main_kernel():
    """Get the main kernel from current session"""
    session = get_current_session()
    if session:
        return session.kernel
    from backend.kernel_manager import get_kernel
    return get_kernel()


def sandbox_execute(code: str, timeout: int = 10) -> dict:
    """
    Execute Python code in an isolated sandbox kernel.

    Use this tool when you need to:
    - Test code before suggesting it to the user
    - Verify that code works correctly
    - See actual output instead of guessing
    - Experiment with different approaches
    - Check for syntax errors or runtime errors

    The sandbox is completely isolated from the user's main kernel.
    Variables and imports do NOT affect the user's environment.

    Args:
        code: Python code to execute in the sandbox
        timeout: Maximum execution time in seconds (default: 10, max: 30)

    Returns:
        Dictionary with:
        - success: Whether execution succeeded
        - output: Output text from the code
        - error: Error message if execution failed
        - execution_time: How long the code took to run

    Example:
        result = sandbox_execute("print(2 + 2)")
        # Returns: {"success": True, "output": "4", "error": None}

        result = sandbox_execute("import pandas as pd; df = pd.DataFrame({'a': [1,2,3]}); print(df.head())")
        # Returns: {"success": True, "output": "   a\\n0  1\\n1  2\\n2  3", "error": None}
    """
    log_debug_message(f"==> sandbox_execute: {code[:100]}... called from LLM")

    sandbox = _get_sandbox_kernel()
    if sandbox is None:
        return {
            "success": False,
            "output": "",
            "error": "No session available for sandbox"
        }

    # Limit timeout
    timeout = min(max(timeout, 1), 30)

    # Start sandbox kernel if not running
    if not sandbox.is_alive():
        log_debug_message("[Sandbox] Starting sandbox kernel...")
        if not sandbox.start():
            return {
                "success": False,
                "output": "",
                "error": "Failed to start sandbox kernel"
            }

    # Execute in sandbox
    import time
    start_time = time.time()

    result = sandbox.execute(code, timeout=timeout)

    execution_time = round(time.time() - start_time, 2)

    # Format output
    output_text = ""
    if result["outputs"]:
        for output in result["outputs"]:
            if output.get("type") == "stream":
                output_text += output.get("text", "")
            elif output.get("type") == "execute_result":
                output_text += output.get("data", {}).get("text/plain", "")
            elif output.get("type") == "display_data":
                data = output.get("data", {})
                if "text/plain" in data:
                    output_text += data["text/plain"]
                elif "image/png" in data:
                    output_text += "[Image output generated]"
            elif output.get("type") == "error":
                # Include traceback in error
                tb = output.get("traceback", [])
                # Clean up ANSI codes from traceback
                import re
                clean_tb = []
                for line in tb:
                    clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
                    clean_tb.append(clean_line)
                output_text += "\n".join(clean_tb)

    error_msg = None
    if not result["success"]:
        error = result.get("error")
        if isinstance(error, dict):
            error_msg = f"{error.get('ename', 'Error')}: {error.get('evalue', '')}"
        elif error:
            error_msg = str(error)

    return {
        "success": result["success"],
        "output": output_text.strip(),
        "error": error_msg,
        "execution_time": f"{execution_time}s"
    }


def sandbox_reset() -> dict:
    """
    Reset the sandbox kernel to a clean state.

    Use this tool when you need to:
    - Clear all variables from a previous test
    - Start fresh for a new experiment
    - Fix a broken sandbox state

    This completely restarts the sandbox kernel, clearing all state.

    Returns:
        Dictionary with:
        - success: Whether reset succeeded
        - message: Status message

    Example:
        result = sandbox_reset()
        # Returns: {"success": True, "message": "Sandbox reset successfully"}
    """
    log_debug_message("==> sandbox_reset() called from LLM")

    sandbox = _get_sandbox_kernel()
    if sandbox is None:
        return {
            "success": False,
            "message": "No session available for sandbox"
        }

    # Stop and restart
    if sandbox.is_alive():
        sandbox.stop()

    if sandbox.start():
        return {
            "success": True,
            "message": "Sandbox reset successfully. All variables cleared."
        }
    else:
        return {
            "success": False,
            "message": "Failed to restart sandbox kernel"
        }


def sandbox_sync_from_main(variable_names: List[str] = None) -> dict:
    """
    Copy variables from the main kernel to the sandbox.

    Use this tool when you need to:
    - Test code that uses the user's existing variables
    - Work with the user's DataFrame or data
    - Verify code modifications on actual data

    This copies variable values (not references) to the sandbox.
    Changes in the sandbox do NOT affect the main kernel.

    Args:
        variable_names: List of variable names to copy. If None or empty, copies all user variables.

    Returns:
        Dictionary with:
        - success: Whether sync succeeded
        - copied: List of variable names that were copied
        - failed: List of variable names that failed to copy
        - error: Error message if sync completely failed

    Example:
        # Copy specific variables
        result = sandbox_sync_from_main(["df", "config"])
        # Returns: {"success": True, "copied": ["df", "config"], "failed": []}

        # Copy all variables
        result = sandbox_sync_from_main()
        # Returns: {"success": True, "copied": ["df", "x", "y", ...], "failed": []}
    """
    log_debug_message(f"==> sandbox_sync_from_main({variable_names}) called from LLM")

    main_kernel = _get_main_kernel()
    sandbox = _get_sandbox_kernel()

    if sandbox is None:
        return {
            "success": False,
            "copied": [],
            "failed": [],
            "error": "No session available for sandbox"
        }

    if not main_kernel.is_alive():
        return {
            "success": False,
            "copied": [],
            "failed": [],
            "error": "Main kernel is not running"
        }

    # Start sandbox if needed
    if not sandbox.is_alive():
        if not sandbox.start():
            return {
                "success": False,
                "copied": [],
                "failed": [],
                "error": "Failed to start sandbox kernel"
            }

    # First, get list of available variables from main kernel
    if variable_names:
        vars_to_copy = variable_names
    else:
        # Get all user variables
        get_vars_code = '''
import json
_skip_names = {'In', 'Out', 'get_ipython', 'exit', 'quit', '_', '__', '___',
               '_i', '_ii', '_iii', '_oh', '_dh', '_sh'}
_skip_types = {'module', 'function', 'builtin_function_or_method', 'type', 'method'}
_vars = []
for _name in dir():
    if _name.startswith('_'):
        continue
    if _name in _skip_names:
        continue
    try:
        _obj = eval(_name)
        _type_name = type(_obj).__name__
        if _type_name not in _skip_types:
            _vars.append(_name)
    except:
        pass
print(json.dumps(_vars))
'''
        result = main_kernel.execute(get_vars_code)
        if result["success"]:
            try:
                output_text = ""
                for output in result.get("outputs", []):
                    if output.get("type") == "stream":
                        output_text += output.get("text", "")
                import json
                vars_to_copy = json.loads(output_text.strip())
            except:
                vars_to_copy = []
        else:
            vars_to_copy = []

    if not vars_to_copy:
        return {
            "success": True,
            "copied": [],
            "failed": [],
            "message": "No variables to copy"
        }

    # Copy each variable using pickle (for complex objects)
    copied = []
    failed = []

    for var_name in vars_to_copy:
        try:
            # Serialize in main kernel
            serialize_code = f'''
import pickle
import base64
try:
    _data = pickle.dumps({var_name})
    print(base64.b64encode(_data).decode('ascii'))
except Exception as e:
    print(f"ERROR:{{e}}")
'''
            result = main_kernel.execute(serialize_code)

            if not result["success"]:
                failed.append(var_name)
                continue

            output_text = ""
            for output in result.get("outputs", []):
                if output.get("type") == "stream":
                    output_text += output.get("text", "")

            output_text = output_text.strip()

            if output_text.startswith("ERROR:"):
                failed.append(var_name)
                continue

            # Deserialize in sandbox
            deserialize_code = f'''
import pickle
import base64
_data = base64.b64decode("{output_text}")
{var_name} = pickle.loads(_data)
print("OK")
'''
            result = sandbox.execute(deserialize_code)

            if result["success"]:
                copied.append(var_name)
            else:
                failed.append(var_name)

        except Exception as e:
            log_debug_message(f"[Sandbox] Failed to copy {var_name}: {e}")
            failed.append(var_name)

    return {
        "success": len(copied) > 0 or len(failed) == 0,
        "copied": copied,
        "failed": failed,
        "message": f"Copied {len(copied)} variable(s) to sandbox"
    }


def sandbox_status() -> dict:
    """
    Get the current status of the sandbox kernel.

    Use this tool to check if the sandbox is ready for use.

    Returns:
        Dictionary with:
        - success: Always True
        - alive: Whether sandbox kernel is running
        - execution_count: Number of executions in current sandbox session
        - message: Status message

    Example:
        result = sandbox_status()
        # Returns: {"success": True, "alive": True, "execution_count": 5, "message": "Sandbox is running"}
    """
    log_debug_message("==> sandbox_status() called from LLM")

    sandbox = _get_sandbox_kernel()

    if sandbox is None:
        return {
            "success": True,
            "alive": False,
            "execution_count": 0,
            "message": "No session available"
        }

    return {
        "success": True,
        "alive": sandbox.is_alive(),
        "execution_count": sandbox.execution_count,
        "message": "Sandbox is running" if sandbox.is_alive() else "Sandbox is not running (will auto-start on execute)"
    }


def cleanup_sandbox(session_id: str = None):
    """
    Cleanup sandbox kernel for a session (internal use).
    Called when a session is deleted.
    """
    global _sandbox_kernels

    if session_id:
        sandbox = _sandbox_kernels.pop(session_id, None)
        if sandbox and sandbox.is_alive():
            sandbox.stop()
            log_debug_message(f"[Sandbox] Cleaned up sandbox for session {session_id}")
    else:
        # Cleanup all
        for sid, sandbox in list(_sandbox_kernels.items()):
            if sandbox.is_alive():
                sandbox.stop()
        _sandbox_kernels.clear()
        log_debug_message("[Sandbox] Cleaned up all sandboxes")
