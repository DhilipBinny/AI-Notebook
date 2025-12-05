"""
Chat API routes.

Uses JSON-based chat history stored in MinIO with the new folder structure:
    {mm-yyyy}/{project_id}/chats/
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.dependencies import get_current_active_user
from app.users.models import User
from app.projects.service import ProjectService
from app.playgrounds.service import PlaygroundService
from app.notebooks.s3_client import s3_client as notebook_s3_client
from .service import ChatService
from .schemas import (
    ChatMessageCreate,
    ChatResponse,
    CellContext,
    ExecuteToolsRequest,
    AICellRunRequest,
    AICellResponse,
)

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["Chat"])


class ChatHistoryResponse(BaseModel):
    """Response for chat history endpoint."""
    success: bool
    project_id: str
    messages: List[Dict[str, Any]]
    chat_id: str = "default"


class SaveChatHistoryRequest(BaseModel):
    """Request to save chat history."""
    messages: List[Dict[str, Any]]
    chat_id: str = "default"


class ChatListResponse(BaseModel):
    """Response for list chats endpoint."""
    success: bool
    project_id: str
    chats: List[Dict[str, Any]]


class CreateChatRequest(BaseModel):
    """Request to create a new chat."""
    name: Optional[str] = None


class RenameChatRequest(BaseModel):
    """Request to rename a chat."""
    name: str


@router.get("", response_model=ChatHistoryResponse)
async def get_chat_history(
    project_id: str,
    chat_id: str = "default",
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

    chat_service = ChatService(project.storage_month)
    messages = chat_service.get_history(project_id, chat_id)

    return ChatHistoryResponse(
        success=True,
        project_id=project_id,
        messages=messages,
        chat_id=chat_id,
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

    chat_service = ChatService(project.storage_month)
    success = chat_service.save_history(project_id, request.messages, request.chat_id)

    if success:
        return {
            "success": True,
            "message": f"Chat history saved for project {project_id}",
            "chat_id": request.chat_id,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save chat history",
        )


@router.get("/list", response_model=ChatListResponse)
async def list_chats(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all chats for a project.
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    chat_service = ChatService(project.storage_month)
    chats = chat_service.list_chats(project_id)

    return ChatListResponse(
        success=True,
        project_id=project_id,
        chats=chats,
    )


@router.post("/new", response_model=dict)
async def create_chat(
    project_id: str,
    request: CreateChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new chat for a project.
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    chat_service = ChatService(project.storage_month)
    chat_id = chat_service.create_chat(project_id, request.name)

    if chat_id:
        return {
            "success": True,
            "chat_id": chat_id,
            "message": f"Created new chat: {chat_id}",
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chat",
        )


@router.put("/{chat_id}/rename", response_model=dict)
async def rename_chat(
    project_id: str,
    chat_id: str,
    request: RenameChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Rename a chat.
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    chat_service = ChatService(project.storage_month)
    success = chat_service.rename_chat(project_id, chat_id, request.name)

    if success:
        return {
            "success": True,
            "chat_id": chat_id,
            "message": f"Renamed chat to: {request.name}",
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rename chat",
        )


@router.delete("/{chat_id}", response_model=dict)
async def delete_chat(
    project_id: str,
    chat_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a chat (cannot delete default chat).
    """
    if chat_id == "default":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default chat",
        )

    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    chat_service = ChatService(project.storage_month)
    success = chat_service.delete_chat(project_id, chat_id)

    if success:
        return {
            "success": True,
            "message": f"Deleted chat: {chat_id}",
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chat",
        )


@router.post("", response_model=ChatResponse)
async def send_message(
    project_id: str,
    request: ChatMessageCreate,
    tool_mode: str = "manual",
    llm_provider: str = "gemini",
    context_format: str = "xml",
    chat_id: str = "default",
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
        llm_provider: LLM provider to use ("gemini", "openai", "anthropic", "ollama")
        context_format: Context format for LLM ("xml" or "plain")
        chat_id: Chat ID (default: "default")

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

    # Load cell content from S3 if cell IDs provided
    context: List[CellContext] = []
    if request.context_cell_ids:
        notebook_data = await notebook_s3_client.load_notebook(project.storage_month, project_id)
        if notebook_data and "cells" in notebook_data:
            # Build lookup by cell_id
            cell_id_set = set(request.context_cell_ids)
            for idx, cell in enumerate(notebook_data["cells"]):
                cell_id = cell.get("metadata", {}).get("cell_id", "")
                if cell_id in cell_id_set:
                    cell_type = cell.get("cell_type", "code")
                    ai_data = cell.get("ai_data", {})

                    # For AI cells, use ai_data content; for others, use source
                    if cell_type == "ai" and ai_data:
                        content = ai_data.get("user_prompt", "") or cell.get("source", "")
                        ai_prompt = ai_data.get("user_prompt", "")
                        ai_response = ai_data.get("llm_response", "")
                    else:
                        content = cell.get("source", "")
                        ai_prompt = None
                        ai_response = None

                    context.append(CellContext(
                        cell_id=cell_id,
                        type=cell_type,
                        content=content,
                        output=None,  # Don't include outputs
                        cell_number=idx + 1,
                        ai_prompt=ai_prompt,
                        ai_response=ai_response,
                    ))

    # Update playground activity (user is actively using it)
    if playground:
        await playground_service.update_activity(playground)

    # Send message
    chat_service = ChatService(project.storage_month)
    response = await chat_service.send_message(
        project=project,
        playground=playground,
        message=request.message,
        context=context,
        tool_mode=tool_mode,
        llm_provider=llm_provider,
        context_format=context_format,
        chat_id=chat_id,
    )

    return response


@router.post("/execute-tools", response_model=ChatResponse)
async def execute_tools(
    project_id: str,
    request: ExecuteToolsRequest,
    tool_mode: str = "manual",
    llm_provider: str = "gemini",
    context_format: str = "xml",
    chat_id: str = "default",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute approved tool calls.

    After the AI returns pending tool calls, the user can approve them
    and call this endpoint to execute the approved tools.

    Args:
        project_id: Project ID
        request: Approved tools to execute
        tool_mode: "auto", "manual", or "ai_decide"
        llm_provider: LLM provider to use ("gemini", "openai", "anthropic", "ollama")
        chat_id: Chat ID (default: "default")
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

    # Update playground activity (user is actively using it)
    await playground_service.update_activity(playground)

    # Execute tools
    chat_service = ChatService(project.storage_month)
    response = await chat_service.execute_tools(
        project=project,
        playground=playground,
        approved_tools=request.approved_tools,
        tool_mode=tool_mode,
        llm_provider=llm_provider,
        context_format=context_format,
        chat_id=chat_id,
    )

    return response


@router.delete("", status_code=status.HTTP_200_OK)
async def clear_chat_history(
    project_id: str,
    chat_id: str = "default",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Clear chat history for a project/chat.
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    chat_service = ChatService(project.storage_month)
    success = chat_service.clear_history(project_id, chat_id)

    return {
        "success": success,
        "message": f"Chat history cleared for project {project_id}, chat {chat_id}",
    }


@router.post("/ai-cell/run", response_model=AICellResponse)
async def run_ai_cell(
    project_id: str,
    request: AICellRunRequest,
    llm_provider: str = "gemini",
    context_format: str = "xml",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run an AI Cell - inline Q&A with notebook context and web search.

    AI Cells are a simpler form of LLM interaction:
    - Read-only access to notebook context
    - Web search capability for documentation/examples
    - No tool calling or cell modification
    - Returns markdown response with code suggestions

    Args:
        project_id: Project ID
        request: AI Cell run request with prompt and context cell IDs
        llm_provider: LLM provider to use
        context_format: Context format for LLM ("xml" or "plain")

    Returns:
        AICellResponse with AI response
    """
    import httpx

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

    if not playground or playground.status.value != "running":
        return AICellResponse(
            success=False,
            response="",
            error="Playground is not running. Start the playground to use AI cells.",
        )

    # Load full cell content from S3 for context
    context_list = []
    if request.context_cell_ids:
        notebook_data = await notebook_s3_client.load_notebook(project.storage_month, project_id)
        if notebook_data and "cells" in notebook_data:
            cell_id_set = set(request.context_cell_ids)
            for idx, cell in enumerate(notebook_data["cells"]):
                cell_id = cell.get("metadata", {}).get("cell_id", "")
                if cell_id in cell_id_set:
                    # Get output text if available
                    output_text = None
                    outputs = cell.get("outputs", [])
                    if outputs:
                        for output in outputs:
                            if output.get("output_type") == "stream":
                                text = output.get("text", "")
                                if isinstance(text, list):
                                    text = "".join(text)
                                output_text = text
                                break
                            elif output.get("output_type") in ("execute_result", "display_data"):
                                data = output.get("data", {})
                                if "text/plain" in data:
                                    output_text = data["text/plain"]
                                    if isinstance(output_text, list):
                                        output_text = "".join(output_text)
                                    break
                            elif output.get("output_type") == "error":
                                output_text = f"Error: {output.get('ename', '')}: {output.get('evalue', '')}"
                                break

                    cell_type = cell.get("cell_type", "code")
                    ai_data = cell.get("ai_data", {})

                    # For AI cells, include ai_data content
                    if cell_type == "ai" and ai_data:
                        content = ai_data.get("user_prompt", "") or cell.get("source", "")
                        ai_prompt = ai_data.get("user_prompt", "")
                        ai_response = ai_data.get("llm_response", "")
                    else:
                        content = cell.get("source", "")
                        ai_prompt = None
                        ai_response = None

                    context_list.append({
                        "id": cell_id,
                        "type": cell_type,
                        "content": content,
                        "output": output_text,
                        "cellNumber": idx + 1,
                        "ai_prompt": ai_prompt,
                        "ai_response": ai_response,
                    })

    try:
        async with httpx.AsyncClient() as client:
            # Set the LLM provider
            await client.post(
                f"{playground.internal_url}/llm/provider",
                headers={"X-Internal-Secret": playground.internal_secret},
                json={"provider": llm_provider},
                timeout=10,
            )

            # Call AI Cell endpoint
            response = await client.post(
                f"{playground.internal_url}/ai-cell/run",
                headers={"X-Internal-Secret": playground.internal_secret},
                json={
                    "prompt": request.prompt,
                    "context": context_list,
                    "ai_cell_id": request.ai_cell_id,
                    "ai_cell_index": request.ai_cell_index,
                    "session_id": project_id,
                    "context_format": context_format,
                },
                timeout=120,  # LLM can take a while
            )

            if response.status_code != 200:
                return AICellResponse(
                    success=False,
                    response="",
                    error=f"Playground returned error: {response.text}",
                )

            data = response.json()

            return AICellResponse(
                success=data.get("success", False),
                response=data.get("response", ""),
                model=data.get("model", llm_provider),
                error=data.get("error"),
            )

    except httpx.TimeoutException:
        return AICellResponse(
            success=False,
            response="",
            error="Request timed out. The AI is taking too long to respond.",
        )
    except Exception as e:
        return AICellResponse(
            success=False,
            response="",
            error=f"Error: {str(e)}",
        )
