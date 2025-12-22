"""
File management API routes.

Handles file upload, download, list, delete, and S3 sync operations.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging
import io

from app.db.session import get_db
from app.auth.dependencies import get_current_active_user
from app.users.models import User
from app.projects.service import ProjectService
from app.playgrounds.service import PlaygroundService
from app.playgrounds.models import PlaygroundStatus
from .service import file_service
from .schemas import (
    FileInfo,
    FileListResponse,
    FileUploadResponse,
    FileSaveResponse,
    FileRestoreResponse,
    FileDeleteRequest,
    FileDeleteResponse,
    FILE_UPLOAD_MAX_SIZE,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/files", tags=["Files"])


async def get_running_playground(
    project_id: str,
    current_user: User,
    db: AsyncSession,
) -> tuple:
    """
    Verify project ownership and get running playground.

    Returns:
        Tuple of (project, playground)

    Raises:
        HTTPException if project not found or playground not running
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Playground is not running. Start the playground to manage files.",
        )

    return project, playground


@router.get("", response_model=FileListResponse)
async def list_files(
    project_id: str,
    path: str = Query("", description="Subdirectory path"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List files in the workspace directory.

    Args:
        project_id: Project ID
        path: Optional subdirectory path

    Returns:
        FileListResponse with list of files
    """
    project, playground = await get_running_playground(project_id, current_user, db)

    try:
        files, total_size = await file_service.list_files(
            playground.container_name,
            path,
        )

        return FileListResponse(
            files=files,
            total_size=total_size,
            workspace_path=path or "/",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {e}",
        )


@router.post("", response_model=FileUploadResponse)
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    path: str = Query("", description="Subdirectory path"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a file to the workspace.

    Args:
        project_id: Project ID
        file: File to upload
        path: Optional subdirectory path

    Returns:
        FileUploadResponse with upload result
    """
    project, playground = await get_running_playground(project_id, current_user, db)

    # Read file content
    content = await file.read()

    # Check size
    if len(content) > FILE_UPLOAD_MAX_SIZE:
        max_mb = FILE_UPLOAD_MAX_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_mb}MB.",
        )

    try:
        file_info = await file_service.upload_file(
            playground.container_name,
            file.filename,
            content,
            path,
        )

        return FileUploadResponse(
            success=True,
            path=file_info.path,
            size=file_info.size,
            message=f"Uploaded {file.filename} ({file_info.size} bytes)",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {e}",
        )


@router.post("/upload-multiple", response_model=List[FileUploadResponse])
async def upload_multiple_files(
    project_id: str,
    files: List[UploadFile] = File(...),
    path: str = Query("", description="Subdirectory path"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload multiple files to the workspace.

    Args:
        project_id: Project ID
        files: Files to upload
        path: Optional subdirectory path

    Returns:
        List of FileUploadResponse for each file
    """
    project, playground = await get_running_playground(project_id, current_user, db)

    results = []

    for file in files:
        try:
            content = await file.read()

            if len(content) > FILE_UPLOAD_MAX_SIZE:
                results.append(FileUploadResponse(
                    success=False,
                    path="",
                    size=len(content),
                    message=f"File too large: {file.filename}",
                ))
                continue

            file_info = await file_service.upload_file(
                playground.container_name,
                file.filename,
                content,
                path,
            )

            results.append(FileUploadResponse(
                success=True,
                path=file_info.path,
                size=file_info.size,
                message=f"Uploaded {file.filename}",
            ))

        except Exception as e:
            results.append(FileUploadResponse(
                success=False,
                path="",
                size=0,
                message=f"Failed to upload {file.filename}: {e}",
            ))

    return results


@router.get("/download/{file_path:path}")
async def download_file(
    project_id: str,
    file_path: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download a file from the workspace.

    Args:
        project_id: Project ID
        file_path: Path to file relative to workspace

    Returns:
        File content as streaming response
    """
    project, playground = await get_running_playground(project_id, current_user, db)

    try:
        content, filename = await file_service.download_file(
            playground.container_name,
            file_path,
        )

        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(content)),
            },
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {e}",
        )


@router.delete("", response_model=FileDeleteResponse)
async def delete_files(
    project_id: str,
    request: FileDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete files from the workspace.

    Args:
        project_id: Project ID
        request: List of file paths to delete

    Returns:
        FileDeleteResponse with deletion results
    """
    project, playground = await get_running_playground(project_id, current_user, db)

    try:
        deleted, errors = await file_service.delete_files(
            playground.container_name,
            request.paths,
        )

        return FileDeleteResponse(
            success=len(errors) == 0,
            deleted_count=len(deleted),
            deleted_files=deleted,
            errors=errors,
        )

    except Exception as e:
        logger.error(f"Failed to delete files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete files: {e}",
        )


@router.post("/save", response_model=FileSaveResponse)
async def save_files_to_s3(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save all workspace files to S3 for persistence.

    Args:
        project_id: Project ID

    Returns:
        FileSaveResponse with save results
    """
    project, playground = await get_running_playground(project_id, current_user, db)

    try:
        saved_files, total_size, errors = await file_service.save_to_s3(
            playground.container_name,
            project.storage_month,
            project_id,
        )

        return FileSaveResponse(
            success=len(errors) == 0,
            saved_count=len(saved_files),
            total_size=total_size,
            saved_files=saved_files,
            errors=errors,
        )

    except Exception as e:
        logger.error(f"Failed to save files to S3: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save files: {e}",
        )


@router.post("/restore", response_model=FileRestoreResponse)
async def restore_files_from_s3(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restore workspace files from S3.

    Args:
        project_id: Project ID

    Returns:
        FileRestoreResponse with restore results
    """
    project, playground = await get_running_playground(project_id, current_user, db)

    try:
        restored_files, total_size, errors = await file_service.restore_from_s3(
            playground.container_name,
            project.storage_month,
            project_id,
        )

        return FileRestoreResponse(
            success=len(errors) == 0,
            restored_count=len(restored_files),
            total_size=total_size,
            restored_files=restored_files,
            errors=errors,
        )

    except Exception as e:
        logger.error(f"Failed to restore files from S3: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore files: {e}",
        )


@router.get("/saved", response_model=FileListResponse)
async def list_saved_files(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List files saved in S3 (without requiring running playground).

    Args:
        project_id: Project ID

    Returns:
        FileListResponse with list of saved files
    """
    # Verify project ownership (no playground needed)
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    try:
        # List files directly from S3
        s3_prefix = file_service._get_workspace_s3_prefix(
            project.storage_month,
            project_id,
        )

        files = []
        total_size = 0

        paginator = file_service.s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=file_service.bucket, Prefix=s3_prefix)

        for page in pages:
            for obj in page.get("Contents", []):
                s3_key = obj["Key"]
                file_path = s3_key[len(s3_prefix):]

                if not file_path:
                    continue

                files.append(FileInfo(
                    name=file_path.split("/")[-1],
                    path=file_path,
                    size=obj["Size"],
                    is_directory=False,
                    modified_at=obj["LastModified"],
                ))
                total_size += obj["Size"]

        files.sort(key=lambda f: f.path.lower())

        return FileListResponse(
            files=files,
            total_size=total_size,
            workspace_path="/",
        )

    except Exception as e:
        logger.error(f"Failed to list saved files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list saved files: {e}",
        )
