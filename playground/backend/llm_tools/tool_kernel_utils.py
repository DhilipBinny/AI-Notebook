"""
Runtime Inspection Tools - Additional runtime inspection utilities

Runtime tools (require running kernel):
- runtime_get_last_error: Get the most recent error/exception
- runtime_get_dataframe: Get detailed DataFrame information
"""

from backend.session_manager import get_current_session
from backend.utils.util_func import log


def _get_session_kernel(auto_start: bool = True):
    """Get kernel from current session. Raises if no session."""
    session = get_current_session()
    if not session:
        raise RuntimeError("No active session. Session is required for kernel operations.")
    kernel = session.kernel
    if auto_start and not kernel.is_alive():
        log("[Kernel Utils] Auto-starting kernel for session")
        kernel.start()
    return kernel


def runtime_get_last_error() -> dict:
    """
    Get the most recent error/exception from the running kernel.

    Use this tool when:
    - User asks "why did this fail?" or "what's the error?"
    - User asks to fix/debug something without showing the error
    - You need to understand what went wrong in a recent execution

    Returns:
        Dictionary with:
        - success: Whether retrieval succeeded
        - has_error: Whether there was a recent error
        - ename: Exception name (e.g., "ValueError", "TypeError")
        - evalue: Exception message
        - traceback: Full traceback as list of strings
        - simplified: Human-readable summary of the error
        - error: Error message if retrieval failed

    Example:
        result = runtime_get_last_error()
        # Returns: {"success": True, "has_error": True,
        #   "ename": "KeyError", "evalue": "'column_name'",
        #   "simplified": "KeyError: The key 'column_name' was not found..."}
    """
    log("==> runtime_get_last_error() called from LLM")

    kernel = _get_session_kernel()

    if not kernel.is_alive():
        return {
            "success": False,
            "has_error": False,
            "error": "Kernel is not running."
        }

    # Get last error from IPython's error history
    inspect_code = '''
import json
import sys

_error_info = {
    "has_error": False,
    "ename": None,
    "evalue": None,
    "traceback": [],
    "simplified": None
}

# Check if there's a last exception
if hasattr(sys, 'last_type') and sys.last_type is not None:
    _error_info["has_error"] = True
    _error_info["ename"] = sys.last_type.__name__ if sys.last_type else None
    _error_info["evalue"] = str(sys.last_value) if hasattr(sys, 'last_value') else None

    # Get traceback
    if hasattr(sys, 'last_traceback') and sys.last_traceback:
        import traceback
        _tb_lines = traceback.format_tb(sys.last_traceback)
        _error_info["traceback"] = _tb_lines

    # Create simplified explanation
    _ename = _error_info["ename"]
    _evalue = _error_info["evalue"]

    if _ename == "KeyError":
        _error_info["simplified"] = f"KeyError: The key {_evalue} was not found in the dictionary or DataFrame."
    elif _ename == "IndexError":
        _error_info["simplified"] = f"IndexError: {_evalue}. You tried to access an index that doesn't exist."
    elif _ename == "TypeError":
        _error_info["simplified"] = f"TypeError: {_evalue}. There's a type mismatch in your operation."
    elif _ename == "ValueError":
        _error_info["simplified"] = f"ValueError: {_evalue}. The value provided is invalid for this operation."
    elif _ename == "NameError":
        _error_info["simplified"] = f"NameError: {_evalue}. The variable or function is not defined."
    elif _ename == "AttributeError":
        _error_info["simplified"] = f"AttributeError: {_evalue}. The object doesn't have this attribute/method."
    elif _ename == "ImportError" or _ename == "ModuleNotFoundError":
        _error_info["simplified"] = f"{_ename}: {_evalue}. The module is not installed or cannot be found."
    elif _ename == "FileNotFoundError":
        _error_info["simplified"] = f"FileNotFoundError: {_evalue}. The file or path doesn't exist."
    elif _ename == "ZeroDivisionError":
        _error_info["simplified"] = f"ZeroDivisionError: You tried to divide by zero."
    elif _ename == "SyntaxError":
        _error_info["simplified"] = f"SyntaxError: {_evalue}. There's a syntax error in your code."
    else:
        _error_info["simplified"] = f"{_ename}: {_evalue}"

print(json.dumps(_error_info))
'''

    result = kernel.execute(inspect_code)

    if not result["success"]:
        return {
            "success": False,
            "has_error": False,
            "error": str(result.get("error", "Failed to get error info"))
        }

    try:
        output_text = ""
        for output in result.get("outputs", []):
            if output.get("type") == "stream":
                output_text += output.get("text", "")

        import json
        error_info = json.loads(output_text.strip())
        error_info["success"] = True
        return error_info
    except Exception as e:
        return {
            "success": False,
            "has_error": False,
            "error": f"Failed to parse error info: {str(e)}"
        }


def runtime_get_dataframe(name: str) -> dict:
    """
    Get COMPREHENSIVE info about a pandas DataFrame from the running kernel (columns, types, stats, nulls).

    WHEN TO USE THIS TOOL:
    - Variable is a pandas DataFrame
    - User asks about data structure, columns, or types
    - You need to write code using the DataFrame
    - User asks for data analysis suggestions

    WHEN NOT TO USE THIS TOOL:
    - For non-DataFrame variables → use runtime_get_variable(name) instead

    This tool provides DataFrame-specific info that runtime_get_variable doesn't:
    - Column names and data types
    - Null counts per column
    - Statistical summary (describe)
    - Sample values
    - Memory usage

    Args:
        name: Name of the DataFrame variable

    Returns:
        Dictionary with shape, columns, dtypes, null_counts, head, describe, sample_values

    Example:
        runtime_get_dataframe("df")  → full DataFrame analysis
    """
    log(f"==> runtime_get_dataframe({name}) called from LLM")

    kernel = _get_session_kernel()

    if not kernel.is_alive():
        return {
            "success": False,
            "error": "Kernel is not running."
        }

    inspect_code = f'''
import json
import pandas as pd

_var_name = {repr(name)}

if _var_name not in dir():
    print(json.dumps({{"error": f"Variable '{{_var_name}}' not found"}}))
else:
    _obj = eval(_var_name)

    if not isinstance(_obj, pd.DataFrame):
        print(json.dumps({{"error": f"'{{_var_name}}' is not a DataFrame, it's a {{type(_obj).__name__}}"}}))
    else:
        _info = {{
            "name": _var_name,
            "shape": list(_obj.shape),
            "rows": _obj.shape[0],
            "columns_count": _obj.shape[1],
            "columns": list(_obj.columns),
            "dtypes": {{str(k): str(v) for k, v in _obj.dtypes.to_dict().items()}},
            "null_counts": _obj.isnull().sum().to_dict(),
            "total_nulls": int(_obj.isnull().sum().sum()),
            "memory_usage": None,
            "head": None,
            "describe": None,
            "sample_values": {{}},
            "unique_counts": {{}}
        }}

        # Memory usage
        try:
            _mem = _obj.memory_usage(deep=True).sum()
            if _mem < 1024:
                _info["memory_usage"] = f"{{_mem}} bytes"
            elif _mem < 1024 * 1024:
                _info["memory_usage"] = f"{{_mem / 1024:.1f}} KB"
            else:
                _info["memory_usage"] = f"{{_mem / (1024*1024):.1f}} MB"
        except:
            pass

        # Head (first 5 rows)
        try:
            _info["head"] = _obj.head().to_string()
        except:
            pass

        # Describe (statistics)
        try:
            _desc = _obj.describe(include='all')
            _info["describe"] = _desc.to_string()
        except:
            pass

        # Sample values and unique counts for each column (limit to first 20 cols)
        for _col in list(_obj.columns)[:20]:
            try:
                _unique = _obj[_col].nunique()
                _info["unique_counts"][str(_col)] = _unique

                # Get sample of unique values
                if _unique <= 10:
                    _samples = _obj[_col].dropna().unique().tolist()[:10]
                else:
                    _samples = _obj[_col].dropna().head(5).tolist()

                # Convert to JSON-safe format
                _safe_samples = []
                for _s in _samples:
                    try:
                        if hasattr(_s, 'item'):  # numpy types
                            _safe_samples.append(_s.item())
                        else:
                            _safe_samples.append(str(_s) if not isinstance(_s, (int, float, str, bool, type(None))) else _s)
                    except:
                        _safe_samples.append(str(_s))
                _info["sample_values"][str(_col)] = _safe_samples
            except:
                pass

        print(json.dumps(_info))
'''

    result = kernel.execute(inspect_code)

    if not result["success"]:
        return {
            "success": False,
            "error": str(result.get("error", "Failed to inspect DataFrame"))
        }

    try:
        output_text = ""
        for output in result.get("outputs", []):
            if output.get("type") == "stream":
                output_text += output.get("text", "")

        import json
        info = json.loads(output_text.strip())

        if "error" in info:
            return {
                "success": False,
                "error": info["error"]
            }

        info["success"] = True
        return info
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse DataFrame info: {str(e)}"
        }
