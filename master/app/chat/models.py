"""
ChatMessage model for storing LLM conversation history.
"""

from sqlalchemy import Column, String, Text, DateTime, Enum as SQLEnum, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from uuid import uuid4

from app.db.base import Base


class MessageRole(str, enum.Enum):
    """Chat message role."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(Base):
    """Chat message model."""

    __tablename__ = "chat_messages"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Project reference
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Message content
    role = Column(SQLEnum(MessageRole, values_callable=lambda x: [e.value for e in x]), nullable=False)
    content = Column(Text, nullable=False)

    # Metadata (model info, tokens, etc.)
    message_metadata = Column("metadata", JSON, nullable=True)

    # Tool calls tracking
    tool_calls = Column(JSON, nullable=True)
    tool_results = Column(JSON, nullable=True)

    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Relationships
    project = relationship("Project", back_populates="chat_messages")

    def __repr__(self) -> str:
        return f"<ChatMessage {self.role.value} at {self.created_at}>"
