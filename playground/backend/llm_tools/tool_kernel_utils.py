"""
Kernel Utility Tools - Additional tools for kernel inspection and debugging

Provides:
- get_last_error: Get the most recent error/exception
- get_dataframe_info: Get detailed DataFrame information
- get_cell_outputs: Get outputs from a specific cell
- search_notebook: Search for text in notebook cells
"""

from typing import Optional, List, Dict, Any
from backend.session_manager import get_current_session
from backend.utils.util_func import log_debug_message


def _get_session_kernel(auto_start: bool = True):
    """Get kernel from current session, with optional auto-start"""
    session = get_current_session()
    if session:
        kernel = session.kernel
        if auto_start and not kernel.is_alive():
            log_debug_message("[Kernel Utils] Auto-starting kernel for session")
            kernel.start()
        return kernel
    from backend.kernel_manager import get_kernel
    kernel = get_kernel()
    if auto_start and not kernel.is_alive():
        log_debug_message("[Kernel Utils] Auto-starting global kernel")
        kernel.start()
    return kernel


def get_last_error() -> dict:
    """
    Get the most recent error/exception from the kernel.

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
        result = get_last_error()
        # Returns: {"success": True, "has_error": True,
        #   "ename": "KeyError", "evalue": "'column_name'",
        #   "simplified": "KeyError: The key 'column_name' was not found..."}
    """
    log_debug_message("==> get_last_error() called from LLM")

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


def get_dataframe_info(name: str) -> dict:
    """
    Get COMPREHENSIVE info about a pandas DataFrame (columns, types, stats, nulls).

    WHEN TO USE THIS TOOL:
    - Variable is a pandas DataFrame
    - User asks about data structure, columns, or types
    - You need to write code using the DataFrame
    - User asks for data analysis suggestions

    WHEN NOT TO USE THIS TOOL:
    - For non-DataFrame variables → use inspect_variable(name) instead

    This tool provides DataFrame-specific info that inspect_variable doesn't:
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
        get_dataframe_info("df")  → full DataFrame analysis
    """
    log_debug_message(f"==> get_dataframe_info({name}) called from LLM")

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


def get_cell_outputs(cell_id: str) -> dict:
    """
    Get a cell's EXECUTION OUTPUT (what it produced when run).

    WHEN TO USE THIS TOOL:
    - To see what a cell outputted (print statements, results, errors)
    - User asks "what did cell 3 produce?"
    - To check if a cell has an error

    WHEN NOT TO USE THIS TOOL:
    - To read the cell's source code → use get_cell_content(cell_id)

    KEY DIFFERENCE:
    - get_cell_content() → returns SOURCE (the code/markdown)
    - get_cell_outputs() → returns OUTPUT (execution results, errors, images)

    Args:
        cell_id: The cell's unique ID

    Returns:
        Dictionary with cell_id, outputs (list), has_error, source

    Example:
        get_cell_outputs(cell_id) → see print output, errors, images
    """
    log_debug_message(f"==> get_cell_outputs({cell_id}) called from LLM")

    session = get_current_session()
    if not session:
        return {
            "success": False,
            "error": "No active session"
        }

    # Get notebook state from session
    notebook_state = session.notebook_state
    cells = notebook_state.get("cells", [])

    # Find the cell
    target_cell = None
    for cell in cells:
        if cell.get("id") == cell_id:
            target_cell = cell
            break

    if not target_cell:
        return {
            "success": False,
            "cell_id": cell_id,
            "error": f"Cell with ID '{cell_id}' not found"
        }

    cell_type = target_cell.get("type", "code")
    source = target_cell.get("source", "")
    outputs = target_cell.get("outputs", [])
    execution_count = target_cell.get("execution_count")

    # Check for errors in outputs
    has_error = any(o.get("output_type") == "error" for o in outputs)

    # Format outputs for easier reading
    formatted_outputs = []
    for output in outputs:
        output_type = output.get("output_type", "unknown")
        formatted = {"type": output_type}

        if output_type == "stream":
            formatted["text"] = output.get("text", "")
        elif output_type == "execute_result" or output_type == "display_data":
            data = output.get("data", {})
            if "text/plain" in data:
                formatted["text"] = data["text/plain"]
            if "text/html" in data:
                formatted["html"] = data["text/html"][:500] + "..." if len(data.get("text/html", "")) > 500 else data.get("text/html", "")
            if "image/png" in data:
                formatted["has_image"] = True
        elif output_type == "error":
            formatted["ename"] = output.get("ename", "")
            formatted["evalue"] = output.get("evalue", "")
            formatted["traceback"] = output.get("traceback", [])

        formatted_outputs.append(formatted)

    return {
        "success": True,
        "cell_id": cell_id,
        "cell_type": cell_type,
        "source": source,
        "execution_count": execution_count,
        "outputs": formatted_outputs,
        "has_error": has_error,
        "output_count": len(outputs)
    }


def search_notebook(query: str, search_type: str = "all") -> dict:
    """
    Search for text in notebook cells.

    Use this tool when:
    - User asks "where is X defined?"
    - User asks to find something in the notebook
    - You need to locate a function, variable, or import
    - You need to find cells related to a topic

    Args:
        query: Text to search for (case-insensitive)
        search_type: What to search - "all", "code", "markdown", "outputs"

    Returns:
        Dictionary with:
        - success: Whether search succeeded
        - query: The search query
        - matches: List of matching cells with context
        - match_count: Total number of matches
        - error: Error message if failed

    Example:
        result = search_notebook("pandas")
        # Returns: {"success": True, "matches": [
        #   {"cell_id": "abc", "cell_type": "code", "line": 1, "context": "import pandas as pd"},
        # ]}
    """
    log_debug_message(f"==> search_notebook({query}, {search_type}) called from LLM")

    session = get_current_session()
    if not session:
        return {
            "success": False,
            "error": "No active session"
        }

    notebook_state = session.notebook_state
    cells = notebook_state.get("cells", [])

    query_lower = query.lower()
    matches = []

    for idx, cell in enumerate(cells):
        cell_id = cell.get("id", f"cell_{idx}")
        cell_type = cell.get("type", "code")
        source = cell.get("source", "")
        outputs = cell.get("outputs", [])

        # Skip based on search_type
        if search_type == "code" and cell_type != "code":
            continue
        if search_type == "markdown" and cell_type != "markdown":
            continue

        # Search in source
        if search_type in ["all", "code", "markdown"]:
            source_lines = source.split("\n")
            for line_num, line in enumerate(source_lines, 1):
                if query_lower in line.lower():
                    matches.append({
                        "cell_id": cell_id,
                        "cell_index": idx,
                        "cell_type": cell_type,
                        "location": "source",
                        "line_number": line_num,
                        "context": line.strip()[:200],
                        "full_line": line
                    })

        # Search in outputs
        if search_type in ["all", "outputs"] and cell_type == "code":
            for output in outputs:
                output_text = ""
                if output.get("output_type") == "stream":
                    output_text = output.get("text", "")
                elif output.get("output_type") in ["execute_result", "display_data"]:
                    data = output.get("data", {})
                    output_text = data.get("text/plain", "")
                elif output.get("output_type") == "error":
                    output_text = f"{output.get('ename', '')}: {output.get('evalue', '')}"

                if query_lower in output_text.lower():
                    # Find the matching line
                    for line in output_text.split("\n"):
                        if query_lower in line.lower():
                            matches.append({
                                "cell_id": cell_id,
                                "cell_index": idx,
                                "cell_type": cell_type,
                                "location": "output",
                                "context": line.strip()[:200]
                            })
                            break  # One match per output is enough

    return {
        "success": True,
        "query": query,
        "search_type": search_type,
        "matches": matches[:50],  # Limit to 50 matches
        "match_count": len(matches),
        "truncated": len(matches) > 50
    }
