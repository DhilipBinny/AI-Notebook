"""
Internal API routes for playground-to-master communication.

These endpoints allow the playground container's LLM tools to
read/write notebook data directly from S3 (single source of truth).

Authentication: X-Internal-Secret header (validated against playground's secret in database)
"""

from fastapi import APIRouter, HTTPException, status, Header, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.notebooks.s3_client import s3_client
from app.db.session import get_db
from app.playgrounds.models import Playground

router = APIRouter(prefix="/internal", tags=["Internal"])


async def verify_internal_secret_for_project(
    project_id: str,
    x_internal_secret: str,
    db: AsyncSession,
) -> bool:
    """Verify the internal secret against the playground's secret in database"""
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

    return True


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
    await verify_internal_secret_for_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project_id)

        if notebook_data is None:
            return NotebookOverview(total_cells=0, cells=[])

        cells = notebook_data.get("cells", [])

        # Convert to tool-friendly format
        overview_cells = []
        for idx, cell in enumerate(cells):
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
                "index": idx,
                "cell_number": idx + 1,
                "id": cell.get("id", f"cell-{idx}"),
                "type": cell.get("type", "code"),
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


@router.get("/notebook/{project_id}/cell/{cell_index}")
async def get_cell(
    project_id: str,
    cell_index: int,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific cell by index.

    Used by LLM tools: get_cell_content()
    """
    await verify_internal_secret_for_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project_id)

        if notebook_data is None:
            return {
                "success": False,
                "error": "Notebook not found",
            }

        cells = notebook_data.get("cells", [])

        if cell_index < 0 or cell_index >= len(cells):
            return {
                "success": False,
                "error": f"Cell index {cell_index} out of range. Notebook has {len(cells)} cells (valid indices: 0-{len(cells)-1})",
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
            "cell_index": cell_index,
            "cell_number": cell_index + 1,
            "id": cell.get("id", f"cell-{cell_index}"),
            "type": cell.get("type", "code"),
            "content": cell.get("source", ""),
            "output": output_text,
            "execution_count": cell.get("execution_count"),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put("/notebook/{project_id}/cell/{cell_index}")
async def update_cell(
    project_id: str,
    cell_index: int,
    request: CellUpdateRequest,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a specific cell's content.

    Used by LLM tools: update_cell_content()
    """
    await verify_internal_secret_for_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project_id)

        if notebook_data is None:
            return {
                "success": False,
                "error": "Notebook not found",
            }

        cells = notebook_data.get("cells", [])

        if cell_index < 0 or cell_index >= len(cells):
            return {
                "success": False,
                "error": f"Cell index {cell_index} out of range. Notebook has {len(cells)} cells",
            }

        # Store old content for response
        old_content = cells[cell_index].get("source", "")
        old_type = cells[cell_index].get("type", "code")

        # Update cell
        cells[cell_index]["source"] = request.content

        # Update type if specified
        if request.cell_type and request.cell_type in ["code", "markdown"]:
            cells[cell_index]["type"] = request.cell_type

        # Clear outputs since content changed
        cells[cell_index]["outputs"] = []
        cells[cell_index]["execution_count"] = None

        # Save back to S3
        notebook_data["cells"] = cells
        await s3_client.save_notebook(project_id, notebook_data)

        return {
            "success": True,
            "cell_index": cell_index,
            "cell_number": cell_index + 1,
            "cell_id": cells[cell_index].get("id"),
            "old_content": old_content,
            "new_content": request.content,
            "type": cells[cell_index].get("type", "code"),
            "message": f"Cell {cell_index} updated successfully",
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
    await verify_internal_secret_for_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project_id)

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

        # Generate new cell ID
        import uuid
        new_cell = {
            "id": f"cell-{uuid.uuid4().hex[:8]}",
            "type": request.cell_type,
            "source": request.content,
            "outputs": [],
            "execution_count": None,
            "metadata": {},
        }

        # Insert at position
        cells.insert(position, new_cell)

        # Save back to S3
        notebook_data["cells"] = cells
        await s3_client.save_notebook(project_id, notebook_data)

        return {
            "success": True,
            "inserted_at": position,
            "cell_id": new_cell["id"],
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


@router.put("/notebook/{project_id}/cell/{cell_index}/output")
async def update_cell_output(
    project_id: str,
    cell_index: int,
    request: CellOutputRequest,
    x_internal_secret: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a cell's output after execution.

    Used by LLM tools: execute_cell() (after kernel execution)
    """
    await verify_internal_secret_for_project(project_id, x_internal_secret, db)

    try:
        notebook_data = await s3_client.load_notebook(project_id)

        if notebook_data is None:
            return {"success": False, "error": "Notebook not found"}

        cells = notebook_data.get("cells", [])

        if cell_index < 0 or cell_index >= len(cells):
            return {"success": False, "error": f"Cell index {cell_index} out of range"}

        # Update output - prefer full outputs array if provided
        if request.outputs is not None:
            # Full outputs array with images, display_data, etc.
            cells[cell_index]["outputs"] = request.outputs
        elif request.output:
            # Legacy: simple text output
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
        await s3_client.save_notebook(project_id, notebook_data)

        return {
            "success": True,
            "cell_index": cell_index,
            "output": request.output,
            "execution_count": request.execution_count,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
