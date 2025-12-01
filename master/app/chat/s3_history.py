"""
S3/MinIO-based chat history storage.

Storage structure:
    {mm-yyyy}/{project_id}/chats/
        default.json        # Default/main chat
        {chat_id}.json      # Additional chats
        index.json          # List of all chats

Each chat JSON contains:
    {
        "chat_id": "default",
        "name": "Main Chat",
        "project_id": "...",
        "created": "2025-01-29T09:00:00",
        "updated": "2025-01-29T10:00:00",
        "messages": [...]
    }
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_CHAT_ID = "default"
DEFAULT_CHAT_NAME = "Main Chat"


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

    def _get_chats_base_path(self, storage_month: str, project_id: str) -> str:
        """Get base path for chats: {mm-yyyy}/{project_id}/chats"""
        return f"{storage_month}/{project_id}/chats"

    def _get_chat_path(self, storage_month: str, project_id: str, chat_id: str = DEFAULT_CHAT_ID) -> str:
        """Get S3 path for a specific chat file."""
        base = self._get_chats_base_path(storage_month, project_id)
        return f"{base}/{chat_id}.json"

    def _get_index_path(self, storage_month: str, project_id: str) -> str:
        """Get S3 path for chat index file."""
        base = self._get_chats_base_path(storage_month, project_id)
        return f"{base}/index.json"

    def load_history(
        self,
        storage_month: str,
        project_id: str,
        chat_id: str = DEFAULT_CHAT_ID,
    ) -> List[Dict[str, Any]]:
        """
        Load chat history from S3.

        Args:
            storage_month: Storage month folder (mm-yyyy)
            project_id: Project ID
            chat_id: Chat ID (default: "default")

        Returns:
            List of message dicts with role, content, timestamp, and optional steps
        """
        path = self._get_chat_path(storage_month, project_id, chat_id)

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=path)
            data = json.loads(response["Body"].read().decode("utf-8"))
            return data.get("messages", [])
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return []
            logger.error(f"Failed to load chat history: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to load chat history: {e}")
            return []

    def save_history(
        self,
        storage_month: str,
        project_id: str,
        messages: List[Dict[str, Any]],
        chat_id: str = DEFAULT_CHAT_ID,
        chat_name: Optional[str] = None,
    ) -> bool:
        """
        Save chat history to S3.

        Args:
            storage_month: Storage month folder (mm-yyyy)
            project_id: Project ID
            messages: List of message dicts
            chat_id: Chat ID (default: "default")
            chat_name: Optional chat name

        Returns:
            True if successful
        """
        path = self._get_chat_path(storage_month, project_id, chat_id)

        try:
            # Load existing to preserve created timestamp and name
            existing_data = {}
            try:
                response = self.client.get_object(Bucket=self.bucket, Key=path)
                existing_data = json.loads(response["Body"].read().decode("utf-8"))
            except ClientError:
                pass

            now = datetime.now(timezone.utc).isoformat()

            # Build data
            data = {
                "chat_id": chat_id,
                "name": chat_name or existing_data.get("name") or (DEFAULT_CHAT_NAME if chat_id == DEFAULT_CHAT_ID else f"Chat {chat_id[:8]}"),
                "project_id": project_id,
                "created": existing_data.get("created", now),
                "updated": now,
                "messages": messages,
            }

            # Save to S3
            self.client.put_object(
                Bucket=self.bucket,
                Key=path,
                Body=json.dumps(data, indent=2, ensure_ascii=False),
                ContentType="application/json",
            )

            # Update chat index
            self._update_chat_index(storage_month, project_id, chat_id, data["name"], data["created"], now)

            logger.info(f"Saved chat history: {path} ({len(messages)} messages)")
            return True

        except Exception as e:
            logger.error(f"Failed to save chat history: {e}")
            return False

    def _update_chat_index(
        self,
        storage_month: str,
        project_id: str,
        chat_id: str,
        name: str,
        created: str,
        updated: str,
    ) -> None:
        """Update the chat index file."""
        index_path = self._get_index_path(storage_month, project_id)

        try:
            # Load existing index
            index_data = {"chats": []}
            try:
                response = self.client.get_object(Bucket=self.bucket, Key=index_path)
                index_data = json.loads(response["Body"].read().decode("utf-8"))
            except ClientError:
                pass

            # Find and update or add chat entry
            chats = index_data.get("chats", [])
            found = False
            for chat in chats:
                if chat.get("id") == chat_id:
                    chat["name"] = name
                    chat["updated"] = updated
                    found = True
                    break

            if not found:
                chats.append({
                    "id": chat_id,
                    "name": name,
                    "created": created,
                    "updated": updated,
                })

            # Sort by updated (most recent first)
            chats.sort(key=lambda x: x.get("updated", ""), reverse=True)
            index_data["chats"] = chats

            # Save index
            self.client.put_object(
                Bucket=self.bucket,
                Key=index_path,
                Body=json.dumps(index_data, indent=2),
                ContentType="application/json",
            )

        except Exception as e:
            logger.error(f"Failed to update chat index: {e}")

    def add_message(
        self,
        storage_month: str,
        project_id: str,
        role: str,
        content: str,
        steps: Optional[List[Dict[str, Any]]] = None,
        chat_id: str = DEFAULT_CHAT_ID,
    ) -> bool:
        """
        Add a single message to chat history.

        Args:
            storage_month: Storage month folder (mm-yyyy)
            project_id: Project ID
            role: Message role ('user' or 'assistant')
            content: Message content
            steps: Optional list of LLM steps (tool calls, results)
            chat_id: Chat ID (default: "default")

        Returns:
            True if successful
        """
        messages = self.load_history(storage_month, project_id, chat_id)

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if steps:
            message["steps"] = steps

        messages.append(message)
        return self.save_history(storage_month, project_id, messages, chat_id)

    def list_chats(self, storage_month: str, project_id: str) -> List[Dict[str, Any]]:
        """
        List all chats for a project.

        Args:
            storage_month: Storage month folder (mm-yyyy)
            project_id: Project ID

        Returns:
            List of chat info dicts with id, name, created, updated
        """
        index_path = self._get_index_path(storage_month, project_id)

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=index_path)
            data = json.loads(response["Body"].read().decode("utf-8"))
            return data.get("chats", [])
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return []
            logger.error(f"Failed to list chats: {e}")
            return []

    def create_chat(
        self,
        storage_month: str,
        project_id: str,
        name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a new chat for a project.

        Args:
            storage_month: Storage month folder (mm-yyyy)
            project_id: Project ID
            name: Optional chat name

        Returns:
            New chat ID or None if failed
        """
        chat_id = f"chat-{uuid4().hex[:12]}"
        chat_name = name or f"Chat {chat_id[:12]}"

        # Save empty chat to create it
        if self.save_history(storage_month, project_id, [], chat_id, chat_name):
            return chat_id
        return None

    def rename_chat(
        self,
        storage_month: str,
        project_id: str,
        chat_id: str,
        new_name: str,
    ) -> bool:
        """
        Rename a chat.

        Args:
            storage_month: Storage month folder (mm-yyyy)
            project_id: Project ID
            chat_id: Chat ID
            new_name: New chat name

        Returns:
            True if successful
        """
        messages = self.load_history(storage_month, project_id, chat_id)
        return self.save_history(storage_month, project_id, messages, chat_id, new_name)

    def delete_chat(
        self,
        storage_month: str,
        project_id: str,
        chat_id: str,
    ) -> bool:
        """
        Delete a specific chat.

        Args:
            storage_month: Storage month folder (mm-yyyy)
            project_id: Project ID
            chat_id: Chat ID

        Returns:
            True if successful
        """
        if chat_id == DEFAULT_CHAT_ID:
            logger.warning("Cannot delete default chat")
            return False

        path = self._get_chat_path(storage_month, project_id, chat_id)

        try:
            self.client.delete_object(Bucket=self.bucket, Key=path)

            # Update index
            self._remove_from_chat_index(storage_month, project_id, chat_id)

            logger.info(f"Deleted chat: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete chat: {e}")
            return False

    def _remove_from_chat_index(self, storage_month: str, project_id: str, chat_id: str) -> None:
        """Remove a chat from the index."""
        index_path = self._get_index_path(storage_month, project_id)

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=index_path)
            index_data = json.loads(response["Body"].read().decode("utf-8"))

            chats = [c for c in index_data.get("chats", []) if c.get("id") != chat_id]
            index_data["chats"] = chats

            self.client.put_object(
                Bucket=self.bucket,
                Key=index_path,
                Body=json.dumps(index_data, indent=2),
                ContentType="application/json",
            )
        except Exception as e:
            logger.error(f"Failed to remove from chat index: {e}")

    def clear_history(
        self,
        storage_month: str,
        project_id: str,
        chat_id: str = DEFAULT_CHAT_ID,
    ) -> bool:
        """
        Clear chat history (delete messages but keep chat).

        Args:
            storage_month: Storage month folder (mm-yyyy)
            project_id: Project ID
            chat_id: Chat ID (default: "default")

        Returns:
            True if successful
        """
        return self.save_history(storage_month, project_id, [], chat_id)


# Singleton instance
chat_history_client = ChatHistoryS3Client()
