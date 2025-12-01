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


def get_notebook_overview() -> dict:
    """
    Get a high-level overview of all cells in the current notebook.

    IMPORTANT: Always call this first before editing cells to get their cell_id values.
    Cell IDs are stable identifiers that don't change when cells are inserted/deleted.

    Use this tool when you need to:
    - Understand the notebook structure before making changes
    - Get the cell_id of cells you want to read or edit
    - See what cells exist and their types
    - Get a quick preview of cell contents

    Returns:
        Dictionary with:
        - total_cells: Number of cells in notebook
        - cells: List of cell summaries with:
            - id: Unique cell identifier (use this for editing!)
            - cell_number: Position number (1-based, matches what user sees)
            - type: "code" or "markdown"
            - preview: First 100 chars of content

    Example:
        1. Call get_notebook_overview() to see all cells and their IDs
        2. User says "update cell 3" → find cell with cell_number=3, use its id
        3. Use the cell_id from the response to read or update specific cells
    """
    log_debug_message("==> get_notebook_overview called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "total_cells": 0,
            "cells": [],
            "message": "No active session - cannot determine project"
        }

    result = _call_master_api("GET", f"/internal/notebook/{project_id}/cells")

    if "error" in result and result.get("success") == False:
        return {
            "total_cells": 0,
            "cells": [],
            "message": result.get("error", "Failed to fetch notebook")
        }

    return result


def get_cell_content(cell_id: str) -> dict:
    """
    Read the full content of a specific cell by its unique ID.

    Use this tool when you need to:
    - Investigate a cell's code or markdown before editing
    - Analyze a function or code block
    - Read documentation or markdown content
    - Check what a cell contains before making improvements

    Args:
        cell_id: The unique cell identifier (e.g., "cell-a1b2c3d4").
                 Get this from get_notebook_overview().

    Returns:
        Dictionary with:
        - success: Whether the cell was found
        - cell_id: The cell's unique identifier
        - cell_number: Position number (1-based, matches what user sees)
        - type: Cell type ("code" or "markdown")
        - content: Full cell content
        - output: Cell output if it's a code cell that has been executed
        - error: Error message if cell not found

    Example:
        1. First call get_notebook_overview() to find the cell_id
        2. Then: get_cell_content("cell-a1b2c3d4")
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


def insert_cell_after(after_cell_id: str, content: str, cell_type: str) -> dict:
    """
    Insert a new cell after a specific cell (identified by cell_id).

    This is the recommended way to insert cells as it uses stable cell IDs
    rather than position indices that can change.

    Use this tool when you need to:
    - Add helper functions after existing code
    - Insert explanatory markdown after a cell
    - Add new code cells for additional functionality
    - Create documentation cells

    Args:
        after_cell_id: The cell_id of the cell after which to insert.
                       Get this from get_notebook_overview().
        content: The content of the new cell
        cell_type: Type of cell ("code" or "markdown")

    Returns:
        Dictionary with:
        - success: Whether the insertion succeeded
        - inserted_after: The reference cell_id
        - new_cell_id: The ID of the newly created cell
        - inserted_at_index: Current position of new cell
        - content: The inserted content
        - type: Cell type
        - total_cells: New total number of cells
        - error: Error message if insertion failed

    Example:
        1. First call get_notebook_overview() to find the cell_id
        2. Then: insert_cell_after("cell-a1b2c3d4", "def helper():\\n    ...", "code")
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
    Insert a new cell at a specific position in the notebook.

    NOTE: Prefer insert_cell_after() when possible, as it uses stable cell IDs.
    Use this only when you need to insert at the beginning (position=0) or
    at the very end of the notebook.

    Args:
        position: Where to insert the cell (0-based index)
                 - 0 = insert at beginning (before first cell)
                 - n = insert at position n
                 - Use total_cells from get_notebook_overview() to append at end
        content: The content of the new cell
        cell_type: Type of cell ("code" or "markdown")

    Returns:
        Dictionary with:
        - success: Whether the insertion succeeded
        - inserted_at: The index where cell was inserted
        - cell_id: The ID of the newly created cell
        - content: The inserted content
        - type: Cell type
        - total_cells: New total number of cells
        - error: Error message if insertion failed

    Example:
        To insert at the beginning: insert_cell_at_position(0, "# Introduction", "markdown")
        To append at end: insert_cell_at_position(5, "# Summary", "markdown") where 5 is total_cells
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
    Execute a specific code cell in the Jupyter kernel by its unique ID.

    Use this tool when you need to:
    - Test code changes after editing a cell
    - Run a cell to see its output
    - Verify that improvements work correctly
    - Check if code runs without errors

    Note: Only works for code cells. Markdown cells cannot be executed.

    Args:
        cell_id: The unique cell identifier (e.g., "cell-a1b2c3d4").
                 Get this from get_notebook_overview().

    Returns:
        Dictionary with:
        - success: Whether execution succeeded
        - cell_id: The cell's unique identifier
        - cell_number: Position number (1-based, matches what user sees)
        - output: Text output from execution
        - error: Error message if execution failed
        - execution_count: Kernel execution count

    Example:
        1. First call get_notebook_overview() to find the cell_id
        2. After editing a cell, test it: execute_cell("cell-a1b2c3d4")
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
