# Master Tool List

All LLM-callable tools across the platform. Source of truth: `playground/backend/llm_tools/__init__.py`

Generated: 2026-03-07

---

## Tool Availability by Context

| Context | Tool List | Count |
|---------|-----------|-------|
| Chat Panel | `TOOL_FUNCTIONS` | 36 |
| AI Cell - Crisp | `AI_CELL_TOOLS` subset (DB-controlled) | 9 |
| AI Cell - Standard | `AI_CELL_TOOLS` | 14 |
| AI Cell - Power | `ALL_AI_CELL_TOOLS` | 19 |

---

## All Tools

### Category: Runtime Inspection (7 tools)
Live kernel state - requires running kernel.

| # | tool_name | parameters | description | module | Chat Panel | Crisp | Standard | Power |
|---|-----------|------------|-------------|--------|:---:|:---:|:---:|:---:|
| 1 | `runtime_list_variables` | (none) | List all user-defined variables in the running kernel with their types and shapes | tool_kernel_inspect.py | Y | Y | Y | Y |
| 2 | `runtime_get_variable` | name: str | Get detailed info about any variable (list, dict, object, etc.) from the running kernel | tool_kernel_inspect.py | Y | - | Y | Y |
| 3 | `runtime_get_dataframe` | name: str | Get comprehensive info about a pandas DataFrame (columns, types, stats, nulls) | tool_kernel_utils.py | Y | - | Y | Y |
| 4 | `runtime_list_functions` | (none) | List all user-defined functions in the running kernel | tool_kernel_inspect.py | Y | - | Y | Y |
| 5 | `runtime_list_imports` | (none) | List all imported modules in the running kernel | tool_kernel_inspect.py | Y | - | Y | Y |
| 6 | `runtime_kernel_status` | (none) | Get kernel state: memory usage, execution count, uptime | tool_kernel_inspect.py | Y | Y | Y | Y |
| 7 | `runtime_get_last_error` | (none) | Get the most recent error/exception with full traceback | tool_kernel_utils.py | Y | Y | Y | Y |

### Category: Notebook Cells (9 tools)
Notebook structure operations. Read tools fetch from Master API. Write tools modify notebook state.

| # | tool_name | parameters | description | module | Chat Panel | Crisp | Standard | Power |
|---|-----------|------------|-------------|--------|:---:|:---:|:---:|:---:|
| 8 | `get_notebook_overview` | detail: str = "brief" | Get overview of all cells (IDs, types, previews). Use detail="full" for complete content | tool_notebook_cells.py | Y | Y | Y | Y |
| 9 | `get_cell_content` | cell_id: str | Read a cell's source code and outputs | tool_notebook_cells.py | Y | - | Y | Y |
| 10 | `update_cell_content` | cell_id: str, new_content: str, cell_type: str? | Update a cell's content by ID. ALWAYS read cell first | tool_notebook_cells.py | Y | - | - | - |
| 11 | `delete_cell` | cell_id: str | Delete a cell by ID | tool_notebook_cells.py | Y | - | - | - |
| 12 | `multi_delete_cells` | cell_ids: List[str] | Delete multiple cells in one operation | tool_notebook_cells.py | Y | - | - | - |
| 13 | `multi_insert_cells` | cells_json: str | Insert multiple cells in one operation (JSON string) | tool_notebook_cells.py | Y | - | - | - |
| 14 | `insert_cell_after` | after_cell_id: str, content: str, cell_type: str | Insert a new cell after an existing cell | tool_notebook_cells.py | Y | - | - | - |
| 15 | `insert_cell_at_position` | position: int, content: str, cell_type: str | Insert a cell at position 0 (beginning) or end of notebook | tool_notebook_cells.py | Y | - | - | - |
| 16 | `execute_cell` | cell_id: str | Run a notebook cell and save its output | tool_notebook_cells.py | Y | - | - | - |

### Category: Code Execution (1 tool)
Run code in the user's main kernel. Affects real state.

| # | tool_name | parameters | description | module | Chat Panel | Crisp | Standard | Power |
|---|-----------|------------|-------------|--------|:---:|:---:|:---:|:---:|
| 17 | `execute_python_code` | code: str | Execute Python code in the user's kernel. CAUTION: affects real state | tool_jupyter_kernel.py | Y | - | - | - |

### Category: Sandbox Testing (5 tools)
Isolated kernel for safe experimentation. Does not affect user's work.

| # | tool_name | parameters | description | module | Chat Panel | Crisp | Standard | Power |
|---|-----------|------------|-------------|--------|:---:|:---:|:---:|:---:|
| 18 | `sandbox_execute` | code: str, timeout: int = 10 | Test code in an isolated environment before suggesting it | tool_sandbox.py | Y | Y | Y | Y |
| 19 | `sandbox_reset` | (none) | Reset sandbox kernel to clean state | tool_sandbox.py | Y | Y | Y | Y |
| 20 | `sandbox_pip_install` | packages: str | Install packages in the sandbox environment | tool_sandbox.py | - | Y | Y | Y |
| 21 | `sandbox_sync_from_main` | variable_names: List[str]? | Copy variables from main kernel to sandbox | tool_sandbox.py | Y | Y | Y | Y |
| 22 | `sandbox_status` | (none) | Check sandbox kernel status (running, memory, etc.) | tool_sandbox.py | Y | Y | Y | Y |

### Category: File Operations - Project (6 tools)
File operations scoped to user's project directory. From `tool_files.py`.

| # | tool_name | parameters | description | module | Chat Panel | Crisp | Standard | Power |
|---|-----------|------------|-------------|--------|:---:|:---:|:---:|:---:|
| 23 | `list_project_files` | path: str = "/", pattern: str = "*", recursive: bool = False | List files in the project directory | tool_files.py | Y | - | - | - |
| 24 | `file_info` | path: str | Get detailed file info (size, modified date, type) | tool_files.py | Y | - | - | - |
| 25 | `read_text_file` | path: str, max_lines: int = 200, encoding: str = "utf-8" | Read a text file from the project directory | tool_files.py | Y | - | - | Y |
| 26 | `preview_data_file` | path: str, rows: int = 10 | Preview CSV/JSON/Excel without loading entire file | tool_files.py | Y | - | - | - |
| 27 | `write_text_file` | path: str, content: str, overwrite: bool = False | Write content to a file in the project directory | tool_files.py | Y | - | - | - |
| 28 | `delete_file` | path: str, confirm: bool = False | Delete a file from the project directory | tool_files.py | Y | - | - | - |

### Category: File Utilities - Advanced (4 tools)
Advanced file operations: surgical edit, glob search, regex grep, workspace context. From `tool_file_utils.py`.

| # | tool_name | parameters | description | module | Chat Panel | Crisp | Standard | Power |
|---|-----------|------------|-------------|--------|:---:|:---:|:---:|:---:|
| 29 | `edit_file` | file_path: str, old_text: str, new_text: str | Edit a file by finding and replacing exact text | tool_file_utils.py | Y | - | - | - |
| 30 | `list_files` | pattern: str = "*", directory: str = "." | Search for files by glob pattern | tool_file_utils.py | Y | - | - | Y |
| 31 | `search_files` | pattern: str, directory: str = ".", file_glob: str = "*", ignore_case: bool = False | Regex search across file contents | tool_file_utils.py | Y | - | - | Y |
| 32 | `get_workspace_context` | directory: str = ".", file_types: str?, max_file_size: int = 10000, include_content: bool = True | Get workspace overview: file tree + contents in one call | tool_file_utils.py | Y | - | - | Y |

### Category: Package Management (6 tools)
pip operations in the user's kernel environment.

| # | tool_name | parameters | description | module | Chat Panel | Crisp | Standard | Power |
|---|-----------|------------|-------------|--------|:---:|:---:|:---:|:---:|
| 33 | `pip_install` | packages: str, upgrade: bool = False | Install Python packages in the kernel | tool_pip.py | Y | - | - | - |
| 34 | `pip_uninstall` | packages: str | Uninstall Python packages from the kernel | tool_pip.py | Y | - | - | - |
| 35 | `pip_list` | (none) | List all installed packages | tool_pip.py | Y | - | - | - |
| 36 | `pip_show` | package: str | Show info about an installed package | tool_pip.py | Y | - | - | - |
| 37 | `pip_search_installed` | query: str | Search installed packages by name | tool_pip.py | Y | - | - | - |
| 38 | `extract_missing_modules` | error_message: str | Extract missing module names from an ImportError message | tool_pip.py | Y | - | - | - |

### Category: Terminal (1 tool)
Shell command execution in the project workspace.

| # | tool_name | parameters | description | module | Chat Panel | Crisp | Standard | Power |
|---|-----------|------------|-------------|--------|:---:|:---:|:---:|:---:|
| 39 | `execute_terminal_command` | command: str, timeout: int = 30 | Execute a shell command and return output. Has a blocklist for dangerous commands | tool_terminal.py | Y | - | - | - |

### Category: Web (1 tool)
Fetch external content.

| # | tool_name | parameters | description | module | Chat Panel | Crisp | Standard | Power |
|---|-----------|------------|-------------|--------|:---:|:---:|:---:|:---:|
| 40 | `web_fetch` | url: str, save_as: str? | Fetch URL content (HTML converted to markdown, JSON, CSV). Optionally save to workspace | tool_web_fetch.py | Y | - | - | Y |

---

## Summary by Context

### Chat Panel (36 tools)
All tools EXCEPT `sandbox_pip_install` (AI Cell only — Chat Panel uses `pip_install` directly).

### AI Cell - Crisp (9 tools)
`runtime_list_variables`, `runtime_kernel_status`, `runtime_get_last_error`, `get_notebook_overview`, `sandbox_execute`, `sandbox_reset`, `sandbox_pip_install`, `sandbox_sync_from_main`, `sandbox_status`

### AI Cell - Standard (14 tools)
Crisp 9 + `runtime_get_variable`, `runtime_get_dataframe`, `runtime_list_functions`, `runtime_list_imports`, `get_cell_content`

### AI Cell - Power (19 tools)
Standard 14 + `list_files`, `search_files`, `read_text_file`, `get_workspace_context`, `web_fetch`

---

## Known Issues

### 1. Chat Panel prompt uses wrong tool names
The DB system prompt for chat_panel references names that don't match actual functions:
- `inspect_variables()` -> should be `runtime_list_variables()`
- `inspect_variable(name)` -> should be `runtime_get_variable(name)`
- `list_functions()` -> should be `runtime_list_functions()`
- `list_imports()` -> should be `runtime_list_imports()`
- `kernel_info()` -> should be `runtime_kernel_status()`
- `get_last_error()` -> should be `runtime_get_last_error()`
- `get_dataframe_info(name)` -> should be `runtime_get_dataframe(name)`
- `read_file, write_file, list_directory` -> should be `read_text_file, write_text_file, list_project_files`

### 2. Ghost tools referenced in Chat Panel prompt
These tools are mentioned in the prompt but DO NOT EXIST:
- `get_cell_outputs(cell_id)` - no such function anywhere
- `search_notebook(query)` - no such function anywhere

### 3. Undocumented tools in Chat Panel
12 tools exist in TOOL_FUNCTIONS but are NOT mentioned in the Chat Panel system prompt:
`execute_terminal_command`, `edit_file`, `list_files`, `search_files`, `get_workspace_context`, `web_fetch`, `pip_uninstall`, `pip_search_installed`, `extract_missing_modules`, `sandbox_pip_install`(N/A), `sandbox_status`, `sandbox_reset`

### 4. Duplicate file tools across two modules
`tool_files.py` and `tool_file_utils.py` have overlapping functionality:
- `read_text_file` (tool_files) vs `read_file` (tool_file_utils)
- `write_text_file` (tool_files) vs `write_file` (tool_file_utils)
- `delete_file` exists in BOTH (different implementations)
- `list_project_files` (tool_files) vs `list_files` + `list_directory` (tool_file_utils)
- `file_info` (tool_files) vs `get_workspace_context` (tool_file_utils)

### 5. Resolution: Remove tool names from system prompts
Since tools are dynamically controlled via DB tool catalog, system prompts should NOT hardcode tool names. The LLM receives tool schemas via function calling API. Prompts should contain only behavioral instructions.
