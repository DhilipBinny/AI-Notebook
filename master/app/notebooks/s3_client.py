"""
S3/MinIO client for notebook storage.

Storage structure:
    {mm-yyyy}/{project_id}/
        notebook.ipynb          # Current notebook
        notebook.v{N}.ipynb     # Version backups (max 5)
        metadata.json           # Notebook metadata
        chats/
            default.json        # Default chat
            {chat_id}.json      # Additional chats
            index.json          # Chat index
"""

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Client:
    """Client for S3/MinIO storage operations."""

    MAX_VERSIONS = 5  # Keep only last 5 versions

    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4"),
        )
        self.bucket = settings.s3_bucket_notebooks

    def _get_base_path(self, storage_month: str, project_id: str) -> str:
        """Get base S3 path: {mm-yyyy}/{project_id}"""
        return f"{storage_month}/{project_id}"

    def _get_notebook_key(self, storage_month: str, project_id: str, version: Optional[int] = None) -> str:
        """Get S3 key for notebook."""
        base = self._get_base_path(storage_month, project_id)
        if version:
            return f"{base}/notebook.v{version}.ipynb"
        return f"{base}/notebook.ipynb"

    def _get_metadata_key(self, storage_month: str, project_id: str) -> str:
        """Get S3 key for notebook metadata."""
        base = self._get_base_path(storage_month, project_id)
        return f"{base}/metadata.json"

    async def save_notebook(
        self,
        storage_month: str,
        project_id: str,
        notebook_data: Dict[str, Any],
        create_version: bool = True,
    ) -> Dict[str, Any]:
        """
        Save notebook to S3.

        Args:
            storage_month: Storage month folder (mm-yyyy)
            project_id: Project ID
            notebook_data: Notebook data dict
            create_version: Whether to create a version backup

        Returns:
            Dict with save info (version, timestamp, etc.)
        """
        try:
            # Get current version
            metadata = await self.get_metadata(storage_month, project_id)
            current_version = metadata.get("version", 0) if metadata else 0
            new_version = current_version + 1

            # Convert to JSON
            notebook_json = json.dumps(notebook_data, indent=2)
            notebook_bytes = notebook_json.encode("utf-8")

            # Save current notebook
            key = self._get_notebook_key(storage_month, project_id)
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=notebook_bytes,
                ContentType="application/json",
            )

            # Create version backup
            if create_version:
                version_key = self._get_notebook_key(storage_month, project_id, new_version)
                self.client.put_object(
                    Bucket=self.bucket,
                    Key=version_key,
                    Body=notebook_bytes,
                    ContentType="application/json",
                )

            # Update metadata
            now = datetime.now(timezone.utc)
            new_metadata = {
                "version": new_version,
                "last_modified": now.isoformat(),
                "size_bytes": len(notebook_bytes),
                "cell_count": len(notebook_data.get("cells", [])),
            }
            await self.save_metadata(storage_month, project_id, new_metadata)

            # Cleanup old versions (keep only MAX_VERSIONS)
            if create_version:
                await self._cleanup_old_versions(storage_month, project_id)

            logger.info(f"Saved notebook for project {project_id}, version {new_version}")

            return {
                "version": new_version,
                "saved_at": now,
                "size_bytes": len(notebook_bytes),
            }

        except ClientError as e:
            logger.error(f"Failed to save notebook: {e}")
            raise RuntimeError(f"Failed to save notebook: {e}")

    async def load_notebook(
        self,
        storage_month: str,
        project_id: str,
        version: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Load notebook from S3.

        Args:
            storage_month: Storage month folder (mm-yyyy)
            project_id: Project ID
            version: Specific version to load (None for latest)

        Returns:
            Notebook data dict or None if not found
        """
        try:
            key = self._get_notebook_key(storage_month, project_id, version)
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            return json.loads(content)

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            logger.error(f"Failed to load notebook: {e}")
            raise RuntimeError(f"Failed to load notebook: {e}")

    async def get_metadata(self, storage_month: str, project_id: str) -> Optional[Dict[str, Any]]:
        """Get notebook metadata."""
        try:
            key = self._get_metadata_key(storage_month, project_id)
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            return json.loads(content)

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            logger.error(f"Failed to get metadata: {e}")
            return None

    async def save_metadata(self, storage_month: str, project_id: str, metadata: Dict[str, Any]) -> None:
        """Save notebook metadata."""
        try:
            key = self._get_metadata_key(storage_month, project_id)
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(metadata).encode("utf-8"),
                ContentType="application/json",
            )
        except ClientError as e:
            logger.error(f"Failed to save metadata: {e}")

    async def _cleanup_old_versions(self, storage_month: str, project_id: str) -> None:
        """Delete old versions, keeping only the last MAX_VERSIONS."""
        try:
            versions = await self.list_versions(storage_month, project_id)

            if len(versions) > self.MAX_VERSIONS:
                # versions are sorted by version number descending (newest first)
                versions_to_delete = versions[self.MAX_VERSIONS:]

                for v in versions_to_delete:
                    version_key = self._get_notebook_key(storage_month, project_id, v["version"])
                    self.client.delete_object(
                        Bucket=self.bucket,
                        Key=version_key,
                    )
                    logger.info(f"Deleted old version {v['version']} for project {project_id}")

        except ClientError as e:
            logger.error(f"Failed to cleanup old versions: {e}")

    async def list_versions(self, storage_month: str, project_id: str) -> list:
        """List all notebook versions."""
        try:
            base = self._get_base_path(storage_month, project_id)
            prefix = f"{base}/notebook.v"
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
            )

            versions = []
            for obj in response.get("Contents", []):
                key = obj["Key"]
                # Extract version number from key
                try:
                    version_str = key.split(".v")[1].split(".ipynb")[0]
                    version = int(version_str)
                    versions.append({
                        "version": version,
                        "saved_at": obj["LastModified"],
                        "size_bytes": obj["Size"],
                    })
                except (IndexError, ValueError):
                    continue

            return sorted(versions, key=lambda x: x["version"], reverse=True)

        except ClientError as e:
            logger.error(f"Failed to list versions: {e}")
            return []

    async def delete_notebook(self, storage_month: str, project_id: str) -> None:
        """Delete all notebook data for a project (including chats)."""
        try:
            base = self._get_base_path(storage_month, project_id)
            prefix = f"{base}/"
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
            )

            for obj in response.get("Contents", []):
                self.client.delete_object(
                    Bucket=self.bucket,
                    Key=obj["Key"],
                )

            logger.info(f"Deleted all data for project {project_id}")

        except ClientError as e:
            logger.error(f"Failed to delete notebook: {e}")


# Singleton instance
s3_client = S3Client()
