"""
Notebook Pydantic schemas.
"""

from pydantic import BaseModel, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

# Maximum notebook size: 50MB (generous limit for notebooks with embedded images)
MAX_NOTEBOOK_SIZE_BYTES = 50 * 1024 * 1024


class ImageInput(BaseModel):
    """Image input for AI Cell (pasted or uploaded images)."""
    data: Optional[str] = None  # Base64 encoded image data
    mime_type: Optional[str] = "image/png"  # MIME type
    url: Optional[str] = None  # URL-based image
    filename: Optional[str] = None  # Original filename for display


class LLMStep(BaseModel):
    """Tool call step for AI Cell response."""
    type: str  # "tool_call", "tool_result", "text"
    name: Optional[str] = None  # Tool name
    content: str  # Arguments or result content


class AICellData(BaseModel):
    """AI Cell specific data."""
    user_prompt: str = ""
    llm_response: str = ""
    status: str = "idle"  # idle, running, completed, error
    model: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None
    images: Optional[List[ImageInput]] = None  # Pasted/uploaded images for visual analysis
    steps: Optional[List[LLMStep]] = None  # Tool call steps


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

    @model_validator(mode='after')
    def validate_size(self) -> 'NotebookSaveRequest':
        """Validate notebook size to prevent DoS attacks."""
        # Estimate size by serializing to JSON
        size = len(json.dumps([c.model_dump() for c in self.cells]))
        if size > MAX_NOTEBOOK_SIZE_BYTES:
            raise ValueError(
                f"Notebook size ({size / 1024 / 1024:.1f}MB) exceeds "
                f"maximum allowed ({MAX_NOTEBOOK_SIZE_BYTES / 1024 / 1024:.0f}MB)"
            )
        return self


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

    @model_validator(mode='after')
    def validate_size(self) -> 'NotebookImportRequest':
        """Validate notebook size to prevent DoS attacks."""
        size = len(json.dumps(self.ipynb_data))
        if size > MAX_NOTEBOOK_SIZE_BYTES:
            raise ValueError(
                f"Notebook size ({size / 1024 / 1024:.1f}MB) exceeds "
                f"maximum allowed ({MAX_NOTEBOOK_SIZE_BYTES / 1024 / 1024:.0f}MB)"
            )
        return self
