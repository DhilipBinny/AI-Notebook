"""
Kernel Inspection Tools - Allows AI to inspect the notebook's runtime state

These tools provide read-only access to the main kernel's state:
- Variables (names, types, shapes, values)
- User-defined functions
- Imported modules
- Kernel info (memory, execution count)

Uses session-scoped kernel from session_manager.
"""

from typing import Optional
from backend.session_manager import get_current_session
from backend.utils.util_func import log_debug_message


def _get_session_kernel(auto_start: bool = True):
    """Get kernel from current session, or fallback to global kernel.

    Args:
        auto_start: If True, automatically start the kernel if not running

    Returns:
        The kernel instance
    """
    session = get_current_session()
    if session:
        kernel = session.kernel
        # Auto-start kernel if not running
        if auto_start and not kernel.is_alive():
            log_debug_message("[Kernel Inspect] Auto-starting kernel for session")
            kernel.start()
        return kernel
    # Fallback to global kernel
    from backend.kernel_manager import get_kernel
    kernel = get_kernel()
    if auto_start and not kernel.is_alive():
        log_debug_message("[Kernel Inspect] Auto-starting global kernel")
        kernel.start()
    return kernel


def inspect_variables() -> dict:
    """
    List all user-defined variables in the main kernel with their types and shapes.

    Use this tool when you need to:
    - See what variables are available in the notebook
    - Understand the data types and shapes of variables
    - Get an overview of the current kernel state
    - Find variable names to reference in your response

    Returns:
        Dictionary with:
        - success: Whether the inspection succeeded
        - variables: List of variable info dicts with name, type, shape, size, preview
        - error: Error message if failed

    Example:
        result = inspect_variables()
        # Returns: {"success": True, "variables": [
        #   {"name": "df", "type": "DataFrame", "shape": "(1000, 5)", "size": "~40KB", "preview": "..."},
        #   {"name": "x", "type": "int", "shape": null, "size": "28 bytes", "preview": "42"},
        # ]}
    """
    log_debug_message("==> inspect_variables() called from LLM")

    kernel = _get_session_kernel()

    if not kernel.is_alive():
        return {
            "success": False,
            "variables": [],
            "error": "Kernel is not running. No variables available."
        }

    # Code to inspect all user variables
    inspect_code = '''
import sys
import json

def _get_var_info(name, obj):
    """Get info about a variable"""
    info = {
        "name": name,
        "type": type(obj).__name__,
        "shape": None,
        "size": None,
        "preview": None
    }

    # Get shape for arrays/dataframes
    if hasattr(obj, 'shape'):
        info["shape"] = str(obj.shape)
    elif hasattr(obj, '__len__') and not isinstance(obj, (str, bytes)):
        try:
            info["shape"] = f"({len(obj)},)"
        except:
            pass

    # Get size
    try:
        size_bytes = sys.getsizeof(obj)
        if size_bytes < 1024:
            info["size"] = f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            info["size"] = f"~{size_bytes // 1024}KB"
        else:
            info["size"] = f"~{size_bytes // (1024*1024)}MB"
    except:
        pass

    # Get preview (truncated string representation)
    try:
        preview = repr(obj)
        if len(preview) > 100:
            preview = preview[:100] + "..."
        info["preview"] = preview
    except:
        info["preview"] = "<unable to preview>"

    return info

# Get all user variables (exclude builtins, modules, and private vars)
_user_vars = []
_skip_names = {'In', 'Out', 'get_ipython', 'exit', 'quit', '_', '__', '___',
               '_i', '_ii', '_iii', '_oh', '_dh', '_sh', '_getvar', '_get_var_info',
               '_user_vars', '_skip_names', '_skip_types', 'json', 'sys'}
_skip_types = {'module', 'function', 'builtin_function_or_method', 'type', 'method'}

for _name in dir():
    if _name.startswith('_'):
        continue
    if _name in _skip_names:
        continue
    try:
        _obj = eval(_name)
        _type_name = type(_obj).__name__
        if _type_name in _skip_types:
            continue
        _user_vars.append(_get_var_info(_name, _obj))
    except:
        pass

# Sort by name
_user_vars.sort(key=lambda x: x['name'])
print(json.dumps(_user_vars))
'''

    result = kernel.execute(inspect_code)

    if not result["success"]:
        return {
            "success": False,
            "variables": [],
            "error": str(result.get("error", "Failed to inspect variables"))
        }

    # Parse the output
    try:
        output_text = ""
        for output in result.get("outputs", []):
            if output.get("type") == "stream":
                output_text += output.get("text", "")

        import json
        variables = json.loads(output_text.strip())

        return {
            "success": True,
            "variables": variables,
            "count": len(variables)
        }
    except Exception as e:
        return {
            "success": False,
            "variables": [],
            "error": f"Failed to parse variable info: {str(e)}"
        }


def inspect_variable(name: str) -> dict:
    """
    Get detailed info about ANY variable (list, dict, object, etc.).

    WHEN TO USE THIS TOOL:
    - To examine a list, dict, or custom object
    - To see object attributes and methods
    - To get value of a variable
    - For general variable inspection

    WHEN NOT TO USE THIS TOOL:
    - For pandas DataFrame → use get_dataframe_info(name) instead
      (it provides columns, dtypes, null counts, describe stats)

    Args:
        name: Variable name to inspect

    Returns:
        Dictionary with name, type, value/sample, shape, attributes

    Example:
        inspect_variable("my_list")  → info about a list
        inspect_variable("config")   → info about a dict
    """
    log_debug_message(f"==> inspect_variable({name}) called from LLM")

    kernel = _get_session_kernel()

    if not kernel.is_alive():
        return {
            "success": False,
            "error": "Kernel is not running."
        }

    # Code to inspect a specific variable
    inspect_code = f'''
import json
import sys

_var_name = {repr(name)}

if _var_name not in dir():
    print(json.dumps({{"error": f"Variable '{{_var_name}}' not found"}}))
else:
    _obj = eval(_var_name)
    _info = {{
        "name": _var_name,
        "type": type(_obj).__name__,
        "value": None,
        "shape": None,
        "dtype": None,
        "columns": None,
        "sample": None,
        "attributes": []
    }}

    # Get shape
    if hasattr(_obj, 'shape'):
        _info["shape"] = str(_obj.shape)
    elif hasattr(_obj, '__len__') and not isinstance(_obj, (str, bytes)):
        try:
            _info["shape"] = f"length: {{len(_obj)}}"
        except:
            pass

    # Get dtype for arrays/series
    if hasattr(_obj, 'dtype'):
        _info["dtype"] = str(_obj.dtype)
    elif hasattr(_obj, 'dtypes'):
        try:
            _info["dtype"] = str(_obj.dtypes.to_dict())
        except:
            pass

    # Get columns for DataFrames
    if hasattr(_obj, 'columns'):
        try:
            _info["columns"] = list(_obj.columns)[:50]  # Limit to 50 columns
        except:
            pass

    # Get value (small objects) or sample (large objects)
    try:
        _size = sys.getsizeof(_obj)
        if _size < 10000:  # Small object, show full value
            _val = repr(_obj)
            if len(_val) > 2000:
                _val = _val[:2000] + "... (truncated)"
            _info["value"] = _val
        else:
            # Large object, show sample
            if hasattr(_obj, 'head'):
                # DataFrame/Series
                _info["sample"] = str(_obj.head(5))
            elif hasattr(_obj, '__iter__') and not isinstance(_obj, (str, bytes, dict)):
                # List/array - show first few items
                try:
                    _items = list(_obj)[:5]
                    _info["sample"] = repr(_items) + f"... ({{len(_obj)}} total)"
                except:
                    _info["sample"] = repr(_obj)[:500] + "..."
            elif isinstance(_obj, dict):
                # Dict - show first few items
                _items = dict(list(_obj.items())[:5])
                _info["sample"] = repr(_items) + f"... ({{len(_obj)}} keys total)"
            else:
                _info["value"] = repr(_obj)[:2000] + "... (truncated)"
    except Exception as e:
        _info["value"] = f"<unable to get value: {{e}}>"

    # Get interesting attributes (non-private, non-method)
    try:
        _attrs = []
        for _attr in dir(_obj):
            if _attr.startswith('_'):
                continue
            try:
                _attr_val = getattr(_obj, _attr)
                if not callable(_attr_val):
                    _attrs.append(_attr)
            except:
                pass
        _info["attributes"] = _attrs[:20]  # Limit to 20
    except:
        pass

    print(json.dumps(_info))
'''

    result = kernel.execute(inspect_code)

    if not result["success"]:
        return {
            "success": False,
            "error": str(result.get("error", "Failed to inspect variable"))
        }

    # Parse the output
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
            "error": f"Failed to parse variable info: {str(e)}"
        }


def list_functions() -> dict:
    """
    List all user-defined functions in the main kernel.

    Use this tool when you need to:
    - See what functions the user has defined
    - Understand available utility functions
    - Check function signatures and docstrings

    Returns:
        Dictionary with:
        - success: Whether the inspection succeeded
        - functions: List of function info dicts with name, args, docstring, source
        - error: Error message if failed

    Example:
        result = list_functions()
        # Returns: {"success": True, "functions": [
        #   {"name": "process_data", "args": "(x, y=10)", "docstring": "Process data...", "source": "def process_data..."},
        # ]}
    """
    log_debug_message("==> list_functions() called from LLM")

    kernel = _get_session_kernel()

    if not kernel.is_alive():
        return {
            "success": False,
            "functions": [],
            "error": "Kernel is not running."
        }

    # Code to list user-defined functions
    inspect_code = '''
import json
import inspect

_skip_names = {'get_ipython', 'exit', 'quit'}
_functions = []

for _name in dir():
    if _name.startswith('_'):
        continue
    if _name in _skip_names:
        continue
    try:
        _obj = eval(_name)
        if callable(_obj) and hasattr(_obj, '__code__'):
            # It's a user-defined function
            _info = {
                "name": _name,
                "args": None,
                "docstring": None,
                "source": None
            }

            # Get signature
            try:
                _sig = inspect.signature(_obj)
                _info["args"] = str(_sig)
            except:
                pass

            # Get docstring
            if _obj.__doc__:
                _doc = _obj.__doc__.strip()
                if len(_doc) > 200:
                    _doc = _doc[:200] + "..."
                _info["docstring"] = _doc

            # Get source (if available and not too long)
            try:
                _src = inspect.getsource(_obj)
                if len(_src) > 500:
                    _src = _src[:500] + "\\n... (truncated)"
                _info["source"] = _src
            except:
                pass

            _functions.append(_info)
    except:
        pass

_functions.sort(key=lambda x: x['name'])
print(json.dumps(_functions))
'''

    result = kernel.execute(inspect_code)

    if not result["success"]:
        return {
            "success": False,
            "functions": [],
            "error": str(result.get("error", "Failed to list functions"))
        }

    # Parse the output
    try:
        output_text = ""
        for output in result.get("outputs", []):
            if output.get("type") == "stream":
                output_text += output.get("text", "")

        import json
        functions = json.loads(output_text.strip())

        return {
            "success": True,
            "functions": functions,
            "count": len(functions)
        }
    except Exception as e:
        return {
            "success": False,
            "functions": [],
            "error": f"Failed to parse function info: {str(e)}"
        }


def list_imports() -> dict:
    """
    List all imported modules in the main kernel.

    Use this tool when you need to:
    - See what libraries are already imported
    - Check import aliases (e.g., pd, np, plt)
    - Know which packages are available without re-importing

    Returns:
        Dictionary with:
        - success: Whether the inspection succeeded
        - imports: List of import info dicts with name, alias, module_name, version
        - error: Error message if failed

    Example:
        result = list_imports()
        # Returns: {"success": True, "imports": [
        #   {"name": "pd", "module_name": "pandas", "version": "2.0.0"},
        #   {"name": "np", "module_name": "numpy", "version": "1.24.0"},
        # ]}
    """
    log_debug_message("==> list_imports() called from LLM")

    kernel = _get_session_kernel()

    if not kernel.is_alive():
        return {
            "success": False,
            "imports": [],
            "error": "Kernel is not running."
        }

    # Code to list imported modules
    inspect_code = '''
import json
import sys

_skip_modules = {'builtins', 'sys', 'json', '__builtins__', 'IPython', 'ipykernel'}
_imports = []

for _name in dir():
    if _name.startswith('_'):
        continue
    try:
        _obj = eval(_name)
        if hasattr(_obj, '__file__') or (hasattr(_obj, '__name__') and _obj.__name__ in sys.modules):
            # It's a module
            _module_name = getattr(_obj, '__name__', _name)

            if _module_name in _skip_modules or _module_name.startswith('_'):
                continue
            if _module_name.startswith('IPython') or _module_name.startswith('ipykernel'):
                continue

            _info = {
                "name": _name,  # The alias used (e.g., "pd")
                "module_name": _module_name,  # Full module name (e.g., "pandas")
                "version": None
            }

            # Try to get version
            try:
                if hasattr(_obj, '__version__'):
                    _info["version"] = str(_obj.__version__)
                elif hasattr(_obj, 'version'):
                    _info["version"] = str(_obj.version)
            except:
                pass

            _imports.append(_info)
    except:
        pass

_imports.sort(key=lambda x: x['name'])
print(json.dumps(_imports))
'''

    result = kernel.execute(inspect_code)

    if not result["success"]:
        return {
            "success": False,
            "imports": [],
            "error": str(result.get("error", "Failed to list imports"))
        }

    # Parse the output
    try:
        output_text = ""
        for output in result.get("outputs", []):
            if output.get("type") == "stream":
                output_text += output.get("text", "")

        import json
        imports = json.loads(output_text.strip())

        return {
            "success": True,
            "imports": imports,
            "count": len(imports)
        }
    except Exception as e:
        return {
            "success": False,
            "imports": [],
            "error": f"Failed to parse import info: {str(e)}"
        }


def kernel_info() -> dict:
    """
    Get information about the main kernel's state.

    Use this tool when you need to:
    - Check if the kernel is running
    - See memory usage
    - Get execution count
    - Understand kernel configuration

    Returns:
        Dictionary with:
        - success: Whether the inspection succeeded
        - alive: Whether the kernel is running
        - execution_count: Number of code executions so far
        - memory_used: Memory usage string
        - python_version: Python version
        - working_directory: Current working directory
        - error: Error message if failed

    Example:
        result = kernel_info()
        # Returns: {"success": True, "alive": True, "execution_count": 15, "memory_used": "~256MB", ...}
    """
    log_debug_message("==> kernel_info() called from LLM")

    kernel = _get_session_kernel()

    info = {
        "success": True,
        "alive": kernel.is_alive(),
        "execution_count": kernel.execution_count if kernel else 0,
        "memory_used": None,
        "python_version": None,
        "working_directory": None
    }

    if not kernel.is_alive():
        info["message"] = "Kernel is not running. Start the kernel to see more info."
        return info

    # Get additional info from kernel
    inspect_code = '''
import json
import sys
import os
import psutil

_info = {
    "python_version": sys.version.split()[0],
    "working_directory": os.getcwd(),
    "memory_used": None
}

# Get memory usage
try:
    _process = psutil.Process(os.getpid())
    _mem = _process.memory_info().rss
    if _mem < 1024 * 1024:
        _info["memory_used"] = f"~{_mem // 1024}KB"
    elif _mem < 1024 * 1024 * 1024:
        _info["memory_used"] = f"~{_mem // (1024*1024)}MB"
    else:
        _info["memory_used"] = f"~{_mem // (1024*1024*1024)}GB"
except:
    _info["memory_used"] = "unknown"

print(json.dumps(_info))
'''

    result = kernel.execute(inspect_code)

    if result["success"]:
        try:
            output_text = ""
            for output in result.get("outputs", []):
                if output.get("type") == "stream":
                    output_text += output.get("text", "")

            import json
            kernel_state = json.loads(output_text.strip())
            info.update(kernel_state)
        except:
            pass

    return info
