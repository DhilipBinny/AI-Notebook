"""
Chat Pydantic schemas for LLM interaction.
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from .models import MessageRole


class CellContext(BaseModel):
    """A notebook cell provided as context to the LLM."""
    id: str
    type: str  # "code" or "markdown"
    content: str
    output: Optional[str] = None
    cell_number: Optional[int] = None


class ChatMessageCreate(BaseModel):
    """Schema for creating a chat message."""
    message: str
    context: List[CellContext] = []


class ChatMessageResponse(BaseModel):
    """Schema for a chat message response."""
    id: str
    role: MessageRole
    content: str
    created_at: datetime
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


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


class ChatHistoryResponse(BaseModel):
    """Response containing chat history."""
    messages: List[ChatMessageResponse]
    total: int
