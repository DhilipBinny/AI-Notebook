"""
Internal API routes for playground-to-master communication.

These endpoints allow the playground container's LLM tools to
read/write notebook data directly from S3 (single source of truth).

Authentication: X-Internal-Secret header (validated against playground's secret in database)

WebSocket: /internal/ws/notebook for real-time cell updates to frontend
"""

from fastapi import APIRouter, HTTPException, status, Header, Depends, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import logging

from app.notebooks.s3_client import s3_client
from app.db.session import get_db, AsyncSessionLocal
from app.playgrounds.models import Playground
from app.projects.models import Project
from app.users.models import User
from app.users.service import UserService
from app.auth.jwt import verify_token
from app.internal.notebook_broadcaster import get_notebook_broadcaster, NotebookUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal"])


async def verify_internal_secret_and_get_project(
    project_id: str,
    x_internal_secret: str,
    db: AsyncSession,
) -> Project:
    """Verify the internal secret and return the project with storage_month"""
    if not x_internal_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing internal secret header",
        )

    # Look up the playground for this project and verify its secret
    result = await db.execute(
        select(Playground).where(Playground.project_id == project_id)
    )
    playground = result.scalar_one_or_none()

    if playground is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No playground found for this project",
        )

    if playground.internal_secret != x_internal_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal secret",
        )

    # Get the project to access storage_month
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project


# === Request/Response Models ===

class CellData(BaseModel):
    """Cell data for API responses"""
    id: str
    type: str
    content: str  # source code or markdown
    output: Optional[str] = None
    cell_number: int
    execution_count: Optional[int] = None


class CellUpdateRequest(BaseModel):
    """Request to update a cell"""
    content: str
    cell_type: Optional[str] = None  # "code" or "markdown"


class CellInsertRequest(BaseModel):
    """Request to insert a new cell"""
    content: str
    cell_type: str  # "code" or "markdown"


class CellOutputRequest(BaseModel):
    """Request to update cell output"""
    output: Optional[str] = None  # Legacy: simple text output
    outputs: Optional[List[Dict[str, Any]]] = None  # Full outputs array with images
    execution_count: Optional[int] = None


class NotebookOverview(BaseModel):
    """Overview of notebook cells"""
    total_cells: int
    cells: List[Dict[str, Any]]


class CellInsertAfterRequest(BaseModel):
    """Request to insert a new cell after a specific cell"""
    content: str
    cell_type: str  # "code" or "markdown"


class BatchCellInsert(BaseModel):
    """Single cell insert specification for batch operations"""
    after_cell_id: str  # Insert after this cell
    content: str
    cell_type: str  # "code" or "markdown"


class BatchInsertRequest(BaseModel):
    """Request to insert multiple cells in one operation"""
    cells: List[BatchCellInsert]


class BatchDeleteRequest(BaseModel):
    """Request to delete multiple cells in one operation"""
    cell_ids: List[str]


# === Helper Functions ===

def get_cell_id(cell: Dict) -> str:
    """Get cell_id from metadata.cell_id (Jupyter standard)."""
    return cell.get("metadata", {}).get("cell_id", "")


def get_cell_type(cell: Dict) -> str:
    """Get cell type from cell_type (Jupyter standard)."""
    return cell.get("cell_type", "code")


def find_cell_index_by_id(cells: List[Dict], cell_id: str) -> int:
    """Find cell index by its unique ID from metadata.cell_id. Returns -1 if not found."""
    for idx, cell in enumerate(cells):
        if get_cell_id(cell) == cell_id:
            return idx
    return -1


# === Endpoints ===

@router.get("/notebook/{project_id}/cells")
async def get_all_cells(
    project_id: str,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all cells from a notebook.

    Used by LLM tools: get_notebook_overview()
    """
    project = await verify_internal_secret_and_get_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project.storage_month, project_id)

        if notebook_data is None:
            return NotebookOverview(total_cells=0, cells=[])

        cells = notebook_data.get("cells", [])

        # Convert to tool-friendly format
        overview_cells = []
        for idx, cell in enumerate(cells, start=1):  # IMP start=1 for cell_number - to align with human counting
            source = cell.get("source", "")
            preview = source[:100] + ("..." if len(source) > 100 else "")

            # Format output
            output_text = None
            if cell.get("outputs"):
                output_parts = []
                for output in cell.get("outputs", []):
                    if output.get("output_type") == "stream":
                        text = output.get("text", "")
                        if isinstance(text, list):
                            text = "".join(text)
                        output_parts.append(text)
                    elif output.get("output_type") == "execute_result":
                        data = output.get("data", {})
                        output_parts.append(data.get("text/plain", ""))
                    elif output.get("output_type") == "error":
                        output_parts.append(f"{output.get('ename')}: {output.get('evalue')}")
                output_text = "\n".join(output_parts) if output_parts else None

            overview_cells.append({
                "cell_number": idx,  # 1-based (human-friendly)
                "id": get_cell_id(cell) or f"cell-{idx}",  # cell_id from metadata
                "type": get_cell_type(cell),
                "preview": preview,
                "has_output": bool(output_text),
            })

        return {
            "total_cells": len(cells),
            "cells": overview_cells,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/notebook/{project_id}/cells/full")
async def get_all_cells_full(
    project_id: str,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all cells with full content and outputs.

    Used by LLM tools: get_notebook_overview(detail="full")
    Returns complete cell data in a single API call.
    """
    project = await verify_internal_secret_and_get_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project.storage_month, project_id)

        if notebook_data is None:
            return {"total_cells": 0, "cells": []}

        cells = notebook_data.get("cells", [])

        # Convert to tool-friendly format with full content
        full_cells = []
        for idx, cell in enumerate(cells, start=1):
            source = cell.get("source", "")

            # Format output text
            output_text = None
            if cell.get("outputs"):
                output_parts = []
                for output in cell.get("outputs", []):
                    if output.get("output_type") == "stream":
                        text = output.get("text", "")
                        if isinstance(text, list):
                            text = "".join(text)
                        output_parts.append(text)
                    elif output.get("output_type") == "execute_result":
                        data = output.get("data", {})
                        output_parts.append(data.get("text/plain", ""))
                    elif output.get("output_type") == "error":
                        output_parts.append(f"{output.get('ename')}: {output.get('evalue')}")
                output_text = "\n".join(output_parts) if output_parts else None

            full_cells.append({
                "cell_number": idx,
                "id": get_cell_id(cell) or f"cell-{idx}",
                "type": get_cell_type(cell),
                "content": source,
                "output": output_text,
                "execution_count": cell.get("execution_count"),
            })

        return {
            "total_cells": len(cells),
            "cells": full_cells,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/notebook/{project_id}/cell/{position}")
async def insert_cell(
    project_id: str,
    position: int,
    request: CellInsertRequest,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Insert a new cell at a specific position.

    Used by LLM tools: insert_cell()
    """
    project = await verify_internal_secret_and_get_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project.storage_month, project_id)

        if notebook_data is None:
            # Create new notebook with just this cell
            notebook_data = {
                "cells": [],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }

        cells = notebook_data.get("cells", [])

        if request.cell_type not in ["code", "markdown"]:
            return {
                "success": False,
                "error": f"Invalid cell_type '{request.cell_type}'. Must be 'code' or 'markdown'",
            }

        if position < 0 or position > len(cells):
            return {
                "success": False,
                "error": f"Position {position} out of range. Valid range: 0-{len(cells)}",
            }

        # Generate new cell ID (stored only in metadata - Jupyter standard)
        import uuid
        cell_id = f"cell-{uuid.uuid4().hex[:12]}"
        new_cell = {
            "cell_type": request.cell_type,  # Jupyter standard field name
            "source": request.content,
            "outputs": [],
            "execution_count": None,
            "metadata": {"cell_id": cell_id},
        }

        # Insert at position
        cells.insert(position, new_cell)

        # Save back to S3
        notebook_data["cells"] = cells
        await s3_client.save_notebook(project.storage_month, project_id, notebook_data)

        # Broadcast new cell to connected frontends
        broadcaster = get_notebook_broadcaster()
        await broadcaster.broadcast_update(
            project_id,
            NotebookUpdate(
                update_type="cell_created",
                cell_id=cell_id,
                cell_index=position,
                content=request.content,
                cell_type=request.cell_type,
            )
        )

        return {
            "success": True,
            "inserted_at": position,
            "cell_id": cell_id,
            "content": request.content,
            "type": request.cell_type,
            "total_cells": len(cells),
            "message": f"New {request.cell_type} cell inserted at position {position}",
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# === Cell ID-based Endpoints (more reliable than index-based) ===

@router.get("/notebook/{project_id}/cell/by-id/{cell_id}")
async def get_cell_by_id(
    project_id: str,
    cell_id: str,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific cell by its unique ID.

    More reliable than index-based access as cell IDs don't change
    when other cells are inserted/deleted.
    """
    project = await verify_internal_secret_and_get_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project.storage_month, project_id)

        if notebook_data is None:
            return {"success": False, "error": "Notebook not found"}

        cells = notebook_data.get("cells", [])
        cell_index = find_cell_index_by_id(cells, cell_id)

        if cell_index == -1:
            return {
                "success": False,
                "error": f"Cell with ID '{cell_id}' not found. Use get_notebook_overview() to see available cell IDs.",
            }

        cell = cells[cell_index]

        # Format output
        output_text = None
        if cell.get("outputs"):
            output_parts = []
            for output in cell.get("outputs", []):
                if output.get("output_type") == "stream":
                    text = output.get("text", "")
                    if isinstance(text, list):
                        text = "".join(text)
                    output_parts.append(text)
                elif output.get("output_type") == "execute_result":
                    data = output.get("data", {})
                    output_parts.append(data.get("text/plain", ""))
                elif output.get("output_type") == "error":
                    output_parts.append(f"{output.get('ename')}: {output.get('evalue')}")
            output_text = "\n".join(output_parts) if output_parts else None

        return {
            "success": True,
            "cell_id": cell_id,
            "cell_number": cell_index + 1,  # 1-based (human-friendly)
            "type": get_cell_type(cell),
            "content": cell.get("source", ""),
            "output": output_text,
            "execution_count": cell.get("execution_count"),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put("/notebook/{project_id}/cell/by-id/{cell_id}")
async def update_cell_by_id(
    project_id: str,
    cell_id: str,
    request: CellUpdateRequest,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a specific cell's content by its unique ID.

    More reliable than index-based updates as cell IDs don't change
    when other cells are inserted/deleted.
    """
    project = await verify_internal_secret_and_get_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project.storage_month, project_id)

        if notebook_data is None:
            return {"success": False, "error": "Notebook not found"}

        cells = notebook_data.get("cells", [])
        cell_index = find_cell_index_by_id(cells, cell_id)

        if cell_index == -1:
            return {
                "success": False,
                "error": f"Cell with ID '{cell_id}' not found. Use get_notebook_overview() to see available cell IDs.",
            }

        # Store old content for response
        old_content = cells[cell_index].get("source", "")

        # Update cell
        cells[cell_index]["source"] = request.content

        # Update type if specified (use Jupyter standard field name)
        if request.cell_type and request.cell_type in ["code", "markdown"]:
            cells[cell_index]["cell_type"] = request.cell_type

        # Clear outputs since content changed
        cells[cell_index]["outputs"] = []
        cells[cell_index]["execution_count"] = None

        # Save back to S3
        notebook_data["cells"] = cells
        await s3_client.save_notebook(project.storage_month, project_id, notebook_data)

        # Broadcast update to connected frontends
        broadcaster = get_notebook_broadcaster()
        await broadcaster.broadcast_update(
            project_id,
            NotebookUpdate(
                update_type="cell_updated",
                cell_id=cell_id,
                cell_index=cell_index,
                content=request.content,
                cell_type=get_cell_type(cells[cell_index]),
            )
        )

        return {
            "success": True,
            "cell_id": cell_id,
            "cell_number": cell_index + 1,  # 1-based (human-friendly)
            "old_content": old_content,
            "new_content": request.content,
            "type": get_cell_type(cells[cell_index]),
            "message": f"Cell {cell_index + 1} ('{cell_id}') updated successfully",
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/notebook/{project_id}/cell/by-id/{cell_id}/insert-after")
async def insert_cell_after_id(
    project_id: str,
    cell_id: str,
    request: CellInsertAfterRequest,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Insert a new cell after a specific cell (identified by ID).

    More reliable than position-based insert as it uses the stable cell ID
    to determine where to insert.
    """
    project = await verify_internal_secret_and_get_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project.storage_month, project_id)

        if notebook_data is None:
            return {"success": False, "error": "Notebook not found"}

        cells = notebook_data.get("cells", [])

        if request.cell_type not in ["code", "markdown"]:
            return {
                "success": False,
                "error": f"Invalid cell_type '{request.cell_type}'. Must be 'code' or 'markdown'",
            }

        # Find the reference cell
        ref_index = find_cell_index_by_id(cells, cell_id)

        if ref_index == -1:
            return {
                "success": False,
                "error": f"Reference cell with ID '{cell_id}' not found. Use get_notebook_overview() to see available cell IDs.",
            }

        # Generate new cell ID (stored only in metadata - Jupyter standard)
        import uuid
        new_cell_id = f"cell-{uuid.uuid4().hex[:12]}"
        new_cell = {
            "cell_type": request.cell_type,  # Jupyter standard field name
            "source": request.content,
            "outputs": [],
            "execution_count": None,
            "metadata": {"cell_id": new_cell_id},
        }

        # Insert after the reference cell
        insert_position = ref_index + 1
        cells.insert(insert_position, new_cell)

        # Save back to S3
        notebook_data["cells"] = cells
        await s3_client.save_notebook(project.storage_month, project_id, notebook_data)

        # Broadcast new cell to connected frontends
        broadcaster = get_notebook_broadcaster()
        await broadcaster.broadcast_update(
            project_id,
            NotebookUpdate(
                update_type="cell_created",
                cell_id=new_cell_id,
                cell_index=insert_position,
                content=request.content,
                cell_type=request.cell_type,
            )
        )

        return {
            "success": True,
            "inserted_after": cell_id,  # Reference cell ID
            "new_cell_id": new_cell_id,
            "inserted_at_index": insert_position,  # 0-based for frontend
            "cell_number": insert_position + 1,  # 1-based (human-friendly)
            "content": request.content,
            "type": request.cell_type,
            "total_cells": len(cells),
            "message": f"New {request.cell_type} cell inserted as cell {insert_position + 1}",
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete("/notebook/{project_id}/cell/by-id/{cell_id}")
async def delete_cell_by_id(
    project_id: str,
    cell_id: str,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a cell from the notebook by its unique ID.

    Used by LLM tools: delete_cell()
    """
    project = await verify_internal_secret_and_get_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project.storage_month, project_id)

        if notebook_data is None:
            return {"success": False, "error": "Notebook not found"}

        cells = notebook_data.get("cells", [])

        # Find the cell to delete
        cell_index = find_cell_index_by_id(cells, cell_id)

        if cell_index == -1:
            return {
                "success": False,
                "error": f"Cell with ID '{cell_id}' not found. Use get_notebook_overview() to see available cell IDs.",
            }

        # Get cell info before deleting
        deleted_cell = cells[cell_index]
        deleted_cell_type = get_cell_type(deleted_cell)

        # Remove the cell
        cells.pop(cell_index)

        # Ensure at least one cell remains
        if len(cells) == 0:
            import uuid
            new_cell_id = f"cell-{uuid.uuid4().hex[:12]}"
            cells.append({
                "cell_type": "code",
                "source": "",
                "outputs": [],
                "execution_count": None,
                "metadata": {"cell_id": new_cell_id},
            })

        # Save back to S3
        notebook_data["cells"] = cells
        await s3_client.save_notebook(project.storage_month, project_id, notebook_data)

        # Broadcast deletion to connected frontends
        broadcaster = get_notebook_broadcaster()
        await broadcaster.broadcast_update(
            project_id,
            NotebookUpdate(
                update_type="cell_deleted",
                cell_id=cell_id,
                cell_index=cell_index,
            )
        )

        return {
            "success": True,
            "deleted_cell_id": cell_id,
            "deleted_cell_type": deleted_cell_type,
            "deleted_from_position": cell_index + 1,  # 1-based
            "total_cells": len(cells),
            "message": f"Cell {cell_id} deleted successfully",
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/notebook/{project_id}/cells/batch-insert")
async def batch_insert_cells(
    project_id: str,
    request: BatchInsertRequest,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Insert multiple cells in one operation.

    Each cell specifies which cell to insert after.
    Cells are processed in order, so later cells can reference
    cells created by earlier inserts in the same batch.

    Used by LLM tools: multi_insert_cells()
    """
    project = await verify_internal_secret_and_get_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project.storage_month, project_id)

        if notebook_data is None:
            return {"success": False, "error": "Notebook not found"}

        cells = notebook_data.get("cells", [])
        results = []

        for cell_spec in request.cells:
            if cell_spec.cell_type not in ["code", "markdown"]:
                results.append({
                    "success": False,
                    "after_cell_id": cell_spec.after_cell_id,
                    "error": f"Invalid cell_type '{cell_spec.cell_type}'"
                })
                continue

            # Find the reference cell
            ref_index = find_cell_index_by_id(cells, cell_spec.after_cell_id)

            if ref_index == -1:
                results.append({
                    "success": False,
                    "after_cell_id": cell_spec.after_cell_id,
                    "error": f"Reference cell '{cell_spec.after_cell_id}' not found"
                })
                continue

            # Generate new cell ID
            import uuid
            new_cell_id = f"cell-{uuid.uuid4().hex[:12]}"
            new_cell = {
                "cell_type": cell_spec.cell_type,
                "source": cell_spec.content,
                "outputs": [],
                "execution_count": None,
                "metadata": {"cell_id": new_cell_id},
            }

            # Insert after the reference cell
            insert_position = ref_index + 1
            cells.insert(insert_position, new_cell)

            results.append({
                "success": True,
                "inserted_after": cell_spec.after_cell_id,
                "new_cell_id": new_cell_id,
                "cell_number": insert_position + 1,
                "type": cell_spec.cell_type
            })

        # Save back to S3
        notebook_data["cells"] = cells
        await s3_client.save_notebook(project.storage_month, project_id, notebook_data)

        successful = sum(1 for r in results if r.get("success"))
        return {
            "success": True,
            "total_requested": len(request.cells),
            "total_inserted": successful,
            "total_cells": len(cells),
            "results": results,
            "message": f"Inserted {successful} of {len(request.cells)} cells"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/notebook/{project_id}/cells/batch-delete")
async def batch_delete_cells(
    project_id: str,
    request: BatchDeleteRequest,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete multiple cells in one operation.

    Used by LLM tools: multi_delete_cells()
    """
    project = await verify_internal_secret_and_get_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project.storage_month, project_id)

        if notebook_data is None:
            return {"success": False, "error": "Notebook not found"}

        cells = notebook_data.get("cells", [])
        results = []

        # Collect indices to delete (process in reverse to maintain indices)
        indices_to_delete = []
        for cell_id in request.cell_ids:
            cell_index = find_cell_index_by_id(cells, cell_id)
            if cell_index == -1:
                results.append({
                    "success": False,
                    "cell_id": cell_id,
                    "error": f"Cell '{cell_id}' not found"
                })
            else:
                indices_to_delete.append((cell_index, cell_id, get_cell_type(cells[cell_index])))

        # Sort by index descending to delete from end first (preserves indices)
        indices_to_delete.sort(key=lambda x: x[0], reverse=True)

        for cell_index, cell_id, cell_type in indices_to_delete:
            cells.pop(cell_index)
            results.append({
                "success": True,
                "cell_id": cell_id,
                "deleted_cell_type": cell_type,
                "deleted_from_position": cell_index + 1
            })

        # Ensure at least one cell remains
        if len(cells) == 0:
            import uuid
            new_cell_id = f"cell-{uuid.uuid4().hex[:12]}"
            cells.append({
                "cell_type": "code",
                "source": "",
                "outputs": [],
                "execution_count": None,
                "metadata": {"cell_id": new_cell_id},
            })

        # Save back to S3
        notebook_data["cells"] = cells
        await s3_client.save_notebook(project.storage_month, project_id, notebook_data)

        successful = sum(1 for r in results if r.get("success"))
        return {
            "success": True,
            "total_requested": len(request.cell_ids),
            "total_deleted": successful,
            "total_cells": len(cells),
            "results": results,
            "message": f"Deleted {successful} of {len(request.cell_ids)} cells"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put("/notebook/{project_id}/cell/by-id/{cell_id}/output")
async def update_cell_output_by_id(
    project_id: str,
    cell_id: str,
    request: CellOutputRequest,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a cell's output after execution (by cell ID).

    Used by LLM tools: execute_cell() (after kernel execution)
    """
    project = await verify_internal_secret_and_get_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project.storage_month, project_id)

        if notebook_data is None:
            return {"success": False, "error": "Notebook not found"}

        cells = notebook_data.get("cells", [])
        cell_index = find_cell_index_by_id(cells, cell_id)

        if cell_index == -1:
            return {
                "success": False,
                "error": f"Cell with ID '{cell_id}' not found.",
            }

        # Update output - prefer full outputs array if provided
        if request.outputs is not None:
            cells[cell_index]["outputs"] = request.outputs
        elif request.output:
            cells[cell_index]["outputs"] = [
                {
                    "output_type": "stream",
                    "name": "stdout",
                    "text": request.output,
                }
            ]
        else:
            cells[cell_index]["outputs"] = []

        if request.execution_count is not None:
            cells[cell_index]["execution_count"] = request.execution_count

        # Save back to S3
        notebook_data["cells"] = cells
        await s3_client.save_notebook(project.storage_month, project_id, notebook_data)

        # Broadcast execution result to connected frontends
        broadcaster = get_notebook_broadcaster()
        await broadcaster.broadcast_update(
            project_id,
            NotebookUpdate(
                update_type="cell_executed",
                cell_id=cell_id,
                cell_index=cell_index,
                outputs=cells[cell_index]["outputs"],
                execution_count=request.execution_count,
            )
        )

        return {
            "success": True,
            "cell_id": cell_id,
            "cell_number": cell_index + 1,  # 1-based (human-friendly)
            "output": request.output,
            "execution_count": request.execution_count,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# =============================================================================
# WebSocket endpoint for real-time notebook updates
# =============================================================================

@router.websocket("/ws/notebook/{project_id}")
async def websocket_notebook_updates(
    websocket: WebSocket,
    project_id: str,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time notebook updates.

    Authentication: JWT access token required via ?token= query parameter.
    The user must own the project to subscribe to its updates.

    Frontend clients connect and receive updates when LLM tools modify cells.

    Message format from client:
        {"type": "ping"}  (keep-alive)

    Message format to client:
        {
            "type": "notebook_update",
            "update_type": "cell_created" | "cell_updated" | "cell_deleted" | "cell_executed",
            "cell_id": "cell-xxx",
            "cell_index": 0,
            "content": "...",
            "cell_type": "code" | "markdown",
            "outputs": [...],
            "execution_count": 1
        }
    """
    # --- Authenticate the WebSocket connection ---
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    token_data = verify_token(token, expected_type="access")
    if token_data is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # Verify the user owns this project
    async with AsyncSessionLocal() as db:
        user_service = UserService(db)
        user = await user_service.get_by_id(token_data.sub)
        if user is None:
            await websocket.close(code=4001, reason="User not found")
            return

        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user.id,
                Project.deleted_at.is_(None),
            )
        )
        project = result.scalar_one_or_none()
        if project is None:
            await websocket.close(code=4003, reason="Project not found or access denied")
            return

    # --- Connection authenticated, proceed ---
    await websocket.accept()

    broadcaster = get_notebook_broadcaster()
    await broadcaster.connect(websocket, project_id)

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket notebook error: {e}")
    finally:
        await broadcaster.disconnect(websocket, project_id)
