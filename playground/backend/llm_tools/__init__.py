"""
LLM Tools - Function calling tools for LLM to interact with the system
"""

from backend.llm_tools.tool_jupyter_kernel import execute_python_code
from backend.llm_tools.tool_notebook_cells import (
    get_notebook_overview,
    get_cell_content,
    update_cell_content,
    insert_cell,
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

# List of all tool functions to pass to LLM
TOOL_FUNCTIONS = [
    # Kernel execution
    execute_python_code,

    # Notebook cell operations
    get_notebook_overview,
    get_cell_content,
    update_cell_content,
    insert_cell,
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
    extract_missing_modules
]
