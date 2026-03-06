"""
API Models - Pydantic models for all API endpoints

Organized by category:
- Base types (CellContext, ChatMessage, etc.)
- Chat models (ChatRequest, ChatResponse)
- AI Cell models (AICellRequest, AICellResponse)
- LLM Complete models
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel


# =============================================================================
# Base Types
# =============================================================================

class CellContext(BaseModel):
    """Cell context passed from frontend."""
    id: str
    type: str  # "code", "markdown", or "ai"
    content: str
    output: Optional[str] = None
    cellNumber: Optional[int] = None
    # AI Cell specific fields
    ai_prompt: Optional[str] = None  # User's question in AI cell
    ai_response: Optional[str] = None  # LLM's response in AI cell


class ChatMessage(BaseModel):
    """Chat message in conversation history."""
    role: str  # "user" or "assistant"
    content: str


class ImageInput(BaseModel):
    """Image input for visual analysis - supports base64 data or URL."""
    data: Optional[str] = None  # Base64 encoded image data
    mime_type: Optional[str] = "image/png"  # MIME type
    url: Optional[str] = None  # URL-based image
    filename: Optional[str] = None  # Original filename for display


class LLMStep(BaseModel):
    """A step in LLM processing (tool call, result, etc.)."""
    type: str
    name: Optional[str] = None
    content: str
    timestamp: Optional[str] = None


class PendingToolCall(BaseModel):
    """A tool call pending user approval."""
    id: str
    name: str
    arguments: Dict[str, Any]


# =============================================================================
# Chat Models
# =============================================================================

class ChatRequest(BaseModel):
    """Request for chat endpoint."""
    message: str
    context: List[CellContext] = []
    history: List[ChatMessage] = []
    session_id: Optional[str] = None
    context_format: str = "xml"  # "plain", "xml", or "json"
    images: Optional[List[ImageInput]] = None
    llm_provider: Optional[str] = None  # Override LLM provider
    tool_mode: Optional[str] = None  # "auto", "manual", "ai_decide"
    system_prompt: Optional[str] = None  # Override system prompt from admin DB


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    success: bool
    response: str
    error: Optional[str] = None
    updates: List[Dict[str, Any]] = []
    pending_tool_calls: List[PendingToolCall] = []
    steps: List[LLMStep] = []


class ExecuteToolsRequest(BaseModel):
    """Request to execute approved tools."""
    session_id: str
    approved_tools: List[PendingToolCall]


# =============================================================================
# AI Cell Models
# =============================================================================

class AICellRequest(BaseModel):
    """Request for AI Cell execution."""
    prompt: str
    context: List[CellContext] = []
    images: Optional[List[ImageInput]] = None
    ai_cell_id: Optional[str] = None  # The AI cell's own ID
    ai_cell_index: Optional[int] = None  # The AI cell's position (0-based)
    session_id: Optional[str] = None
    context_format: str = "xml"
    llm_provider: Optional[str] = None
    system_prompt: Optional[str] = None  # Override system prompt from admin DB
    allowed_tools: Optional[List[str]] = None  # Mode-specific tool allowlist


class AICellResponse(BaseModel):
    """Response from AI Cell."""
    success: bool
    response: str
    model: str = ""
    error: Optional[str] = None
    steps: List[LLMStep] = []


class AICellCancelRequest(BaseModel):
    """Request to cancel an AI Cell execution."""
    session_id: str


class AICellCancelResponse(BaseModel):
    """Response from AI Cell cancellation."""
    success: bool
    message: str


# =============================================================================
# LLM Complete Models
# =============================================================================

class LLMCompleteRequest(BaseModel):
    """Request for simple LLM completion (no tools)."""
    prompt: str
    max_tokens: int = 1000
    llm_provider: Optional[str] = None
