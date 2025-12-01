"""
Notebook API routes for saving/loading notebooks to S3.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timezone

from app.db.session import get_db
from app.auth.dependencies import get_current_active_user
from app.users.models import User
from app.projects.service import ProjectService
from .s3_client import s3_client
from .schemas import (
    NotebookData,
    NotebookSaveRequest,
    NotebookResponse,
    NotebookVersionInfo,
    CellData,
    NotebookImportRequest,
)
import uuid
# Note: NotebookSyncRequest, PlaygroundService, httpx removed - sync endpoint deprecated

router = APIRouter(prefix="/projects/{project_id}/notebook", tags=["Notebooks"])


@router.get("", response_model=NotebookResponse)
async def get_notebook(
    project_id: str,
    version: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get notebook for a project.

    Args:
        project_id: Project ID
        version: Optional specific version to load

    Returns:
        NotebookResponse with notebook data
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Load notebook from S3 using storage_month
    notebook_data = await s3_client.load_notebook(project.storage_month, project_id, version)

    if notebook_data is None:
        # Return empty notebook (Jupyter .ipynb standard format)
        import uuid
        initial_cell_id = f"cell-{uuid.uuid4().hex[:12]}"
        notebook_data = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": "",
                    "outputs": [],
                    "execution_count": None,
                    "metadata": {"cell_id": initial_cell_id},
                }
            ],
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }

    # Get metadata
    metadata = await s3_client.get_metadata(project.storage_month, project_id)
    last_modified = datetime.now(timezone.utc)
    version_num = 0

    if metadata:
        last_modified = datetime.fromisoformat(metadata.get("last_modified", last_modified.isoformat()))
        version_num = metadata.get("version", 0)

    return NotebookResponse(
        project_id=project_id,
        notebook=NotebookData(**notebook_data),
        last_modified=last_modified,
        version=version_num,
    )


@router.put("")
async def save_notebook(
    project_id: str,
    request: NotebookSaveRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save notebook for a project.

    Args:
        project_id: Project ID
        request: Notebook data to save

    Returns:
        Save confirmation with version info
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Build notebook data
    notebook_data = {
        "cells": [cell.model_dump() for cell in request.cells],
        "metadata": request.metadata or {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    # Save to S3 using storage_month
    result = await s3_client.save_notebook(project.storage_month, project_id, notebook_data)

    return {
        "success": True,
        "version": result["version"],
        "saved_at": result["saved_at"].isoformat(),
        "size_bytes": result["size_bytes"],
    }


@router.get("/versions", response_model=list[NotebookVersionInfo])
async def list_versions(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all notebook versions.

    Args:
        project_id: Project ID

    Returns:
        List of version info
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    versions = await s3_client.list_versions(project.storage_month, project_id)

    return [
        NotebookVersionInfo(
            version=v["version"],
            saved_at=v["saved_at"],
            size_bytes=v["size_bytes"],
        )
        for v in versions
    ]


@router.post("/export")
async def export_notebook(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export notebook as .ipynb file.

    Args:
        project_id: Project ID

    Returns:
        Notebook data in .ipynb format
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Load notebook using storage_month
    notebook_data = await s3_client.load_notebook(project.storage_month, project_id)

    if notebook_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No notebook data found",
        )

    # Convert to standard .ipynb format
    ipynb_data = {
        "cells": [],
        "metadata": notebook_data.get("metadata", {}),
        "nbformat": notebook_data.get("nbformat", 4),
        "nbformat_minor": notebook_data.get("nbformat_minor", 5),
    }

    for cell in notebook_data.get("cells", []):
        # cell_id is in metadata.cell_id (Jupyter standard)
        cell_metadata = cell.get("metadata", {}).copy()
        cell_type = cell.get("cell_type", "code")

        ipynb_cell = {
            "cell_type": cell_type,
            "source": cell.get("source", "").split("\n"),
            "metadata": cell_metadata,
        }

        if cell_type == "code":
            ipynb_cell["execution_count"] = cell.get("execution_count")
            ipynb_cell["outputs"] = cell.get("outputs", [])

        ipynb_data["cells"].append(ipynb_cell)

    return ipynb_data


@router.post("/import")
async def import_notebook(
    project_id: str,
    request: NotebookImportRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Import a .ipynb file into the project.

    Args:
        project_id: Project ID
        request: Contains the raw .ipynb JSON data

    Returns:
        Import confirmation with version info
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    ipynb_data = request.ipynb_data

    # Convert .ipynb format to our internal format
    cells = []
    for cell in ipynb_data.get("cells", []):
        # Handle source - can be string or list of strings
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)

        # Map cell_type to type
        cell_type = cell.get("cell_type", "code")
        if cell_type not in ["code", "markdown"]:
            cell_type = "code"

        # Get cell_id from metadata (standard location) or generate new one
        cell_metadata = cell.get("metadata", {}).copy()
        cell_id = cell_metadata.get("cell_id") or f"cell-{uuid.uuid4().hex[:12]}"

        # Ensure cell_id is stored in metadata (only location - Jupyter standard)
        cell_metadata["cell_id"] = cell_id

        cell_data = {
            "cell_type": cell_type,  # Jupyter standard field name
            "source": source,
            "outputs": cell.get("outputs", []) if cell_type == "code" else [],
            "execution_count": cell.get("execution_count") if cell_type == "code" else None,
            "metadata": cell_metadata,
        }
        cells.append(cell_data)

    # Build notebook data
    notebook_data = {
        "cells": cells,
        "metadata": ipynb_data.get("metadata", {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            }
        }),
        "nbformat": ipynb_data.get("nbformat", 4),
        "nbformat_minor": ipynb_data.get("nbformat_minor", 5),
    }

    # Save to S3 using storage_month
    result = await s3_client.save_notebook(project.storage_month, project_id, notebook_data)

    return {
        "success": True,
        "version": result["version"],
        "saved_at": result["saved_at"].isoformat(),
        "size_bytes": result["size_bytes"],
        "cells_imported": len(cells),
    }


# Note: /sync endpoint removed - LLM tools now fetch from /api/internal/notebook/* endpoints directly
