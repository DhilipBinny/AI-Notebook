"""
Notebook Cell Tools - Allows LLM to read and edit notebook cells

These tools fetch notebook data from Master API (single source of truth in S3).
The project_id is obtained from the current session.

CELL IDENTIFICATION:
- Each cell has a unique, stable cell_id (e.g., "cell-a1b2c3d4")
- Cell IDs do NOT change when other cells are inserted/deleted
- Always use cell_id for reliable cell targeting
- Use get_notebook_overview() to see all cell IDs

LAZY LOAD ARCHITECTURE:
- No pre-sync needed
- Tools call Master API on-demand
- Master API reads from S3
- Frontend must save before chat for LLM to see changes
"""

import httpx
from typing import List, Dict, Any
from typing import Optional
from backend.session_manager import get_current_session
from backend.utils.util_func import log_debug_message
import backend.config as cfg


def _get_project_id() -> Optional[str]:
    """Get project_id from current session"""
    session = get_current_session()
    if session:
        # session_id is the project_id (set by master API)
        return session.session_id
    return None


def _get_session_kernel():
    """Get kernel from current session, or None if no session"""
    session = get_current_session()
    if session:
        return session.kernel
    # Fallback to global kernel
    from backend.kernel_manager import get_kernel
    return get_kernel()


def _call_master_api(method: str, endpoint: str, json_data: dict = None) -> dict:
    """
    Make a synchronous call to Master API.

    Args:
        method: HTTP method (GET, PUT, POST)
        endpoint: API endpoint path (e.g., /internal/notebook/{id}/cells)
        json_data: Optional JSON body for PUT/POST

    Returns:
        Response JSON as dict
    """
    url = f"{cfg.MASTER_API_URL}{endpoint}"
    headers = {"X-Internal-Secret": cfg.INTERNAL_SECRET}

    log_debug_message(f"==> Master API call: {method} {url}")

    try:
        with httpx.Client(timeout=30) as client:
            if method == "GET":
                response = client.get(url, headers=headers)
            elif method == "PUT":
                response = client.put(url, headers=headers, json=json_data or {})
            elif method == "POST":
                response = client.post(url, headers=headers, json=json_data or {})
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Master API returned {response.status_code}: {response.text}"
                }

            return response.json()
    except httpx.TimeoutException:
        return {"success": False, "error": "Master API request timed out"}
    except Exception as e:
        log_debug_message(f"Master API error: {e}")
        return {"success": False, "error": str(e)}


def get_notebook_overview(detail: str = "brief") -> dict:
    """
    Get an overview of all cells in the current notebook.

    IMPORTANT: Always call this first before editing cells to get their cell_id values.
    Cell IDs are stable identifiers that don't change when cells are inserted/deleted.

    Args:
        detail: Level of detail to return:
            - "brief" (default): Cell IDs, types, and 100-char preview. Fast. Use for finding cells.
            - "full": Complete cell contents + outputs. Use when you need to understand the entire notebook.

    WHEN TO USE "brief" (default):
    - Finding cell IDs before editing
    - Quick look at notebook structure
    - User says "update cell 3" → find the cell_id

    WHEN TO USE "full":
    - User asks "analyze my notebook" or "summarize what I've done"
    - Need to understand full context of notebook
    - Debugging issues across multiple cells

    Returns:
        Dictionary with:
        - total_cells: Number of cells in notebook
        - detail: The detail level used
        - cells: List of cell info:
            - id: Unique cell identifier (use this for editing!)
            - cell_number: Position number (1-based, matches what user sees)
            - type: "code" or "markdown"
            - preview: First 100 chars (brief mode)
            - content: Full cell content (full mode)
            - outputs: Cell outputs if any (full mode, code cells only)

    Example:
        get_notebook_overview()  → quick view with cell IDs
        get_notebook_overview(detail="full")  → full notebook context
    """
    log_debug_message(f"==> get_notebook_overview(detail={detail}) called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "total_cells": 0,
            "cells": [],
            "detail": detail,
            "message": "No active session - cannot determine project"
        }

    # For brief mode, use the existing endpoint
    if detail == "brief":
        result = _call_master_api("GET", f"/internal/notebook/{project_id}/cells")

        if "error" in result and result.get("success") == False:
            return {
                "total_cells": 0,
                "cells": [],
                "detail": detail,
                "message": result.get("error", "Failed to fetch notebook")
            }

        result["detail"] = detail
        return result

    # For full mode, get complete cell contents
    result = _call_master_api("GET", f"/internal/notebook/{project_id}/cells/full")

    if "error" in result and result.get("success") == False:
        # Fallback: try to build full view from individual cells
        brief_result = _call_master_api("GET", f"/internal/notebook/{project_id}/cells")
        if brief_result.get("success") == False:
            return {
                "total_cells": 0,
                "cells": [],
                "detail": detail,
                "message": result.get("error", "Failed to fetch notebook")
            }

        # Build full context from brief data
        cells_full = []
        for cell in brief_result.get("cells", []):
            cell_detail = _call_master_api("GET", f"/internal/notebook/{project_id}/cell/by-id/{cell['id']}")
            if cell_detail.get("success", True):
                cells_full.append({
                    "id": cell["id"],
                    "cell_number": cell.get("cell_number"),
                    "type": cell.get("type"),
                    "content": cell_detail.get("content", cell.get("preview", "")),
                    "outputs": cell_detail.get("outputs", []) if cell.get("type") == "code" else None
                })
            else:
                cells_full.append(cell)

        return {
            "total_cells": len(cells_full),
            "cells": cells_full,
            "detail": detail
        }

    result["detail"] = detail
    return result


def get_cell_content(cell_id: str) -> dict:
    """
    Read a cell's SOURCE CODE (what the user wrote).

    WHEN TO USE THIS TOOL:
    - To read the code/markdown in a cell before editing it
    - User says "look at cell 3" → get the source
    - Before calling update_cell_content() to modify a cell

    WHEN NOT TO USE THIS TOOL:
    - To see cell execution output → use get_cell_outputs(cell_id)

    KEY DIFFERENCE:
    - get_cell_content() → returns SOURCE (the code/markdown)
    - get_cell_outputs() → returns OUTPUT (execution results)

    Args:
        cell_id: The cell's unique ID (get from get_notebook_overview())

    Returns:
        Dictionary with cell_id, cell_number, type, content, output

    Example:
        1. get_notebook_overview() → find cell_id for "cell 3"
        2. get_cell_content(cell_id) → read the source code
        3. update_cell_content(cell_id, improved_code) → edit it
    """
    log_debug_message(f"==> get_cell_content({cell_id}) called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "success": False,
            "error": "No active session - cannot determine project"
        }

    return _call_master_api("GET", f"/internal/notebook/{project_id}/cell/by-id/{cell_id}")


def update_cell_content(cell_id: str, new_content: str, cell_type: Optional[str] = None) -> dict:
    """
    Update the content of a specific cell by its unique ID.

    Use this tool when you need to:
    - Improve or fix code in a cell
    - Add documentation or comments
    - Refactor functions
    - Update markdown content
    - Fix bugs or add error handling

    Args:
        cell_id: The unique cell identifier (e.g., "cell-a1b2c3d4").
                 Get this from get_notebook_overview().
        new_content: The new content to replace the cell's current content
        cell_type: Optional. Change cell type ("code" or "markdown"). If not provided, keeps existing type.

    Returns:
        Dictionary with:
        - success: Whether the update succeeded
        - cell_id: The cell's unique identifier
        - cell_number: Position number (1-based, matches what user sees)
        - old_content: Previous content (for reference)
        - new_content: Updated content
        - type: Cell type after update
        - error: Error message if update failed

    Example:
        1. First call get_notebook_overview() to find the cell_id
        2. Then: update_cell_content("cell-a1b2c3d4", "def improved_function():\\n    ...")
    """
    log_debug_message(f"==> update_cell_content({cell_id}) called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "success": False,
            "error": "No active session - cannot determine project"
        }

    payload = {"content": new_content}
    if cell_type:
        payload["cell_type"] = cell_type

    return _call_master_api("PUT", f"/internal/notebook/{project_id}/cell/by-id/{cell_id}", payload)


def delete_cell(cell_id: str) -> dict:
    """
    Delete a cell from the notebook by its unique ID.

    Use this tool when you need to:
    - Remove duplicate or redundant cells
    - Clean up unused code or markdown
    - Delete cells that are no longer needed
    - Remove cells with errors that should be rewritten

    IMPORTANT: This action cannot be undone. The cell and its contents
    will be permanently removed.

    Args:
        cell_id: The unique cell identifier (e.g., "cell-a1b2c3d4").
                 Get this from get_notebook_overview().

    Returns:
        Dictionary with:
        - success: Whether the deletion succeeded
        - deleted_cell_id: The ID of the deleted cell
        - deleted_cell_type: Type of the deleted cell (code/markdown)
        - deleted_from_position: Position where cell was deleted (1-based)
        - total_cells: New total number of cells
        - error: Error message if deletion failed

    Example:
        1. First call get_notebook_overview() to find the cell_id
        2. Then: delete_cell("cell-a1b2c3d4")
    """
    log_debug_message(f"==> delete_cell({cell_id}) called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "success": False,
            "error": "No active session - cannot determine project"
        }

    return _call_master_api("DELETE", f"/internal/notebook/{project_id}/cell/by-id/{cell_id}")


def multi_delete_cells(cell_ids: List[str]) -> dict:
    """
    Delete multiple cells from the notebook in one operation.

    Use this tool when you need to:
    - Remove multiple cells at once (more efficient than calling delete_cell multiple times)
    - Clean up several unused or redundant cells
    - Bulk delete cells during notebook restructuring

    IMPORTANT: This action cannot be undone. All specified cells will be permanently removed.

    Args:
        cell_ids: List of cell IDs to delete (e.g., ["cell-a1b2c3d4", "cell-e5f6g7h8"]).
                  Get these from get_notebook_overview().

    Returns:
        Dictionary with:
        - success: Whether the operation succeeded
        - total_requested: Number of cells requested to delete
        - total_deleted: Number of cells actually deleted
        - total_cells: New total number of cells in notebook
        - results: List of results for each cell (success/failure details)
        - message: Summary message

    Example:
        1. First call get_notebook_overview() to find the cell_ids
        2. Then: multi_delete_cells(["cell-a1b2c3d4", "cell-e5f6g7h8", "cell-i9j0k1l2"])
    """
    log_debug_message(f"==> multi_delete_cells({len(cell_ids)} cells) called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "success": False,
            "error": "No active session - cannot determine project"
        }

    payload = {"cell_ids": cell_ids}
    return _call_master_api("POST", f"/internal/notebook/{project_id}/cells/batch-delete", payload)


def multi_insert_cells(cells_json: str) -> dict:
    """
    Insert multiple cells into the notebook in one operation.

    Use this tool when you need to:
    - Add multiple markdown explanations throughout the notebook
    - Insert several code cells at once
    - Bulk add documentation cells
    - Restructure the notebook with multiple new cells

    This is much more efficient than calling insert_cell_after multiple times.

    Args:
        cells_json: JSON string containing a list of cell specifications.
                    Each item must have:
                    - after_cell_id: The cell_id after which to insert
                    - content: The content of the new cell
                    - cell_type: "code" or "markdown"

    Returns:
        Dictionary with:
        - success: Whether the operation succeeded
        - total_requested: Number of cells requested to insert
        - total_inserted: Number of cells actually inserted
        - total_cells: New total number of cells in notebook
        - results: List of results for each cell (with new_cell_id for successful inserts)
        - message: Summary message

    Example:
        multi_insert_cells('[{"after_cell_id": "cell-a1b2", "content": "# Intro", "cell_type": "markdown"}, {"after_cell_id": "cell-c3d4", "content": "print(1)", "cell_type": "code"}]')
    """
    import json

    # Parse JSON string
    try:
        cells = json.loads(cells_json)
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Invalid JSON: {e}"
        }

    if not isinstance(cells, list):
        return {
            "success": False,
            "error": "cells_json must be a JSON array"
        }

    log_debug_message(f"==> multi_insert_cells({len(cells)} cells) called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "success": False,
            "error": "No active session - cannot determine project"
        }

    # Validate cell specifications
    for i, cell in enumerate(cells):
        if not isinstance(cell, dict):
            return {
                "success": False,
                "error": f"Cell {i} must be an object with after_cell_id, content, cell_type"
            }
        if "after_cell_id" not in cell or "content" not in cell or "cell_type" not in cell:
            return {
                "success": False,
                "error": f"Cell {i} missing required fields. Need: after_cell_id, content, cell_type"
            }
        if cell["cell_type"] not in ["code", "markdown"]:
            return {
                "success": False,
                "error": f"Cell {i} has invalid cell_type '{cell['cell_type']}'. Must be 'code' or 'markdown'"
            }

    payload = {"cells": cells}
    return _call_master_api("POST", f"/internal/notebook/{project_id}/cells/batch-insert", payload)


def insert_cell_after(after_cell_id: str, content: str, cell_type: str) -> dict:
    """
    Insert a new cell AFTER an existing cell. This is the PREFERRED insertion method.

    WHEN TO USE THIS TOOL:
    - Adding a new cell anywhere in the notebook (most common case)
    - Insert helper function after imports
    - Add markdown explanation after code

    WHEN NOT TO USE THIS TOOL:
    - To insert at the VERY BEGINNING → use insert_cell_at_position(0, ...)
    - To insert multiple cells at once → use multi_insert_cells()

    WHY THIS IS PREFERRED over insert_cell_at_position:
    - Uses stable cell IDs (don't change when cells are added/deleted)
    - Position indices can shift and cause wrong insertions

    Args:
        after_cell_id: Cell ID to insert after (get from get_notebook_overview())
        content: The new cell's content
        cell_type: "code" or "markdown"

    Returns:
        Dictionary with success, new_cell_id, inserted_at_index

    Example:
        1. get_notebook_overview() → find cell_id
        2. insert_cell_after(cell_id, "# New section", "markdown")
    """
    log_debug_message(f"==> insert_cell_after({after_cell_id}, type={cell_type}) called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "success": False,
            "error": "No active session - cannot determine project"
        }

    if cell_type not in ["code", "markdown"]:
        return {
            "success": False,
            "error": f"Invalid cell_type '{cell_type}'. Must be 'code' or 'markdown'"
        }

    payload = {
        "content": content,
        "cell_type": cell_type
    }

    return _call_master_api("POST", f"/internal/notebook/{project_id}/cell/by-id/{after_cell_id}/insert-after", payload)


def insert_cell_at_position(position: int, content: str, cell_type: str) -> dict:
    """
    Insert a cell at the BEGINNING (position=0) or END of the notebook.

    WHEN TO USE THIS TOOL:
    - Insert at the VERY BEGINNING: insert_cell_at_position(0, content, type)
    - Insert at the VERY END: insert_cell_at_position(total_cells, content, type)

    WHEN NOT TO USE THIS TOOL:
    - For any other insertion → use insert_cell_after(cell_id, ...) instead
      (it's more reliable because cell IDs don't shift)

    Args:
        position: 0 for beginning, or total_cells for end
        content: The new cell's content
        cell_type: "code" or "markdown"

    Returns:
        Dictionary with success, cell_id, inserted_at

    Example:
        # Insert at beginning
        insert_cell_at_position(0, "# Introduction", "markdown")

        # Insert at end (get total_cells from get_notebook_overview first)
        insert_cell_at_position(total_cells, "# Summary", "markdown")
    """
    # Convert to int in case LLM sends float
    position = int(position)

    log_debug_message(f"==> insert_cell_at_position(position={position}, type={cell_type}) called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "success": False,
            "error": "No active session - cannot determine project"
        }

    if cell_type not in ["code", "markdown"]:
        return {
            "success": False,
            "error": f"Invalid cell_type '{cell_type}'. Must be 'code' or 'markdown'"
        }

    payload = {
        "content": content,
        "cell_type": cell_type
    }

    return _call_master_api("POST", f"/internal/notebook/{project_id}/cell/{position}", payload)


def execute_cell(cell_id: str) -> dict:
    """
    Run a notebook cell and SAVE its output to the notebook.

    WHEN TO USE THIS TOOL:
    - After editing a cell with update_cell_content() → run it to verify
    - User says "run cell 3" → execute_cell(cell_id)
    - To show the user output in their notebook

    WHEN NOT TO USE THIS TOOL:
    - For quick calculations → use execute_python_code() instead
    - To test code before suggesting → use sandbox_execute() instead

    KEY DIFFERENCE from execute_python_code:
    - execute_cell() saves output to the notebook cell (user sees it)
    - execute_python_code() runs code but output is NOT saved anywhere

    Args:
        cell_id: The cell's unique ID (get from get_notebook_overview())

    Returns:
        Dictionary with success, cell_id, cell_number, output, error, execution_count

    Example workflow:
        1. get_notebook_overview() → find cell_id
        2. update_cell_content(cell_id, new_code) → edit the cell
        3. execute_cell(cell_id) → run and save output
    """
    log_debug_message(f"==> execute_cell({cell_id}) called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "success": False,
            "error": "No active session - cannot determine project"
        }

    # First, get the cell content from Master API using cell_id
    cell_result = _call_master_api("GET", f"/internal/notebook/{project_id}/cell/by-id/{cell_id}")

    if not cell_result.get("success"):
        return cell_result

    if cell_result.get("type") != "code":
        return {
            "success": False,
            "error": f"Cell '{cell_id}' is a {cell_result.get('type')} cell. Only code cells can be executed."
        }

    # Get kernel from session
    kernel = _get_session_kernel()

    # Auto-start kernel if not running
    if not kernel.is_alive():
        kernel.start()

    # Execute code
    code = cell_result.get("content", "")
    result = kernel.execute(code)

    # Format outputs for storage - keep full structure for images
    outputs_for_storage = []
    output_text = ""  # Text summary for LLM response

    if result["outputs"]:
        for output in result["outputs"]:
            output_type = output.get("type")

            if output_type == "stream":
                text = output.get("text", "")
                output_text += text
                outputs_for_storage.append({
                    "output_type": "stream",
                    "name": output.get("name", "stdout"),
                    "text": text
                })

            elif output_type == "execute_result":
                data = output.get("data", {})
                output_text += data.get("text/plain", "")
                outputs_for_storage.append({
                    "output_type": "execute_result",
                    "data": data,
                    "execution_count": output.get("execution_count")
                })

            elif output_type == "display_data":
                data = output.get("data", {})
                # For text summary, prefer text/plain but note if there's an image
                if "image/png" in data or "image/jpeg" in data:
                    output_text += "[Image output]"
                else:
                    output_text += data.get("text/plain", "")
                outputs_for_storage.append({
                    "output_type": "display_data",
                    "data": data
                })

            elif output_type == "error":
                error_text = f"{output.get('ename', 'Error')}: {output.get('evalue', '')}"
                output_text += error_text
                outputs_for_storage.append({
                    "output_type": "error",
                    "ename": output.get("ename", "Error"),
                    "evalue": output.get("evalue", ""),
                    "traceback": output.get("traceback", [])
                })

    # Update cell output in Master API (persist to S3) using cell_id
    try:
        _call_master_api(
            "PUT",
            f"/internal/notebook/{project_id}/cell/by-id/{cell_id}/output",
            {
                "outputs": outputs_for_storage,
                "execution_count": result["execution_count"]
            }
        )
    except Exception as e:
        log_debug_message(f"Failed to update cell output: {e}")

    return {
        "success": result["success"],
        "cell_id": cell_id,
        "cell_number": cell_result.get("cell_number"),  # 1-based (human-friendly)
        "output": output_text.strip(),
        "error": str(result["error"]) if result["error"] else None,
        "execution_count": result["execution_count"]
    }
