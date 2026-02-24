"""
Chat API routes.

Uses JSON-based chat history stored in MinIO with the new folder structure:
    {mm-yyyy}/{project_id}/chats/
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import httpx
import json

from app.db.session import get_db, AsyncSessionLocal
from app.auth.dependencies import get_current_active_user
from app.users.models import User
from app.projects.service import ProjectService
from app.playgrounds.service import PlaygroundService
from app.notebooks.s3_client import s3_client as notebook_s3_client
from app.api_keys.service import ApiKeyService
from app.credits.service import CreditService
from app.platform_keys.service import PlatformKeyService
from app.system_prompts.service import SystemPromptService
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


async def _build_proxy_headers(
    db: AsyncSession,
    user_id: str,
    playground,
    llm_provider: str,
) -> tuple[dict, bool]:
    """
    Build proxy headers with API key injection for playground requests.

    Resolution order: user key > platform key > container env fallback.

    Returns:
        (headers_dict, is_own_key) tuple
    """
    headers = {"X-Internal-Secret": playground.internal_secret}

    # User keys
    api_key_service = ApiKeyService(db)
    user_keys = await api_key_service.get_all_decrypted_keys(user_id)
    user_key_headers = {
        "openai": "X-User-OpenAI-Key",
        "anthropic": "X-User-Anthropic-Key",
        "gemini": "X-User-Gemini-Key",
        "openai_compatible": "X-User-OpenaiCompatible-Key",
    }
    for provider, key in user_keys.items():
        header = user_key_headers.get(provider)
        if header:
            headers[header] = key

    # User base_url for openai_compatible
    user_all_keys = await api_key_service.get_for_user(user_id)
    for uk in user_all_keys:
        if uk.provider.value == "openai_compatible" and uk.is_active and uk.base_url:
            headers["X-User-OpenaiCompatible-BaseUrl"] = uk.base_url
            break

    # Platform keys
    pk_service = PlatformKeyService(db)
    platform_keys = await pk_service.get_all_active_keys()
    platform_models = await pk_service.get_active_models()
    platform_base_urls = await pk_service.get_active_base_urls()
    platform_auth_types = await pk_service.get_active_auth_types()
    platform_key_headers = {
        "openai": ("X-Platform-OpenAI-Key", "X-Platform-OpenAI-Model"),
        "anthropic": ("X-Platform-Anthropic-Key", "X-Platform-Anthropic-Model"),
        "gemini": ("X-Platform-Gemini-Key", "X-Platform-Gemini-Model"),
        "openai_compatible": ("X-Platform-OpenaiCompatible-Key", "X-Platform-OpenaiCompatible-Model"),
    }
    for provider, key in platform_keys.items():
        hdr = platform_key_headers.get(provider)
        if hdr:
            headers[hdr[0]] = key
            if provider in platform_models:
                headers[hdr[1]] = platform_models[provider]

    # Platform auth_type for anthropic (OAuth token support)
    if "anthropic" in platform_auth_types:
        headers["X-Platform-Anthropic-AuthType"] = platform_auth_types["anthropic"]

    # Platform base_url for openai_compatible
    if "openai_compatible" in platform_base_urls:
        headers["X-Platform-OpenaiCompatible-BaseUrl"] = platform_base_urls["openai_compatible"]

    is_own_key = llm_provider in user_keys
    headers["X-User-Is-Own-Key"] = "true" if is_own_key else "false"

    return headers, is_own_key


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


# =============================================================================
# DEPRECATED: JSON ENDPOINTS - Replaced by SSE streaming endpoints below
# =============================================================================
# These endpoints have been replaced by /stream and /execute-tools/stream
# which provide real-time progress updates via Server-Sent Events.
# Kept commented for reference.

# @router.post("", response_model=ChatResponse)
# async def send_message(
#     project_id: str,
#     request: ChatMessageCreate,
#     tool_mode: str = "manual",
#     llm_provider: str = "gemini",
#     context_format: str = "xml",
#     chat_id: str = "default",
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     """Send a message to the AI assistant (JSON response)."""
#     ...  # Original implementation commented out

# @router.post("/execute-tools", response_model=ChatResponse)
# async def execute_tools(
#     project_id: str,
#     request: ExecuteToolsRequest,
#     tool_mode: str = "manual",
#     llm_provider: str = "gemini",
#     context_format: str = "xml",
#     chat_id: str = "default",
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     """Execute approved tool calls (JSON response)."""
#     ...  # Original implementation commented out


# =============================================================================
# SSE STREAMING ENDPOINTS
# =============================================================================

@router.post("/stream")
async def send_message_stream(
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
    Send a message to the AI assistant with SSE streaming.

    Proxies to playground's /chat/stream endpoint for real-time progress events.

    SSE Events:
    - event: thinking - Status message
    - event: tool_call - Tool being called
    - event: tool_result - Tool execution result
    - event: pending_tools - Tools awaiting approval
    - event: done - Final response
    - event: error - Error occurred
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
    playground = await playground_service.get_by_user_id(current_user.id)

    if not playground or playground.status.value != "running":
        async def error_stream():
            yield f"event: error\ndata: {json.dumps({'error': 'Playground is not running. Start the playground to enable AI assistance.'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # Load cell content from S3 if cell IDs provided
    context_list = []
    if request.context_cell_ids:
        notebook_data = await notebook_s3_client.load_notebook(project.storage_month, project_id)
        if notebook_data and "cells" in notebook_data:
            cell_id_set = set(request.context_cell_ids)
            for idx, cell in enumerate(notebook_data["cells"]):
                cell_id = cell.get("metadata", {}).get("cell_id", "")
                if cell_id in cell_id_set:
                    cell_type = cell.get("cell_type", "code")
                    ai_data = cell.get("ai_data", {})

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
                        "output": None,
                        "cellNumber": idx + 1,
                        "ai_prompt": ai_prompt,
                        "ai_response": ai_response,
                    })

    # Update playground activity
    await playground_service.update_activity(playground)

    # Build proxy headers with API key injection
    proxy_headers, is_own_key = await _build_proxy_headers(db, current_user.id, playground, llm_provider)

    # Pre-flight credit check (skip if using own key)
    if not is_own_key:
        credit_service = CreditService(db)
        estimated_cost = await credit_service.estimate_cost(llm_provider, "", 2000)
        has_credits = await credit_service.check_sufficient_credits(current_user.id, estimated_cost)
        if not has_credits:
            async def no_credits_stream():
                yield f"event: error\ndata: {json.dumps({'error': 'Insufficient credits. Please add credits or use your own API key.'})}\n\n"
            return StreamingResponse(no_credits_stream(), media_type="text/event-stream")

    # Convert images
    images_data = None
    if request.images:
        images_data = [
            {"data": img.data, "mime_type": img.mime_type, "url": img.url, "filename": img.filename}
            for img in request.images
            if img.data or img.url
        ]
        if not images_data:
            images_data = None

    # Fetch active system prompt for chat panel (fallback to hardcoded if DB fails)
    try:
        sp_service = SystemPromptService(db)
        chat_system_prompt = await sp_service.get_active("chat_panel")
    except Exception:
        chat_system_prompt = None

    # Capture variables for post-flight usage recording
    user_id = current_user.id

    # Stream SSE response from playground with post-flight usage recording
    async def stream_sse():
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "message": request.message,
                    "context": context_list,
                    "session_id": project_id,
                    "context_format": context_format,
                    "llm_provider": llm_provider,
                    "tool_mode": tool_mode,
                    "images": images_data,
                }
                if chat_system_prompt:
                    payload["system_prompt"] = chat_system_prompt
                async with client.stream(
                    "POST",
                    f"{playground.internal_url}/chat/stream",
                    headers=proxy_headers,
                    json=payload,
                    timeout=300,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield f"event: error\ndata: {json.dumps({'error': f'Playground error: {error_text.decode()}'})}\n\n"
                        return

                    async for line in response.aiter_lines():
                        if line:
                            # Intercept done events to record usage
                            if line.startswith("data:") and '"usage"' in line:
                                try:
                                    data_str = line[len("data:"):].strip()
                                    data = json.loads(data_str)
                                    usage = data.get("usage")
                                    if usage and data.get("success"):
                                        # Record usage in background
                                        async with AsyncSessionLocal() as usage_db:
                                            cs = CreditService(usage_db)
                                            await cs.record_usage_and_deduct(
                                                user_id=user_id,
                                                project_id=project_id,
                                                provider=usage.get("provider", llm_provider),
                                                model=usage.get("model", ""),
                                                request_type="chat",
                                                input_tokens=usage.get("input_tokens", 0),
                                                output_tokens=usage.get("output_tokens", 0),
                                                cached_tokens=usage.get("cached_tokens", 0),
                                                is_own_key=is_own_key,
                                            )
                                            credit = await cs.get_balance(user_id)
                                            await usage_db.commit()
                                        # Append balance to the done event
                                        data["credits_remaining_cents"] = credit.balance_cents if credit else 0
                                        line = f"data: {json.dumps(data)}"
                                except Exception:
                                    pass  # Don't break SSE stream on usage recording errors
                            yield f"{line}\n"
                        else:
                            yield "\n"

        except httpx.TimeoutException:
            yield f"event: error\ndata: {json.dumps({'error': 'Request timed out'})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/execute-tools/stream")
async def execute_tools_stream(
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
    Execute approved tool calls with SSE streaming.

    Proxies to playground's /chat/execute-tools/stream endpoint.

    SSE Events:
    - event: thinking - Status message
    - event: tool_executing - Tool being executed
    - event: tool_result - Tool execution result
    - event: pending_tools - More tools need approval
    - event: done - Final response
    - event: error - Error occurred
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
    playground = await playground_service.get_by_user_id(current_user.id)

    if not playground or playground.status.value != "running":
        async def error_stream():
            yield f"event: error\ndata: {json.dumps({'error': 'Playground is not running'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # Update playground activity
    await playground_service.update_activity(playground)

    # Build proxy headers with API key injection
    et_proxy_headers, is_own_key_et = await _build_proxy_headers(db, current_user.id, playground, llm_provider)

    # Capture variables for post-flight usage recording
    et_user_id = current_user.id

    # Stream SSE response from playground with post-flight usage recording
    async def stream_sse():
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{playground.internal_url}/chat/execute-tools/stream",
                    headers=et_proxy_headers,
                    json={
                        "session_id": project_id,
                        "approved_tools": [t.model_dump() for t in request.approved_tools],
                    },
                    timeout=300,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield f"event: error\ndata: {json.dumps({'error': f'Playground error: {error_text.decode()}'})}\n\n"
                        return

                    async for line in response.aiter_lines():
                        if line:
                            # Intercept done events to record usage
                            if line.startswith("data:") and '"usage"' in line:
                                try:
                                    data_str = line[len("data:"):].strip()
                                    data = json.loads(data_str)
                                    usage = data.get("usage")
                                    if usage and data.get("success"):
                                        async with AsyncSessionLocal() as usage_db:
                                            cs = CreditService(usage_db)
                                            await cs.record_usage_and_deduct(
                                                user_id=et_user_id,
                                                project_id=project_id,
                                                provider=usage.get("provider", llm_provider),
                                                model=usage.get("model", ""),
                                                request_type="chat",
                                                input_tokens=usage.get("input_tokens", 0),
                                                output_tokens=usage.get("output_tokens", 0),
                                                cached_tokens=usage.get("cached_tokens", 0),
                                                is_own_key=is_own_key_et,
                                            )
                                            credit = await cs.get_balance(et_user_id)
                                            await usage_db.commit()
                                        data["credits_remaining_cents"] = credit.balance_cents if credit else 0
                                        line = f"data: {json.dumps(data)}"
                                except Exception:
                                    pass
                            yield f"{line}\n"
                        else:
                            yield "\n"

        except httpx.TimeoutException:
            yield f"event: error\ndata: {json.dumps({'error': 'Request timed out'})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


@router.post("/ai-cell/run")
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
    playground = await playground_service.get_by_user_id(current_user.id)

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

    # Prepare images for forwarding (convert Pydantic models to dicts)
    images_data = None
    if request.images:
        images_data = [
            {
                "data": img.data,
                "mime_type": img.mime_type,
                "url": img.url,
                "filename": img.filename,
            }
            for img in request.images
            if img.data or img.url  # Only include images with actual content
        ]
        if not images_data:
            images_data = None

    # Build proxy headers with API key injection
    ai_proxy_headers, is_own_key_ai = await _build_proxy_headers(db, current_user.id, playground, llm_provider)

    # Pre-flight credit check (skip if using own key)
    if not is_own_key_ai:
        credit_service = CreditService(db)
        estimated_cost = await credit_service.estimate_cost(llm_provider, "", 1000)
        has_credits = await credit_service.check_sufficient_credits(current_user.id, estimated_cost)
        if not has_credits:
            async def no_credits_stream():
                yield f"event: error\ndata: {json.dumps({'error': 'Insufficient credits. Please add credits or use your own API key.'})}\n\n"
            return StreamingResponse(no_credits_stream(), media_type="text/event-stream")

    # Fetch active system prompt for AI cell (fallback to hardcoded if DB fails)
    try:
        sp_service_ai = SystemPromptService(db)
        ai_cell_system_prompt = await sp_service_ai.get_active("ai_cell")
    except Exception:
        ai_cell_system_prompt = None

    # Capture for post-flight
    ai_user_id = current_user.id

    # Stream SSE response from playground to frontend with post-flight usage recording
    async def stream_sse():
        try:
            async with httpx.AsyncClient() as client:
                ai_payload = {
                    "prompt": request.prompt,
                    "context": context_list,
                    "ai_cell_id": request.ai_cell_id,
                    "ai_cell_index": request.ai_cell_index,
                    "session_id": project_id,
                    "context_format": context_format,
                    "images": images_data,
                    "llm_provider": llm_provider,
                }
                if ai_cell_system_prompt:
                    ai_payload["system_prompt"] = ai_cell_system_prompt
                async with client.stream(
                    "POST",
                    f"{playground.internal_url}/ai-cell/run",
                    headers=ai_proxy_headers,
                    json=ai_payload,
                    timeout=120,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield f"event: error\ndata: {json.dumps({'error': f'Playground error: {error_text.decode()}'})}\n\n"
                        return

                    # Stream SSE events from playground to frontend
                    async for line in response.aiter_lines():
                        if line:
                            # Intercept done events to record usage
                            if line.startswith("data:") and '"usage"' in line:
                                try:
                                    data_str = line[len("data:"):].strip()
                                    data = json.loads(data_str)
                                    usage = data.get("usage")
                                    if usage and data.get("success"):
                                        async with AsyncSessionLocal() as usage_db:
                                            cs = CreditService(usage_db)
                                            await cs.record_usage_and_deduct(
                                                user_id=ai_user_id,
                                                project_id=project_id,
                                                provider=usage.get("provider", llm_provider),
                                                model=usage.get("model", ""),
                                                request_type="ai_cell",
                                                input_tokens=usage.get("input_tokens", 0),
                                                output_tokens=usage.get("output_tokens", 0),
                                                cached_tokens=usage.get("cached_tokens", 0),
                                                is_own_key=is_own_key_ai,
                                            )
                                            credit = await cs.get_balance(ai_user_id)
                                            await usage_db.commit()
                                        data["credits_remaining_cents"] = credit.balance_cents if credit else 0
                                        line = f"data: {json.dumps(data)}"
                                except Exception:
                                    pass
                            yield f"{line}\n"
                        else:
                            yield "\n"

        except httpx.TimeoutException:
            yield f"event: error\ndata: {json.dumps({'error': 'Request timed out'})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/ai-cell/cancel")
async def cancel_ai_cell(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running AI Cell execution by proxying to the playground."""
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_user_id(current_user.id)

    if not playground or playground.status.value != "running":
        return {"success": False, "message": "Playground is not running"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{playground.internal_url}/ai-cell/cancel",
                headers={"X-Internal-Secret": playground.internal_secret},
                json={"session_id": project_id},
                timeout=10,
            )
            return response.json()
    except Exception as e:
        return {"success": False, "message": f"Failed to cancel: {str(e)}"}
