"""
File management service.

Handles file operations between:
- Browser <-> Master API <-> Playground Container (via docker cp)
- Playground Container <-> S3 (for persistence)
"""

import os
import io
import shlex
import tarfile
import tempfile
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime, timezone

import docker
from docker.errors import NotFound, APIError
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from .schemas import (
    FileInfo,
    FILE_UPLOAD_MAX_SIZE,
    FILE_NAME_MAX_LENGTH,
    WORKSPACE_MAX_SIZE,
    ALLOWED_EXTENSIONS,
)

logger = logging.getLogger(__name__)


class FileService:
    """Service for managing workspace files."""

    WORKSPACE_PATH = "/workspace"  # Path inside container

    def __init__(self):
        self.docker_client = docker.from_env()
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4"),
        )
        self.bucket = settings.s3_bucket_notebooks

    def _get_container(self, container_name: str):
        """Get container by name."""
        try:
            return self.docker_client.containers.get(container_name)
        except NotFound:
            raise ValueError(f"Container {container_name} not found")
        except APIError as e:
            raise RuntimeError(f"Docker error: {e}")

    def _validate_filename(self, filename: str) -> Tuple[bool, str]:
        """Validate filename for security and constraints."""
        if not filename:
            return False, "Filename cannot be empty"

        if len(filename) > FILE_NAME_MAX_LENGTH:
            return False, f"Filename too long (max {FILE_NAME_MAX_LENGTH} chars)"

        # Security checks
        if ".." in filename:
            return False, "Path traversal not allowed"

        if filename.startswith("/"):
            return False, "Absolute paths not allowed"

        # Check for dangerous characters
        dangerous_chars = ["<", ">", ":", '"', "|", "?", "*", "\x00"]
        for char in dangerous_chars:
            if char in filename:
                return False, f"Invalid character in filename: {char}"

        # Check extension (if has one)
        if "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower()
            if ext and ext not in ALLOWED_EXTENSIONS:
                return False, f"File extension '.{ext}' not allowed"

        return True, ""

    def _validate_file_size(self, size: int) -> Tuple[bool, str]:
        """Validate file size."""
        if size > FILE_UPLOAD_MAX_SIZE:
            max_mb = FILE_UPLOAD_MAX_SIZE / (1024 * 1024)
            return False, f"File too large (max {max_mb}MB)"
        return True, ""

    async def list_files(
        self,
        container_name: str,
        path: str = "",
    ) -> Tuple[List[FileInfo], int]:
        """
        List files in the workspace directory.

        Args:
            container_name: Docker container name
            path: Subdirectory path (relative to workspace)

        Returns:
            Tuple of (list of FileInfo, total size in bytes)
        """
        container = self._get_container(container_name)

        # Build full path
        full_path = f"{self.WORKSPACE_PATH}/{path}".rstrip("/")

        # Execute ls command to get file listing
        try:
            exit_code, output = container.exec_run(
                ["/bin/bash", "-c", f"find {shlex.quote(full_path)} -maxdepth 1 -printf '%T@ %s %y %P\\n' 2>/dev/null"],
                demux=True,
            )

            stdout = output[0].decode("utf-8") if output[0] else ""
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return [], 0

        files = []
        total_size = 0

        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue

            parts = line.split(" ", 3)
            if len(parts) < 4:
                continue

            try:
                mtime = float(parts[0])
                size = int(parts[1])
                ftype = parts[2]
                name = parts[3]

                if not name:  # Skip the directory itself
                    continue

                is_dir = ftype == "d"
                file_path = f"{path}/{name}".lstrip("/") if path else name

                files.append(FileInfo(
                    name=name,
                    path=file_path,
                    size=size if not is_dir else 0,
                    is_directory=is_dir,
                    modified_at=datetime.fromtimestamp(mtime, tz=timezone.utc),
                ))

                if not is_dir:
                    total_size += size

            except (ValueError, IndexError):
                continue

        # Sort: directories first, then by name
        files.sort(key=lambda f: (not f.is_directory, f.name.lower()))

        return files, total_size

    async def upload_file(
        self,
        container_name: str,
        filename: str,
        content: bytes,
        path: str = "",
    ) -> FileInfo:
        """
        Upload a file to the container's workspace.

        Args:
            container_name: Docker container name
            filename: Name of the file
            content: File content as bytes
            path: Subdirectory path (relative to workspace)

        Returns:
            FileInfo of uploaded file
        """
        # Validate
        valid, error = self._validate_filename(filename)
        if not valid:
            raise ValueError(error)

        valid, error = self._validate_file_size(len(content))
        if not valid:
            raise ValueError(error)

        container = self._get_container(container_name)

        # Build target path
        if path:
            target_dir = f"{self.WORKSPACE_PATH}/{path}"
            target_path = f"{target_dir}/{filename}"

            # Ensure directory exists
            container.exec_run(["mkdir", "-p", target_dir])
        else:
            target_path = f"{self.WORKSPACE_PATH}/{filename}"

        # Create tar archive with the file
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            file_data = io.BytesIO(content)
            tarinfo = tarfile.TarInfo(name=filename)
            tarinfo.size = len(content)
            tarinfo.mtime = datetime.now().timestamp()
            tar.addfile(tarinfo, file_data)

        tar_stream.seek(0)

        # Copy to container
        target_dir = str(Path(target_path).parent)
        try:
            container.put_archive(target_dir, tar_stream.getvalue())
        except APIError as e:
            raise RuntimeError(f"Failed to upload file: {e}")

        file_path = f"{path}/{filename}".lstrip("/") if path else filename

        return FileInfo(
            name=filename,
            path=file_path,
            size=len(content),
            is_directory=False,
            modified_at=datetime.now(timezone.utc),
        )

    async def download_file(
        self,
        container_name: str,
        file_path: str,
    ) -> Tuple[bytes, str]:
        """
        Download a file from the container's workspace.

        Args:
            container_name: Docker container name
            file_path: Path relative to workspace

        Returns:
            Tuple of (file content, filename)
        """
        # Validate path
        if ".." in file_path:
            raise ValueError("Path traversal not allowed")

        container = self._get_container(container_name)
        full_path = f"{self.WORKSPACE_PATH}/{file_path}"

        try:
            # Get file as tar archive
            bits, stat = container.get_archive(full_path)

            # Extract from tar
            tar_stream = io.BytesIO()
            for chunk in bits:
                tar_stream.write(chunk)
            tar_stream.seek(0)

            with tarfile.open(fileobj=tar_stream, mode="r") as tar:
                member = tar.getmembers()[0]
                file_obj = tar.extractfile(member)
                if file_obj is None:
                    raise ValueError("Cannot read file (might be a directory)")
                content = file_obj.read()

            filename = Path(file_path).name
            return content, filename

        except NotFound:
            raise ValueError(f"File not found: {file_path}")
        except APIError as e:
            raise RuntimeError(f"Failed to download file: {e}")

    async def delete_files(
        self,
        container_name: str,
        paths: List[str],
    ) -> Tuple[List[str], List[str]]:
        """
        Delete files from the container's workspace.

        Args:
            container_name: Docker container name
            paths: List of file paths relative to workspace

        Returns:
            Tuple of (deleted paths, error messages)
        """
        container = self._get_container(container_name)
        deleted = []
        errors = []

        for path in paths:
            # Validate path
            if ".." in path:
                errors.append(f"Invalid path: {path}")
                continue

            full_path = f"{self.WORKSPACE_PATH}/{path}"

            try:
                exit_code, _ = container.exec_run(["rm", "-rf", full_path])
                if exit_code == 0:
                    deleted.append(path)
                else:
                    errors.append(f"Failed to delete: {path}")
            except Exception as e:
                errors.append(f"Error deleting {path}: {e}")

        return deleted, errors

    def _get_workspace_s3_prefix(self, storage_month: str, project_id: str) -> str:
        """Get S3 prefix for workspace files."""
        return f"{storage_month}/{project_id}/workspace/"

    async def save_to_s3(
        self,
        container_name: str,
        storage_month: str,
        project_id: str,
    ) -> Tuple[List[str], int, List[str]]:
        """
        Save all workspace files to S3.

        Args:
            container_name: Docker container name
            storage_month: Storage month folder (mm-yyyy)
            project_id: Project ID

        Returns:
            Tuple of (saved files, total size, errors)
        """
        container = self._get_container(container_name)
        saved_files = []
        total_size = 0
        errors = []

        # Get all files in workspace
        try:
            exit_code, output = container.exec_run(
                ["/bin/bash", "-c", f"find {shlex.quote(self.WORKSPACE_PATH)} -type f -printf '%P\\n' 2>/dev/null"],
                demux=True,
            )
            stdout = output[0].decode("utf-8") if output[0] else ""
        except Exception as e:
            return [], 0, [f"Failed to list files: {e}"]

        file_paths = [p.strip() for p in stdout.strip().split("\n") if p.strip()]

        if not file_paths:
            return [], 0, []

        s3_prefix = self._get_workspace_s3_prefix(storage_month, project_id)

        for file_path in file_paths:
            try:
                # Download from container
                content, _ = await self.download_file(container_name, file_path)

                # Upload to S3
                s3_key = f"{s3_prefix}{file_path}"
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=s3_key,
                    Body=content,
                )

                saved_files.append(file_path)
                total_size += len(content)
                logger.info(f"Saved {file_path} to S3 ({len(content)} bytes)")

            except Exception as e:
                errors.append(f"Failed to save {file_path}: {e}")
                logger.error(f"Failed to save {file_path}: {e}")

        return saved_files, total_size, errors

    async def restore_from_s3(
        self,
        container_name: str,
        storage_month: str,
        project_id: str,
    ) -> Tuple[List[str], int, List[str]]:
        """
        Restore workspace files from S3 to container.

        Args:
            container_name: Docker container name
            storage_month: Storage month folder (mm-yyyy)
            project_id: Project ID

        Returns:
            Tuple of (restored files, total size, errors)
        """
        container = self._get_container(container_name)
        restored_files = []
        total_size = 0
        errors = []

        s3_prefix = self._get_workspace_s3_prefix(storage_month, project_id)

        try:
            # List all files in S3 workspace
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=s3_prefix)

            for page in pages:
                for obj in page.get("Contents", []):
                    s3_key = obj["Key"]
                    # Get relative path
                    file_path = s3_key[len(s3_prefix):]

                    if not file_path:
                        continue

                    try:
                        # Download from S3
                        response = self.s3_client.get_object(
                            Bucket=self.bucket,
                            Key=s3_key,
                        )
                        content = response["Body"].read()

                        # Upload to container
                        await self.upload_file(
                            container_name,
                            Path(file_path).name,
                            content,
                            str(Path(file_path).parent) if "/" in file_path else "",
                        )

                        restored_files.append(file_path)
                        total_size += len(content)
                        logger.info(f"Restored {file_path} from S3 ({len(content)} bytes)")

                    except Exception as e:
                        errors.append(f"Failed to restore {file_path}: {e}")
                        logger.error(f"Failed to restore {file_path}: {e}")

        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchKey":
                errors.append(f"S3 error: {e}")

        return restored_files, total_size, errors

    async def clear_s3_workspace(
        self,
        storage_month: str,
        project_id: str,
    ) -> None:
        """Delete all workspace files from S3."""
        s3_prefix = self._get_workspace_s3_prefix(storage_month, project_id)

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=s3_prefix)

            for page in pages:
                for obj in page.get("Contents", []):
                    self.s3_client.delete_object(
                        Bucket=self.bucket,
                        Key=obj["Key"],
                    )
                    logger.info(f"Deleted {obj['Key']} from S3")

        except ClientError as e:
            logger.error(f"Failed to clear S3 workspace: {e}")


# Singleton instance
file_service = FileService()
