"""
File management schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class FileInfo(BaseModel):
    """Information about a single file."""
    name: str
    path: str  # Relative path from workspace root
    size: int  # Size in bytes
    is_directory: bool = False
    modified_at: Optional[datetime] = None


class FileListResponse(BaseModel):
    """Response for file listing."""
    files: List[FileInfo]
    total_size: int  # Total size in bytes
    workspace_path: str


class FileUploadResponse(BaseModel):
    """Response after file upload."""
    success: bool
    path: str
    size: int
    message: str = ""


class FileSaveResponse(BaseModel):
    """Response after saving files to S3."""
    success: bool
    saved_count: int
    total_size: int
    saved_files: List[str]
    errors: List[str] = []


class FileRestoreResponse(BaseModel):
    """Response after restoring files from S3."""
    success: bool
    restored_count: int
    total_size: int
    restored_files: List[str]
    errors: List[str] = []


class FileDeleteRequest(BaseModel):
    """Request to delete files."""
    paths: List[str] = Field(..., min_length=1, description="List of file paths to delete")


class FileDeleteResponse(BaseModel):
    """Response after file deletion."""
    success: bool
    deleted_count: int
    deleted_files: List[str]
    errors: List[str] = []


# Configuration limits
FILE_UPLOAD_MAX_SIZE = 50 * 1024 * 1024  # 50MB per file
FILE_NAME_MAX_LENGTH = 255
WORKSPACE_MAX_SIZE = 500 * 1024 * 1024  # 500MB total workspace
ALLOWED_EXTENSIONS = {
    # Data files
    "csv", "json", "jsonl", "xml", "yaml", "yml", "txt", "tsv",
    # Python
    "py", "pyi", "pyx", "pxd",
    # Notebooks
    "ipynb",
    # Binary data
    "pkl", "pickle", "npy", "npz", "h5", "hdf5", "parquet", "feather",
    # Spreadsheets
    "xlsx", "xls",
    # Images
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico",
    # Documents
    "pdf", "md", "rst", "html", "css",
    # Config
    "ini", "cfg", "conf", "toml", "env",
    # Archives (for data)
    "zip", "tar", "gz",
    # SQL
    "sql", "db", "sqlite", "sqlite3",
}
