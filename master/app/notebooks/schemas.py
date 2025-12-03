"""
Notebook Pydantic schemas.
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class AICellData(BaseModel):
    """AI Cell specific data."""
    user_prompt: str = ""
    llm_response: str = ""
    status: str = "idle"  # idle, running, completed, error
    model: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None


class CellData(BaseModel):
    """Notebook cell data - follows Jupyter .ipynb standard."""
    # Note: cell_id is stored in metadata.cell_id (Jupyter standard)
    # No top-level 'id' field - that's not standard .ipynb format
    cell_type: str  # "code", "markdown", "raw", or "ai"
    source: str
    outputs: List[Dict[str, Any]] = []
    execution_count: Optional[int] = None
    metadata: Dict[str, Any] = {}  # cell_id stored here
    ai_data: Optional[AICellData] = None  # Only for AI cells


class NotebookData(BaseModel):
    """Notebook data structure (compatible with .ipynb)."""
    cells: List[CellData] = []
    metadata: Dict[str, Any] = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.11.0"
        }
    }
    nbformat: int = 4
    nbformat_minor: int = 5


class NotebookSaveRequest(BaseModel):
    """Request to save notebook."""
    cells: List[CellData]
    metadata: Optional[Dict[str, Any]] = None


class NotebookResponse(BaseModel):
    """Response with notebook data."""
    project_id: str
    notebook: NotebookData
    last_modified: datetime
    version: int


class NotebookVersionInfo(BaseModel):
    """Notebook version information."""
    version: int
    saved_at: datetime
    size_bytes: int


class NotebookSyncCell(BaseModel):
    """Cell data for syncing to playground."""
    id: str
    type: str  # "code" or "markdown"
    content: str  # Cell source content
    output: Optional[str] = None  # Formatted output
    cellNumber: Optional[int] = None


class NotebookSyncRequest(BaseModel):
    """Request to sync notebook state to playground."""
    cells: List[NotebookSyncCell]


class NotebookImportRequest(BaseModel):
    """Request to import a .ipynb file."""
    ipynb_data: Dict[str, Any]  # The raw .ipynb JSON data
