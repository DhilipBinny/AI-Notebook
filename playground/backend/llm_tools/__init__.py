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
from backend.llm_tools.tool_file_utils import (
    read_file,
    write_file,
    append_file,
    delete_file,
    rename_file,
    copy_file,
    list_directory,
    create_directory,
    delete_directory,
    file_exists
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
    inspect_variables,
    inspect_variable,
    list_functions,
    list_imports,
    kernel_info
)
from backend.llm_tools.tool_sandbox import (
    sandbox_execute,
    sandbox_reset,
    sandbox_sync_from_main,
    sandbox_status
)

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

    # File operations
    read_file,
    write_file,
    append_file,
    delete_file,
    rename_file,
    copy_file,
    list_directory,
    create_directory,
    delete_directory,
    file_exists,

    # Package management
    pip_install,
    pip_uninstall,
    pip_list,
    pip_show,
    pip_search_installed,
    extract_missing_modules,

    # Kernel inspection (read-only)
    inspect_variables,
    inspect_variable,
    list_functions,
    list_imports,
    kernel_info,

    # Sandbox execution (isolated testing)
    sandbox_execute,
    sandbox_reset,
    sandbox_sync_from_main,
    sandbox_status
]

# AI Cell tools - subset for inline AI cell (read-only + sandbox)
AI_CELL_TOOLS = [
    # Kernel inspection (read-only access to main kernel)
    inspect_variables,
    inspect_variable,
    list_functions,
    list_imports,
    kernel_info,

    # Sandbox execution (isolated testing environment)
    sandbox_execute,
    sandbox_reset,
    sandbox_sync_from_main,
    sandbox_status
]
