"""
Tool Schemas - Shared tool definition building utilities

Provides unified functions for converting Python function metadata
into provider-specific tool/function schemas.

Each LLM provider has a different format for tool definitions:
- Anthropic: {"name", "description", "input_schema": {...}}
- Gemini: FunctionDeclaration with Schema
- OpenAI: {"type": "function", "function": {"name", "description", "parameters": {...}}}
"""

from typing import List, Dict, Any, Callable


def parse_function_docstring(func: Callable) -> tuple[str, Dict[str, str]]:
    """
    Parse a function's docstring to extract description and parameter descriptions.

    Args:
        func: The function to parse

    Returns:
        Tuple of (description, {param_name: param_description})
    """
    func_doc = func.__doc__ or ""
    doc_lines = func_doc.strip().split('\n')

    description = ""
    param_descriptions = {}
    current_section = None

    for line in doc_lines:
        line = line.strip()
        if line.lower().startswith('args:'):
            current_section = 'args'
            continue
        elif line.lower().startswith('returns:'):
            current_section = 'returns'
            continue
        elif line.lower().startswith('example:'):
            current_section = 'example'
            continue

        if current_section is None and line:
            description += line + " "
        elif current_section == 'args' and ':' in line:
            param_name = line.split(':')[0].strip()
            param_desc = ':'.join(line.split(':')[1:]).strip()
            param_descriptions[param_name] = param_desc

    return description.strip(), param_descriptions


def get_param_required_list(func: Callable, param_names: List[str]) -> List[str]:
    """
    Determine which parameters are required (no default value).

    Args:
        func: The function to analyze
        param_names: List of parameter names to check

    Returns:
        List of required parameter names
    """
    defaults = func.__defaults__ or ()
    code = func.__code__
    num_params = code.co_argcount
    num_defaults = len(defaults)
    params_without_defaults = num_params - num_defaults

    all_param_names = code.co_varnames[:num_params]
    required = []

    for param_name in param_names:
        if param_name in all_param_names:
            param_index = list(all_param_names).index(param_name)
            if param_index < params_without_defaults:
                required.append(param_name)

    return required


def python_type_to_json_type(python_type) -> str:
    """
    Map Python type annotations to JSON schema types.

    Args:
        python_type: Python type annotation

    Returns:
        JSON schema type string
    """
    type_mapping = {
        int: "integer",
        float: "number",
        bool: "boolean",
        str: "string",
    }
    return type_mapping.get(python_type, "string")


def build_json_schema_properties(func: Callable) -> tuple[Dict[str, Any], List[str]]:
    """
    Build JSON schema properties and required list from function annotations.

    Args:
        func: The function to analyze

    Returns:
        Tuple of (properties_dict, required_list)
    """
    annotations = func.__annotations__
    _, param_descriptions = parse_function_docstring(func)

    properties = {}
    param_names = []

    for param_name, param_type in annotations.items():
        if param_name == 'return':
            continue

        json_type = python_type_to_json_type(param_type)
        properties[param_name] = {
            "type": json_type,
            "description": param_descriptions.get(param_name, f"The {param_name} parameter")
        }
        param_names.append(param_name)

    required = get_param_required_list(func, param_names)

    return properties, required


# =============================================================================
# Provider-Specific Builders
# =============================================================================

def build_anthropic_tool(func: Callable) -> Dict[str, Any]:
    """
    Build Anthropic tool definition from a Python function.

    Args:
        func: The function to convert

    Returns:
        Anthropic tool definition dict
    """
    description, _ = parse_function_docstring(func)
    properties, required = build_json_schema_properties(func)

    return {
        "name": func.__name__,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }


def build_anthropic_tools(functions: List[Callable]) -> List[Dict[str, Any]]:
    """
    Build list of Anthropic tool definitions from functions.

    Args:
        functions: List of functions to convert

    Returns:
        List of Anthropic tool definition dicts
    """
    return [build_anthropic_tool(func) for func in functions]


def build_openai_tool(func: Callable) -> Dict[str, Any]:
    """
    Build OpenAI tool definition from a Python function.

    Args:
        func: The function to convert

    Returns:
        OpenAI tool definition dict
    """
    description, _ = parse_function_docstring(func)
    properties, required = build_json_schema_properties(func)

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }


def build_openai_tools(functions: List[Callable]) -> List[Dict[str, Any]]:
    """
    Build list of OpenAI tool definitions from functions.

    Args:
        functions: List of functions to convert

    Returns:
        List of OpenAI tool definition dicts
    """
    return [build_openai_tool(func) for func in functions]


def build_gemini_tool_schema(func: Callable) -> Dict[str, Any]:
    """
    Build Gemini-compatible tool schema from a Python function.

    Returns a dict that can be passed to types.FunctionDeclaration().
    Gemini uses: types.FunctionDeclaration(name=..., description=..., parameters={...})

    Args:
        func: The function to convert

    Returns:
        Dict with name, description, and parameters for FunctionDeclaration
    """
    description, _ = parse_function_docstring(func)
    properties, required = build_json_schema_properties(func)

    return {
        "name": func.__name__,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }


def build_gemini_tool_schemas(functions: List[Callable]) -> List[Dict[str, Any]]:
    """
    Build list of Gemini tool schemas from functions.

    Args:
        functions: List of functions to convert

    Returns:
        List of schema dicts ready for types.FunctionDeclaration(**schema)
    """
    return [build_gemini_tool_schema(func) for func in functions]
