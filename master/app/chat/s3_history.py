"""
S3/MinIO-based chat history storage.

Stores chat history as JSON files in MinIO, similar to the original backend.
Path format: {user_id}/{project_id}/chat_history.json
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChatHistoryS3Client:
    """Client for storing chat history in S3/MinIO."""

    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        self.bucket = settings.s3_bucket_notebooks

    def _get_history_path(self, user_id: str, project_id: str) -> str:
        """Get S3 path for chat history file."""
        return f"{user_id}/{project_id}/chat_history.json"

    def load_history(self, user_id: str, project_id: str) -> List[Dict[str, Any]]:
        """
        Load chat history from S3.

        Args:
            user_id: User ID
            project_id: Project ID

        Returns:
            List of message dicts with role, content, timestamp, and optional steps
        """
        path = self._get_history_path(user_id, project_id)

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=path)
            data = json.loads(response["Body"].read().decode("utf-8"))
            return data.get("messages", [])
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                # No history yet
                return []
            logger.error(f"Failed to load chat history: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to load chat history: {e}")
            return []

    def save_history(
        self,
        user_id: str,
        project_id: str,
        messages: List[Dict[str, Any]],
    ) -> bool:
        """
        Save chat history to S3.

        Args:
            user_id: User ID
            project_id: Project ID
            messages: List of message dicts

        Returns:
            True if successful
        """
        path = self._get_history_path(user_id, project_id)

        try:
            # Load existing to preserve created timestamp
            existing_data = {}
            try:
                response = self.client.get_object(Bucket=self.bucket, Key=path)
                existing_data = json.loads(response["Body"].read().decode("utf-8"))
            except ClientError:
                pass

            # Build data
            data = {
                "project_id": project_id,
                "created": existing_data.get("created", datetime.now().isoformat()),
                "updated": datetime.now().isoformat(),
                "messages": messages,
            }

            # Save to S3
            self.client.put_object(
                Bucket=self.bucket,
                Key=path,
                Body=json.dumps(data, indent=2, ensure_ascii=False),
                ContentType="application/json",
            )

            logger.info(f"Saved chat history: {path} ({len(messages)} messages)")
            return True

        except Exception as e:
            logger.error(f"Failed to save chat history: {e}")
            return False

    def add_message(
        self,
        user_id: str,
        project_id: str,
        role: str,
        content: str,
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Add a single message to chat history.

        Args:
            user_id: User ID
            project_id: Project ID
            role: Message role ('user' or 'assistant')
            content: Message content
            steps: Optional list of LLM steps (tool calls, results)

        Returns:
            True if successful
        """
        messages = self.load_history(user_id, project_id)

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }

        if steps:
            message["steps"] = steps

        messages.append(message)
        return self.save_history(user_id, project_id, messages)

    def clear_history(self, user_id: str, project_id: str) -> bool:
        """
        Clear chat history for a project.

        Args:
            user_id: User ID
            project_id: Project ID

        Returns:
            True if successful
        """
        path = self._get_history_path(user_id, project_id)

        try:
            self.client.delete_object(Bucket=self.bucket, Key=path)
            logger.info(f"Cleared chat history: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear chat history: {e}")
            return False


# Singleton instance
chat_history_client = ChatHistoryS3Client()
