"""
File management module for project workspace files.

Handles file upload, download, list, delete operations for playground containers,
and sync to/from S3 for persistence.
"""

from .routes import router

__all__ = ["router"]
