"""
Notebook Cell Tools - Allows LLM to read and edit notebook cells

These tools fetch notebook data from Master API (single source of truth in S3).
The project_id is obtained from the current session.

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

    Use this tool when you need to:
    - Understand the notebook structure before making changes
    - See what cells exist and their types
    - Get a quick preview of cell contents
    - Identify which cell to edit or investigate

    Returns:
        Dictionary with:
        - total_cells: Number of cells in notebook
        - cells: List of cell summaries with index (0-based), type, and content preview (first 100 chars)

    Example:
        To see what's in the notebook before improving a function, call this first.
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


def get_cell_content(cell_index: int) -> dict:
    """
    Read the full content of a specific cell.

    Use this tool when you need to:
    - Investigate a cell's code or markdown before editing
    - Analyze a function or code block
    - Read documentation or markdown content
    - Check what a cell contains before making improvements

    Args:
        cell_index: The 0-based index of the cell to read (e.g., 0 for first cell, 1 for second cell)

    Returns:
        Dictionary with:
        - success: Whether the cell was found
        - cell_index: The requested index
        - cell_number: Display number (1-based)
        - type: Cell type ("code" or "markdown")
        - content: Full cell content
        - output: Cell output if it's a code cell that has been executed
        - error: Error message if cell not found

    Example:
        To read cell at index 2 (the 3rd cell): get_cell_content(2)
    """
    # Convert to int in case LLM sends float
    cell_index = int(cell_index)

    log_debug_message(f"==> get_cell_content({cell_index}) called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "success": False,
            "error": "No active session - cannot determine project"
        }

    return _call_master_api("GET", f"/internal/notebook/{project_id}/cell/{cell_index}")


def update_cell_content(cell_index: int, new_content: str, cell_type: Optional[str] = None) -> dict:
    """
    Update the content of a specific cell (and optionally change its type).

    Use this tool when you need to:
    - Improve or fix code in a cell
    - Add documentation or comments
    - Refactor functions
    - Update markdown content
    - Fix bugs or add error handling

    IMPORTANT: Use 0-based indexing (0 for first cell, 1 for second, etc.)

    Args:
        cell_index: The 0-based index of the cell to update
        new_content: The new content to replace the cell's current content
        cell_type: Optional. Change cell type ("code" or "markdown"). If not provided, keeps existing type.

    Returns:
        Dictionary with:
        - success: Whether the update succeeded
        - cell_index: The updated cell index
        - cell_number: Display number (1-based)
        - old_content: Previous content (for reference)
        - new_content: Updated content
        - type: Cell type after update
        - error: Error message if update failed

    Example:
        To improve the function in cell 2: update_cell_content(2, "def improved_function():\\n    ...")
    """
    # Convert to int in case LLM sends float
    cell_index = int(cell_index)

    log_debug_message(f"==> update_cell_content({cell_index}) called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "success": False,
            "error": "No active session - cannot determine project"
        }

    payload = {"content": new_content}
    if cell_type:
        payload["cell_type"] = cell_type

    return _call_master_api("PUT", f"/internal/notebook/{project_id}/cell/{cell_index}", payload)


def insert_cell(position: int, content: str, cell_type: str) -> dict:
    """
    Insert a new cell at a specific position in the notebook.

    Use this tool when you need to:
    - Add helper functions before existing code
    - Insert explanatory markdown before complex code
    - Add new code cells for additional functionality
    - Create documentation cells

    Args:
        position: Where to insert the cell (0-based index)
                 - 0 = insert at beginning (before first cell)
                 - n = insert after cell n-1 (between cells)
                 - Use len(cells) to append at end
                 - position should be integer and not float or string
        content: The content of the new cell
        cell_type: Type of cell ("code" or "markdown")

    Returns:
        Dictionary with:
        - success: Whether the insertion succeeded
        - inserted_at: The index where cell was inserted
        - content: The inserted content
        - type: Cell type
        - total_cells: New total number of cells
        - error: Error message if insertion failed

    Example:
        To insert a helper function before cell 3: insert_cell(3, "def helper():\\n    ...", "code")
        To append at end: insert_cell(5, "# Summary", "markdown") where 5 is current cell count
    """
    # Convert to int in case LLM sends float
    position = int(position)

    log_debug_message(f"==> insert_cell(position={position}, type={cell_type}) called from LLM")

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


def execute_cell(cell_index: int) -> dict:
    """
    Execute a specific code cell in the Jupyter kernel.

    Use this tool when you need to:
    - Test code changes after editing a cell
    - Run a cell to see its output
    - Verify that improvements work correctly
    - Check if code runs without errors

    Note: Only works for code cells. Markdown cells cannot be executed.

    Args:
        cell_index: The 0-based index of the cell to execute

    Returns:
        Dictionary with:
        - success: Whether execution succeeded
        - cell_index: The executed cell index
        - output: Text output from execution
        - error: Error message if execution failed
        - execution_count: Kernel execution count

    Example:
        After improving cell 2, test it: execute_cell(2)
    """
    # Convert to int in case LLM sends float
    cell_index = int(cell_index)

    log_debug_message(f"==> execute_cell({cell_index}) called from LLM")

    project_id = _get_project_id()
    if not project_id:
        return {
            "success": False,
            "error": "No active session - cannot determine project"
        }

    # First, get the cell content from Master API
    cell_result = _call_master_api("GET", f"/internal/notebook/{project_id}/cell/{cell_index}")

    if not cell_result.get("success"):
        return cell_result

    if cell_result.get("type") != "code":
        return {
            "success": False,
            "error": f"Cell {cell_index} is a {cell_result.get('type')} cell. Only code cells can be executed."
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

    # Update cell output in Master API (persist to S3)
    # Send full outputs structure including images
    try:
        _call_master_api(
            "PUT",
            f"/internal/notebook/{project_id}/cell/{cell_index}/output",
            {
                "outputs": outputs_for_storage,
                "execution_count": result["execution_count"]
            }
        )
    except Exception as e:
        log_debug_message(f"Failed to update cell output: {e}")

    return {
        "success": result["success"],
        "cell_index": cell_index,
        "output": output_text.strip(),
        "error": str(result["error"]) if result["error"] else None,
        "execution_count": result["execution_count"]
    }
