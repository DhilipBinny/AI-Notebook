"""
Chat models - currently empty as chat history is stored in S3/MinIO.

The chat_messages table has been deprecated in favor of JSON storage in:
    {mm-yyyy}/{project_id}/chats/{chat_id}.json
"""

# Note: ChatMessage database model has been removed.
# Chat history is now stored in MinIO as JSON files.
# See app/chat/s3_history.py for implementation.
