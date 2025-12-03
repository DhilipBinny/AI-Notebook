"""
Chat Pydantic schemas for LLM interaction.

Note: Chat history is stored as JSON in S3/MinIO, not in the database.
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class CellContext(BaseModel):
    """A notebook cell provided as context to the LLM (built by backend from S3)."""
    cell_id: str  # From metadata.cell_id (Jupyter standard)
    type: str  # "code" or "markdown"
    content: str
    output: Optional[str] = None
    cell_number: Optional[int] = None


class ChatMessageCreate(BaseModel):
    """Schema for creating a chat message."""
    message: str
    context_cell_ids: List[str] = []  # Just cell IDs - backend loads content from S3


class PendingToolCall(BaseModel):
    """A tool call waiting for user approval."""
    id: str
    name: str
    arguments: Dict[str, Any]
    validation_reason: Optional[str] = None


class LLMStep(BaseModel):
    """A step in the LLM's reasoning process."""
    type: str  # "tool_call", "tool_result", "text"
    name: Optional[str] = None
    content: str
    timestamp: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    success: bool
    response: str
    error: Optional[str] = None
    pending_tool_calls: List[PendingToolCall] = []
    steps: List[LLMStep] = []
    updates: List[Dict[str, Any]] = []  # Notebook updates from LLM tools


class ExecuteToolsRequest(BaseModel):
    """Request to execute approved tools."""
    approved_tools: List[PendingToolCall]


class AICellRunRequest(BaseModel):
    """Request to run an AI Cell."""
    prompt: str
    context_cell_ids: List[str] = []  # Cell IDs for context - backend loads content from S3
    ai_cell_id: Optional[str] = None  # The AI cell's own ID for positional awareness
    ai_cell_index: Optional[int] = None  # The AI cell's position (0-based index)


class AICellResponse(BaseModel):
    """Response from AI Cell execution."""
    success: bool
    response: str
    model: str = ""
    error: Optional[str] = None
