"""
Chat API routes.

Uses JSON-based chat history stored in MinIO (like the original backend).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.dependencies import get_current_active_user
from app.users.models import User
from app.projects.service import ProjectService
from app.playgrounds.service import PlaygroundService
from .service import ChatService
from .schemas import (
    ChatMessageCreate,
    ChatResponse,
    ExecuteToolsRequest,
)

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["Chat"])


class ChatHistoryResponse(BaseModel):
    """Response for chat history endpoint."""
    success: bool
    project_id: str
    messages: List[Dict[str, Any]]


class SaveChatHistoryRequest(BaseModel):
    """Request to save chat history."""
    messages: List[Dict[str, Any]]


@router.get("", response_model=ChatHistoryResponse)
async def get_chat_history(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get chat history for a project.

    Returns messages with: role, content, timestamp, steps (optional)
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    chat_service = ChatService(current_user.id)
    messages = chat_service.get_history(project_id)

    return ChatHistoryResponse(
        success=True,
        project_id=project_id,
        messages=messages,
    )


@router.post("/history", response_model=dict)
async def save_chat_history(
    project_id: str,
    request: SaveChatHistoryRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save chat history for a project.

    Used by frontend to save edited/deleted messages.
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    chat_service = ChatService(current_user.id)
    success = chat_service.save_history(project_id, request.messages)

    if success:
        return {
            "success": True,
            "message": f"Chat history saved for project {project_id}",
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save chat history",
        )


@router.post("", response_model=ChatResponse)
async def send_message(
    project_id: str,
    request: ChatMessageCreate,
    tool_mode: str = "manual",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message to the AI assistant.

    The assistant can:
    - Answer questions about selected cells
    - Write and edit code
    - Execute cells (with approval in manual mode)
    - Create documentation

    Args:
        project_id: Project ID
        request: Message and context
        tool_mode: "auto", "manual", or "ai_decide"

    Returns:
        ChatResponse with AI response and any pending tool calls
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Get playground
    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_project_id(project_id)

    # Send message
    chat_service = ChatService(current_user.id)
    response = await chat_service.send_message(
        project=project,
        playground=playground,
        message=request.message,
        context=request.context,
        tool_mode=tool_mode,
    )

    return response


@router.post("/execute-tools", response_model=ChatResponse)
async def execute_tools(
    project_id: str,
    request: ExecuteToolsRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute approved tool calls.

    After the AI returns pending tool calls, the user can approve them
    and call this endpoint to execute the approved tools.
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Get playground
    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_project_id(project_id)

    if playground is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No playground running",
        )

    # Execute tools
    chat_service = ChatService(current_user.id)
    response = await chat_service.execute_tools(
        project=project,
        playground=playground,
        approved_tools=request.approved_tools,
    )

    return response


@router.delete("", status_code=status.HTTP_200_OK)
async def clear_chat_history(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Clear chat history for a project.
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    chat_service = ChatService(current_user.id)
    success = chat_service.clear_history(project_id)

    return {
        "success": success,
        "message": f"Chat history cleared for project {project_id}",
    }
