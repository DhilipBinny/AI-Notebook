"""
LLM Tools - Function calling tools for LLM to interact with the system
"""

from backend.llm_tools.tool_jupyter_kernel import execute_python_code
from backend.llm_tools.tool_notebook_cells import (
    get_notebook_overview,
    get_cell_content,
    update_cell_content,
    delete_cell,
    multi_delete_cells,
    multi_insert_cells,
    insert_cell_after,
    insert_cell_at_position,
    execute_cell
)
from backend.llm_tools.tool_files import (
    list_project_files,
    file_info,
    read_text_file,
    preview_data_file,
    write_text_file,
    delete_file
)
from backend.llm_tools.tool_pip import (
    pip_install,
    pip_uninstall,
    pip_list,
    pip_show,
    pip_search_installed,
    extract_missing_modules
)
from backend.llm_tools.tool_kernel_inspect import (
    runtime_list_variables,
    runtime_get_variable,
    runtime_list_functions,
    runtime_list_imports,
    runtime_kernel_status
)
from backend.llm_tools.tool_sandbox import (
    sandbox_execute,
    sandbox_reset,
    sandbox_pip_install,
    sandbox_sync_from_main,
    sandbox_status
)
from backend.llm_tools.tool_kernel_utils import (
    runtime_get_last_error,
    runtime_get_dataframe
)
from backend.llm_tools.tool_terminal import execute_terminal_command
from backend.llm_tools.tool_file_utils import (
    edit_file,
    list_files,
    search_files,
    get_workspace_context,
)
from backend.llm_tools.tool_web_fetch import web_fetch

# List of all tool functions to pass to LLM (Chat Panel - full access)
TOOL_FUNCTIONS = [
    # Kernel execution
    execute_python_code,

    # Notebook cell operations (use cell_id for reliable targeting)
    get_notebook_overview,
    get_cell_content,
    update_cell_content,
    delete_cell,
    multi_delete_cells,
    multi_insert_cells,
    insert_cell_after,
    insert_cell_at_position,
    execute_cell,

    # File operations (project directory)
    list_project_files,
    file_info,
    read_text_file,
    preview_data_file,
    write_text_file,
    delete_file,

    # Package management
    pip_install,
    pip_uninstall,
    pip_list,
    pip_show,
    pip_search_installed,
    extract_missing_modules,

    # Runtime Inspection (live kernel state - requires running kernel)
    runtime_list_variables,
    runtime_get_variable,
    runtime_get_dataframe,
    runtime_list_functions,
    runtime_list_imports,
    runtime_kernel_status,
    runtime_get_last_error,

    # Sandbox Testing (isolated kernel for safe experimentation)
    sandbox_execute,
    sandbox_reset,
    sandbox_sync_from_main,
    sandbox_status,

    # Terminal (shell command execution)
    execute_terminal_command,

    # Advanced file utilities (edit, find, grep, context)
    edit_file,
    list_files,
    search_files,
    get_workspace_context,

    # Web
    web_fetch,
]

# AI Cell tools - subset for inline AI cell (read-only + sandbox)
# This is the "Standard" mode tool set (14 tools)
AI_CELL_TOOLS = [
    # Runtime Inspection (live kernel state - requires running kernel)
    runtime_list_variables,
    runtime_get_variable,
    runtime_get_dataframe,
    runtime_list_functions,
    runtime_list_imports,
    runtime_kernel_status,
    runtime_get_last_error,

    # Notebook Inspection (fetches from Master API → S3)
    get_notebook_overview,
    get_cell_content,

    # Sandbox Testing (isolated kernel for safe experimentation)
    sandbox_execute,
    sandbox_reset,
    sandbox_pip_install,  # Install packages in sandbox for testing
    sandbox_sync_from_main,
    sandbox_status,
]

# All AI Cell tools superset (Standard 14 + Power 5 = 19 tools)
# Used when mode-based filtering is active — providers build from this list
ALL_AI_CELL_TOOLS = AI_CELL_TOOLS + [
    # File utilities (Power mode only)
    list_files,
    search_files,
    read_text_file,
    get_workspace_context,

    # Web fetching (Power mode only)
    web_fetch,
]

# Name-to-function map for all AI Cell tools (for mode-based filtering)
ALL_AI_CELL_TOOL_MAP = {func.__name__: func for func in ALL_AI_CELL_TOOLS}
