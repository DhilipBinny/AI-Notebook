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
from backend.llm_tools.tool_kernel_utils import (
    get_last_error,
    get_dataframe_info,
    get_cell_outputs,
    search_notebook
)
from backend.llm_tools.tool_web import (
    fetch_url_as_markdown,
    get_library_docs
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

    # Kernel inspection (read-only)
    inspect_variables,
    inspect_variable,
    list_functions,
    list_imports,
    kernel_info,

    # Kernel utilities (debugging & data inspection)
    get_last_error,
    get_dataframe_info,
    get_cell_outputs,
    search_notebook,

    # Sandbox execution (isolated testing)
    sandbox_execute,
    sandbox_reset,
    sandbox_sync_from_main,
    sandbox_status,

    # Web tools (documentation & URL fetching)
    fetch_url_as_markdown,
    get_library_docs
]

# AI Cell tools - subset for inline AI cell (read-only + sandbox)
AI_CELL_TOOLS = [
    # Kernel inspection (read-only access to main kernel)
    inspect_variables,
    inspect_variable,
    list_functions,
    list_imports,
    kernel_info,

    # Kernel utilities (debugging & data inspection)
    get_last_error,
    get_dataframe_info,
    get_cell_outputs,
    search_notebook,

    # Sandbox execution (isolated testing environment)
    sandbox_execute,
    sandbox_reset,
    sandbox_sync_from_main,
    sandbox_status
]
