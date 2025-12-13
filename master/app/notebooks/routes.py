"""
Notebook API routes for saving/loading notebooks to S3.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timezone
import httpx
import logging

from app.db.session import get_db
from app.auth.dependencies import get_current_active_user
from app.users.models import User
from app.projects.service import ProjectService
from app.playgrounds.service import PlaygroundService
from app.playgrounds.models import PlaygroundStatus
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

logger = logging.getLogger(__name__)

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

    # Update playground activity if running (user is actively working)
    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_project_id(project_id)
    if playground:
        await playground_service.update_activity(playground)

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

    # Update project's updated_at timestamp in database
    project.updated_at = datetime.now(timezone.utc)
    await db.flush()

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

        # Handle AI cells specially for .ipynb compatibility
        if cell_type == "ai":
            # Convert to "raw" cell type for Jupyter compatibility
            # Store ai_data in metadata so we can restore it on import
            ai_data = cell.get("ai_data", {})
            cell_metadata["ai_cell"] = True
            cell_metadata["ai_data"] = ai_data

            # Build readable source from prompt + response
            prompt = ai_data.get("user_prompt", "")
            response = ai_data.get("llm_response", "")
            source_lines = []
            if prompt:
                source_lines.append(f"[AI PROMPT]: {prompt}")
            if response:
                source_lines.append("")
                source_lines.append("[AI RESPONSE]:")
                source_lines.extend(response.split("\n"))

            ipynb_cell = {
                "cell_type": "raw",
                "source": source_lines,
                "metadata": cell_metadata,
            }
        else:
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

        # Get cell metadata
        cell_metadata = cell.get("metadata", {}).copy()

        # Check if this is an AI cell (exported from our app)
        if cell_metadata.get("ai_cell"):
            # Restore AI cell
            cell_type = "ai"
            ai_data = cell_metadata.pop("ai_data", {})
            cell_metadata.pop("ai_cell", None)  # Remove marker

            # Get cell_id from metadata or generate new one
            cell_id = cell_metadata.get("cell_id") or f"cell-{uuid.uuid4().hex[:12]}"
            cell_metadata["cell_id"] = cell_id

            cell_data = {
                "cell_type": cell_type,
                "source": "",  # AI cells don't use source field
                "outputs": [],
                "metadata": cell_metadata,
                "ai_data": ai_data,
            }
        else:
            # Regular cell
            cell_type = cell.get("cell_type", "code")
            if cell_type not in ["code", "markdown", "raw"]:
                cell_type = "code"

            # Get cell_id from metadata (standard location) or generate new one
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


@router.post("/summarize")
async def summarize_notebook(
    project_id: str,
    llm_provider: str = "gemini",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an AI summary of the notebook.

    Collects all cell contents (code and markdown, excluding outputs),
    sends them to the LLM for summarization, and returns the summary.

    Args:
        project_id: Project ID
        llm_provider: LLM provider to use ("gemini", "openai", "anthropic", "ollama")

    Returns:
        Dict with success status and summary text
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Check if playground is running
    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_project_id(project_id)

    if not playground or playground.status != PlaygroundStatus.RUNNING:
        return {
            "success": False,
            "summary": "",
            "error": "Playground is not running. Start the playground to use AI summarization.",
        }

    # Load notebook from S3
    notebook_data = await s3_client.load_notebook(project.storage_month, project_id)

    if notebook_data is None or not notebook_data.get("cells"):
        return {
            "success": False,
            "summary": "",
            "error": "No notebook content found to summarize.",
        }

    # Collect cell contents (excluding outputs)
    cell_contents = []
    for i, cell in enumerate(notebook_data.get("cells", []), 1):
        cell_type = cell.get("cell_type", "code")
        source = cell.get("source", "")
        if source.strip():
            cell_contents.append(f"[Cell {i} - {cell_type}]\n{source}")

    if not cell_contents:
        return {
            "success": False,
            "summary": "",
            "error": "All cells are empty. Add some content to summarize.",
        }

    # Build the summarization prompt
    notebook_content = "\n\n".join(cell_contents)
    summarize_prompt = f"""Please provide a concise summary of this Jupyter notebook.
Include:
- The main purpose/goal of the notebook
- Key operations or analyses performed
- Important libraries or tools used
- Main findings or outputs (if apparent from the code)

Keep the summary clear and under 300 words.

Notebook content:
{notebook_content}"""

    try:
        async with httpx.AsyncClient() as client:
            # Call the playground's simple completion endpoint (no tools)
            # llm_provider is passed in the request body
            response = await client.post(
                f"{playground.internal_url}/llm/complete",
                headers={"X-Internal-Secret": playground.internal_secret},
                json={
                    "prompt": summarize_prompt,
                    "max_tokens": 1000,
                    "llm_provider": llm_provider,
                },
                timeout=60,
            )

            if response.status_code != 200:
                logger.error(f"LLM completion failed: {response.text}")
                return {
                    "success": False,
                    "summary": "",
                    "error": f"Failed to generate summary: {response.text}",
                }

            data = response.json()
            summary = data.get("response", "")

            if not summary:
                return {
                    "success": False,
                    "summary": "",
                    "error": "LLM returned empty response.",
                }

            return {
                "success": True,
                "summary": summary,
            }

    except httpx.TimeoutException:
        return {
            "success": False,
            "summary": "",
            "error": "Request timed out. The LLM may be taking too long to respond.",
        }
    except Exception as e:
        logger.error(f"Summarize error: {e}")
        return {
            "success": False,
            "summary": "",
            "error": str(e),
        }


# Note: /sync endpoint removed - LLM tools now fetch from /api/internal/notebook/* endpoints directly
