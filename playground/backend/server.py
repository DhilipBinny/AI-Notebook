"""
AI Notebook Playground - Headless FastAPI Server
Container-based kernel execution and LLM chat API.
No frontend - pure API for Master backend to proxy.
"""

# =============================================================================
# Imports
# =============================================================================

import sys
import os
import json
import asyncio
import queue
import logging
import contextvars
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import backend.config as cfg
from backend.llm_clients import LLMClient
from backend.llm_clients.base import CancelledException
from backend.utils.util_func import (
    log_debug_message,
    log_chat_header,
    log_user_message,
    log_llm_response_box,
)
from backend.notebook_state import get_notebook_updates
from backend.context_manager import ContextManager, ContextFormat
from backend.session_manager import (
    get_session_manager,
    set_current_session,
    clear_current_session,
)
from backend.routes import kernel_router, session_router


# =============================================================================
# App Initialization & Constants
# =============================================================================

app = FastAPI(
    title="AI Notebook Playground",
    version="0.1.0",
    description="Headless notebook execution container",
)

# Track active AI Cell clients for cancellation
# Key: session_id, Value: LLMClient instance
_active_ai_cell_clients: Dict[str, Any] = {}

# Get internal secret from environment (set by Master when spawning container)
INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "")

# =============================================================================
# Pydantic Models
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


# --- Chat Models ---

class ChatRequest(BaseModel):
    """Request for chat endpoint."""
    message: str
    context: List[CellContext] = []
    history: List[ChatMessage] = []
    session_id: Optional[str] = None
    context_format: str = "xml"  # "plain" or "xml" - XML recommended for Claude
    images: Optional[List[ImageInput]] = None
    llm_provider: Optional[str] = None  # Override LLM provider
    tool_mode: Optional[str] = None  # "auto", "manual", "ai_decide"


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


# --- AI Cell Models ---

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


# --- LLM Complete Models ---

class LLMCompleteRequest(BaseModel):
    """Request for simple LLM completion (no tools)."""
    prompt: str
    max_tokens: int = 1000
    llm_provider: Optional[str] = None


# =============================================================================
# Security Dependencies
# =============================================================================

async def verify_internal_secret(x_internal_secret: str = Header(None)):
    """Verify requests come from Master API."""
    if not INTERNAL_SECRET:
        # No secret configured - development mode
        return True

    if x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Invalid internal secret")

    return True


# =============================================================================
# Helper Functions
# =============================================================================

def _build_ai_cell_context(request: AICellRequest, provider: str) -> tuple:
    """
    Build context for AI Cell execution.

    Args:
        request: The AI cell request
        provider: The resolved LLM provider (from request or default)

    Returns:
        Tuple of (user_message, llm_images)
    """

    # AI Cell user message template - contains dynamic context (position, notebook cells, question)
    # The system prompt with tool instructions is in BaseLLMClient.AI_CELL_SYSTEM_PROMPT
    AI_CELL_USER_MESSAGE = """POSITION: {position_info}

    NOTEBOOK CONTEXT:
    {notebook_context}

    USER QUESTION:
    {user_prompt}
    """

    # Build positional context with cells above and below
    ai_cell_index = request.ai_cell_index if request.ai_cell_index is not None else -1
    total_cells = len(request.context) + 1  # +1 for the AI cell itself

    # Build position info
    if ai_cell_index >= 0:
        position_info = f"You are in Cell #{ai_cell_index + 1} of {total_cells} total cells."
        if ai_cell_index > 0:
            position_info += f" There are {ai_cell_index} cell(s) ABOVE you."
        if ai_cell_index < total_cells - 1:
            position_info += f" There are {total_cells - ai_cell_index - 1} cell(s) BELOW you."
    else:
        position_info = "Position unknown."

    # Build notebook context with positional sections using ContextManager
    context_manager = ContextManager()
    ctx_format = ContextFormat.XML if request.context_format == "xml" else ContextFormat.PLAIN

    # Convert request context to cell dicts (including AI cell data)
    cells_data = []
    for cell in request.context or []:
        cell_dict = {
            "id": cell.id,
            "type": cell.type,
            "content": cell.content,
            "output": cell.output,
            "cellNumber": cell.cellNumber,
        }
        # Include AI cell specific fields if present
        if cell.ai_prompt:
            cell_dict["ai_prompt"] = cell.ai_prompt
        if cell.ai_response:
            cell_dict["ai_response"] = cell.ai_response
        cells_data.append(cell_dict)

    notebook_context = context_manager.process_positional_context(
        cells_data,
        ai_cell_index,
        format=ctx_format,
    )

    # Build the user message with context (system prompt is in LLM client)
    user_message = AI_CELL_USER_MESSAGE.format(
        position_info=position_info,
        notebook_context=notebook_context,
        user_prompt=request.prompt,
    )

    # Log the user message being sent to LLM for AI Cell
    print(f"\n{'='*80}")
    print(f"AI CELL USER MESSAGE TO LLM [{provider.upper()}] (format: {request.context_format})")
    print(f"{'='*80}")
    print(user_message)
    print(f"{'='*80}")
    print(f"Stats: {len(user_message)} chars total, position: {ai_cell_index + 1}/{total_cells}")
    print(f"{'='*80}\n")

    # Convert images to LLM format if provided
    llm_images = None
    if request.images:
        llm_images = []
        for img in request.images:
            if img.data:
                llm_images.append({
                    "data": img.data,
                    "mime_type": img.mime_type or "image/png",
                })
            elif img.url:
                llm_images.append({"url": img.url})

        if llm_images:
            log_debug_message(f"AI Cell: {len(llm_images)} image(s) attached")

    return user_message, llm_images


# =============================================================================
# Include Sub-Routers
# =============================================================================

app.include_router(kernel_router)
app.include_router(session_router)


# =============================================================================
# Health & Status Routes
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint (no auth required)."""
    return {
        "status": "ok",
        "service": "playground",
        "provider": cfg.LLM_PROVIDER,
    }


@app.get("/status")
async def status(authorized: bool = Depends(verify_internal_secret)):
    """Detailed status (auth required)."""
    session_manager = get_session_manager()
    return {
        "status": "ok",
        "llm_provider": cfg.LLM_PROVIDER,
        "tool_mode": cfg.TOOL_EXECUTION_MODE,
        "active_sessions": session_manager.session_count,
    }


# =============================================================================
# LLM Complete Route (Simple completion without tools)
# =============================================================================

@app.post("/llm/complete")
async def llm_complete(
    request: LLMCompleteRequest,
    authorized: bool = Depends(verify_internal_secret),
):
    """
    Simple text completion without tools.
    Used for summarization and other simple LLM tasks.
    """
    try:
        provider = request.llm_provider or cfg.LLM_PROVIDER
        log_debug_message(f"LLM complete request (provider={provider}): {request.prompt[:200]}...")

        client = LLMClient(provider=provider)
        response_text = client.chat_completion(request.prompt, request.max_tokens)

        log_debug_message(f"LLM complete response: {response_text[:200]}...")

        return {
            "success": True,
            "response": response_text,
        }

    except Exception as e:
        log_debug_message(f"LLM complete error: {e}")
        return {
            "success": False,
            "response": "",
            "error": str(e),
        }


# =============================================================================
# AI Cell Routes
# =============================================================================

@app.post("/ai-cell/run")
async def run_ai_cell(
    request: AICellRequest,
    authorized: bool = Depends(verify_internal_secret),
):
    """
    Run an AI Cell with unified SSE response.

    Always returns Server-Sent Events (SSE) stream.
    When AI_CELL_STREAMING_ENABLED=true: sends real-time progress events
    When AI_CELL_STREAMING_ENABLED=false: only sends final 'done' event

    SSE Events:
    - event: thinking - LLM is processing
    - event: llm_thinking - LLM reasoning/thinking content
    - event: tool_call - Tool is being called with args
    - event: tool_result - Tool execution result
    - event: done - Final response with all steps
    - event: error - Error occurred
    """
    session_id = request.session_id

    # Validate session_id - required for AI cell
    if not session_id:
        async def error_generator():
            yield f"event: error\ndata: {json.dumps({'error': 'session_id is required for AI cell execution'})}\n\n"
        return StreamingResponse(error_generator(), media_type="text/event-stream")

    # Thread-safe queue for progress events (only used in streaming mode)
    progress_queue: queue.Queue = queue.Queue()

    def progress_callback(event_type: str, data: Any = None):
        """Callback that puts progress events into the queue."""
        progress_queue.put({"event": event_type, "data": data})

    async def event_generator():
        """Generate SSE events - unified for both streaming and non-streaming modes."""
        provider = request.llm_provider or cfg.LLM_PROVIDER
        client = LLMClient(provider=provider)
        _active_ai_cell_clients[session_id] = client

        streaming_enabled = cfg.AI_CELL_STREAMING_ENABLED
        log_debug_message(f"AI Cell: session={session_id}, provider={provider}, streaming={streaming_enabled}")

        try:
            # Build context
            user_message, llm_images = _build_ai_cell_context(request, provider)

            # Set up session for AI cell tools to access main kernel
            # The session ensures kernel is ready and set_current_session allows LLM tools to access it
            try:
                session = get_session_manager().get_or_create_session(session_id)
                set_current_session(session_id)
                log_debug_message(f"Session ready: {session_id}, kernel_alive: {session.kernel.is_alive()}")
            except RuntimeError as e:
                log_debug_message(f"AI Cell session error: {e}")
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                return

            if streaming_enabled:
                # === STREAMING MODE: Send real-time progress events ===
                client.set_progress_callback(progress_callback)

                # Send initial "thinking" event
                yield f"event: thinking\ndata: {json.dumps({'message': 'Starting AI analysis...'})}\n\n"

                # Run LLM in thread pool (allows progress events to be sent)
                # Copy context to thread so session is available for LLM tools (sandbox, etc.)
                ctx = contextvars.copy_context()
                def run_llm():
                    return ctx.run(client.ai_cell_with_tools, user_message, images=llm_images)

                loop = asyncio.get_event_loop()
                llm_future = loop.run_in_executor(None, run_llm)

                # Poll for progress events while LLM is running
                while not llm_future.done():
                    try:
                        try:
                            event = progress_queue.get_nowait()
                            event_type = event["event"]
                            event_data = event["data"] or {}

                            if event_type == "thinking":
                                thinking_content = event_data.get("content", "")
                                thinking_iteration = event_data.get("iteration", 1)
                                if thinking_content:
                                    log_debug_message(f"SSE sending llm_thinking: {len(thinking_content)} chars, iteration {thinking_iteration}")
                                    yield f"event: llm_thinking\ndata: {json.dumps({'content': thinking_content, 'iteration': thinking_iteration})}\n\n"
                            elif event_type == "tool_call":
                                yield f"event: tool_call\ndata: {json.dumps(event_data)}\n\n"
                            elif event_type == "tool_result":
                                yield f"event: tool_result\ndata: {json.dumps(event_data)}\n\n"
                            elif event_type == "iteration_start":
                                iteration_num = event_data.get("iteration", 1)
                                yield f"event: thinking\ndata: {json.dumps({'message': f'Iteration {iteration_num}...'})}\n\n"
                            elif event_type == "iteration_end":
                                if event_data.get("final"):
                                    yield f"event: thinking\ndata: {json.dumps({'message': 'Finalizing response...'})}\n\n"
                        except queue.Empty:
                            pass

                        await asyncio.sleep(0.05)
                    except Exception as e:
                        log_debug_message(f"Error in progress polling: {e}")

                # Get final result
                result = await llm_future

                # Drain any remaining events from the queue
                while True:
                    try:
                        event = progress_queue.get_nowait()
                        event_type = event["event"]
                        event_data = event["data"] or {}

                        if event_type == "thinking":
                            thinking_content = event_data.get("content", "")
                            thinking_iteration = event_data.get("iteration", 1)
                            if thinking_content:
                                log_debug_message(f"SSE sending llm_thinking (drain): {len(thinking_content)} chars")
                                yield f"event: llm_thinking\ndata: {json.dumps({'content': thinking_content, 'iteration': thinking_iteration})}\n\n"
                        elif event_type == "tool_call":
                            yield f"event: tool_call\ndata: {json.dumps(event_data)}\n\n"
                        elif event_type == "tool_result":
                            yield f"event: tool_result\ndata: {json.dumps(event_data)}\n\n"
                    except queue.Empty:
                        break

            else:
                # === NON-STREAMING MODE: Just run and return final result ===
                log_debug_message("AI Cell running in non-streaming mode")
                result = await asyncio.to_thread(client.ai_cell_with_tools, user_message, images=llm_images)

            # Send final 'done' event (both modes)
            response_text = result.get("response", "")
            llm_steps = result.get("steps", [])
            was_cancelled = result.get("cancelled", False)
            thinking_content = result.get("thinking", "")

            final_data = {
                "success": not was_cancelled,
                "response": response_text,
                "model": provider,  # Use actual provider used, not config default
                "steps": llm_steps,
                "cancelled": was_cancelled,
                "thinking": thinking_content if thinking_content else None,
            }
            log_debug_message(f"SSE sending done event (thinking: {len(thinking_content)} chars)")
            yield f"event: done\ndata: {json.dumps(final_data)}\n\n"

        except CancelledException:
            yield f"event: done\ndata: {json.dumps({'success': False, 'response': '[Cancelled by user]', 'cancelled': True, 'steps': []})}\n\n"
        except Exception as e:
            import traceback
            log_debug_message(f"AI Cell error: {e}\n{traceback.format_exc()}")
            error_msg = str(e)
            if "API" in error_msg or "key" in error_msg.lower():
                error_msg = "LLM API error. Please check your API key configuration."
            elif "timeout" in error_msg.lower():
                error_msg = "Request timed out. Please try again."
            yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
        finally:
            # Clean up
            if session_id in _active_ai_cell_clients:
                del _active_ai_cell_clients[session_id]
                log_debug_message(f"AI Cell: Unregistered client for session {session_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.post("/ai-cell/cancel", response_model=AICellCancelResponse)
async def cancel_ai_cell(
    request: AICellCancelRequest,
    authorized: bool = Depends(verify_internal_secret),
):
    """
    Cancel a running AI Cell execution.
    This will stop the current tool execution loop at the next cancellation check point.
    """
    try:
        session_id = request.session_id

        if session_id not in _active_ai_cell_clients:
            log_debug_message(f"Cancel request: No active AI Cell for session {session_id}")
            return AICellCancelResponse(
                success=False,
                message="No active AI Cell execution found for this session",
            )

        client = _active_ai_cell_clients[session_id]
        client.cancel()

        log_debug_message(f"Cancel request: Sent cancellation signal for session {session_id}")

        return AICellCancelResponse(
            success=True,
            message="Cancellation signal sent. The AI Cell will stop at the next check point.",
        )

    except Exception as e:
        log_debug_message(f"Cancel request error: {e}")
        return AICellCancelResponse(
            success=False,
            message=f"Failed to cancel: {str(e)}",
        )


# =============================================================================
# Chat Routes
# =============================================================================

@app.post("/chat", response_model=ChatResponse)
async def chat_with_llm(
    request: ChatRequest,
    authorized: bool = Depends(verify_internal_secret),
):
    """Chat with the LLM assistant."""
    try:
        # Use provider and tool_mode from request body if specified
        provider = request.llm_provider or cfg.LLM_PROVIDER
        tool_mode = request.tool_mode or cfg.TOOL_EXECUTION_MODE

        # Pretty print chat request header
        log_chat_header(provider.upper(), tool_mode, len(request.context) if request.context else 0)
        log_user_message(request.message)

        # Get or create session - ensures session exists for tool execution
        # The session ensures kernel is ready and set_current_session allows LLM tools to access it
        if request.session_id:
            try:
                session = get_session_manager().get_or_create_session(request.session_id)
                set_current_session(request.session_id)
                log_debug_message(f"Session ready: {request.session_id}, kernel_alive: {session.kernel.is_alive()}")
            except RuntimeError as e:
                log_debug_message(f"Chat session error: {e}")
                return ChatResponse(success=False, response="", error=str(e))

        # Build context string using ContextManager (with fallback to simple format)
        context_str = ""
        if request.context:
            try:
                context_manager = ContextManager()
                cells_data = [
                    {
                        "id": cell.id,
                        "type": cell.type,
                        "content": cell.content,
                        "output": cell.output,
                        "cellNumber": cell.cellNumber,
                    }
                    for cell in request.context
                ]
                ctx_format = ContextFormat.XML if request.context_format == "xml" else ContextFormat.PLAIN
                context_str = context_manager.process_context(cells_data, format=ctx_format)
            except Exception as e:
                # Fallback to simple format if context manager fails
                log_debug_message(f"Context manager error, using simple format: {e}")
                context_str = "\n\n--- NOTEBOOK CONTEXT ---\n"
                for cell in request.context:
                    cell_num = cell.cellNumber if cell.cellNumber else "?"
                    context_str += f"\n[Cell {cell_num}] ({cell.type.upper()}):\n```\n{cell.content}\n```"
                    if cell.output:
                        context_str += f"\nOutput:\n```\n{cell.output}\n```"
                context_str += "\n--- END CONTEXT ---\n"

        # Initialize LLM client with provider from request
        try:
            client = LLMClient(provider=provider)
        except Exception as e:
            return ChatResponse(success=False, response="", error=str(e))

        # Convert history to LLM format
        llm_history = []
        for msg in request.history:
            llm_history.append({
                "role": "user" if msg.role == "user" else "model",
                "parts": [msg.content],
            })
        client.set_history(llm_history)

        # Send message
        full_message = request.message
        if context_str:
            full_message = f"=== NOTEBOOK CONTEXT ===\n\n{context_str}\n\n[MESSAGE]\n{request.message}"

        # Log the FULL message being sent to LLM
        print(f"\n{'='*80}")
        print(f"FULL MESSAGE TO LLM [{provider.upper()}] (format: {request.context_format})")
        print(f"{'='*80}")
        print(full_message)
        print(f"{'='*80}")
        print(f"Stats: {len(full_message)} chars total, {len(context_str)} context, {len(request.message)} user message")
        print(f"{'='*80}\n")

        log_debug_message(f"Sending to {client.provider_name}...")

        # Convert images to dict format if present
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
                if img.data or img.url
            ]
            if images_data:
                log_debug_message(f"Chat: {len(images_data)} image(s) attached")

        llm_response = client.send_message(full_message, user_message=request.message, images=images_data)

        # Process response
        pending_tools = []
        llm_steps = []
        session_for_steps = None

        if request.session_id:
            session_for_steps = get_session_manager().get_session(request.session_id)
            if session_for_steps:
                session_for_steps.clear_llm_steps()

        if isinstance(llm_response, dict) and "pending_tool_calls" in llm_response:
            tools_list = [t.get("name") for t in llm_response.get("pending_tool_calls", [])]
            log_debug_message(f"TOOLS CALLED: {', '.join(tools_list)}")
            response_text = llm_response.get("response_text", "")
            all_pending_tools = llm_response.get("pending_tool_calls", [])

            # Record tool call steps
            for tool in all_pending_tools:
                args_str = json.dumps(tool.get("arguments", {}), indent=2)
                if session_for_steps:
                    session_for_steps.add_llm_step("tool_call", args_str, tool.get("name"))

            # Handle based on tool mode
            if tool_mode == "auto":
                # Auto-execute all tools
                tool_calls = [
                    {"id": t["id"], "name": t["name"], "arguments": t["arguments"]}
                    for t in all_pending_tools
                ]
                exec_response = client.execute_approved_tools(tool_calls)

                if isinstance(exec_response, dict):
                    response_text = exec_response.get("response_text", "")
                else:
                    response_text = exec_response

                llm_steps = session_for_steps.get_llm_steps() if session_for_steps else []

            elif tool_mode == "ai_decide":
                # AI decides which tools need approval
                from backend.agent_roles import validate_tool_calls
                validation_result = validate_tool_calls(all_pending_tools, provider=provider)
                safe_tools = validation_result["safe_tools"]
                unsafe_tools = validation_result["unsafe_tools"]

                if safe_tools:
                    safe_tool_calls = [
                        {"id": t["id"], "name": t["name"], "arguments": t["arguments"]}
                        for t in safe_tools
                    ]
                    exec_response = client.execute_approved_tools(safe_tool_calls)

                    if isinstance(exec_response, dict) and "pending_tool_calls" in exec_response:
                        additional_tools = exec_response.get("pending_tool_calls", [])
                        response_text = exec_response.get("response_text", "")
                        for t in additional_tools:
                            unsafe_tools.append({
                                "id": t["id"],
                                "name": t["name"],
                                "arguments": t["arguments"],
                                "validation": {"reason": "Additional tool requested"},
                            })

                    if isinstance(exec_response, dict):
                        response_text = exec_response.get("response_text", "")
                    else:
                        response_text = exec_response

                if unsafe_tools:
                    pending_tools = [
                        {
                            "id": t["id"],
                            "name": t["name"],
                            "arguments": t["arguments"],
                            "validation_reason": t.get("validation", {}).get("reason", "Requires approval"),
                        }
                        for t in unsafe_tools
                    ]

                    # Store client state
                    if request.session_id:
                        session = get_session_manager().get_session(request.session_id)
                        if session:
                            session.pending_client = client
                else:
                    llm_steps = session_for_steps.get_llm_steps() if session_for_steps else []

            else:
                # Manual mode - all tools need approval
                log_debug_message(f"Manual mode - returning {len(all_pending_tools)} tools for approval")
                pending_tools = all_pending_tools
                if request.session_id:
                    session = get_session_manager().get_session(request.session_id)
                    if session:
                        session.pending_client = client
                        log_debug_message(f"Stored pending_client in session {request.session_id}")
                    else:
                        log_debug_message(f"WARNING: Session {request.session_id} not found!")
                else:
                    log_debug_message("WARNING: No session_id provided - cannot store pending_client!")
        else:
            response_text = llm_response if isinstance(llm_response, str) else str(llm_response)
            llm_steps = session_for_steps.get_llm_steps() if session_for_steps else []
            log_debug_message("NO TOOLS - Direct response")

        # Get notebook updates
        updates = get_notebook_updates(session_id=request.session_id)

        # Get remaining steps
        if session_for_steps and len(llm_steps) == 0:
            llm_steps = session_for_steps.get_llm_steps()

        clear_current_session()

        # Pretty print final response
        log_llm_response_box(response_text)

        return ChatResponse(
            success=True,
            response=response_text,
            updates=updates,
            pending_tool_calls=pending_tools,
            steps=[LLMStep(**step) for step in llm_steps],
        )

    except Exception as e:
        clear_current_session()
        return ChatResponse(success=False, response="", error=str(e))


@app.post("/chat/execute-tools", response_model=ChatResponse)
async def execute_approved_tools(
    request: ExecuteToolsRequest,
    authorized: bool = Depends(verify_internal_secret),
):
    """Execute approved tool calls."""
    try:
        log_debug_message(f"Execute-tools request: session_id={request.session_id}, tools={[t.name for t in request.approved_tools]}")

        session = get_session_manager().get_session(request.session_id)

        if not session:
            log_debug_message(f"Session not found: {request.session_id}")
            return ChatResponse(success=False, response="", error="Session not found")

        log_debug_message(f"Session ready: {request.session_id}, kernel_alive: {session.kernel.is_alive()}")

        client = session.pending_client
        if not client:
            log_debug_message("No pending client found!")
            return ChatResponse(success=False, response="", error="No pending tool calls")

        set_current_session(request.session_id)

        approved_tools_list = [tool.dict() for tool in request.approved_tools]
        log_debug_message(f"Executing approved tools: {approved_tools_list}")
        exec_result = client.execute_approved_tools(approved_tools_list)
        log_debug_message(f"Execution result: {exec_result}")

        if isinstance(exec_result, dict) and "pending_tool_calls" in exec_result:
            response_text = exec_result.get("response_text", "")
            pending_tools = exec_result.get("pending_tool_calls", [])
            tool_results = exec_result.get("tool_results", [])

            for tr in tool_results:
                result_str = str(tr.get("result", ""))[:500]
                session.add_llm_step("tool_result", result_str, tr.get("name"))

            for tool in pending_tools:
                args_str = json.dumps(tool.get("arguments", {}), indent=2)
                session.add_llm_step("tool_call", args_str, tool.get("name"))

            session.pending_client = client
            updates = get_notebook_updates(session_id=request.session_id)
            llm_steps = session.llm_steps.copy()
            clear_current_session()

            return ChatResponse(
                success=True,
                response=response_text,
                updates=updates,
                pending_tool_calls=[
                    {"id": t["id"], "name": t["name"], "arguments": t["arguments"]}
                    for t in pending_tools
                ],
                steps=[LLMStep(**step) for step in llm_steps],
            )

        if isinstance(exec_result, dict):
            log_debug_message(f"exec_result is dict with keys: {exec_result.keys()}")
            response_text = exec_result.get("response_text", "")
            tool_results = exec_result.get("tool_results", [])
            log_debug_message(f"Tool results: {len(tool_results)} results")
            for tr in tool_results:
                result_str = str(tr.get("result", ""))[:500]
                log_debug_message(f"Tool result for {tr.get('name')}: {result_str[:200]}...")
                session.add_llm_step("tool_result", result_str, tr.get("name"))
        else:
            log_debug_message(f"exec_result is string: {str(exec_result)[:200]}")
            response_text = exec_result

        log_debug_message(f"Final response_text: {response_text[:200] if response_text else 'EMPTY'}...")

        if response_text and response_text != "Tool executed successfully.":
            session.add_llm_step(
                "text",
                response_text[:200] + "..." if len(response_text) > 200 else response_text,
            )

        llm_steps = session.get_llm_steps()
        updates = get_notebook_updates(session_id=request.session_id)

        log_debug_message(f"Returning: response_text={len(response_text) if response_text else 0} chars, steps={len(llm_steps)}, updates={len(updates)}")

        session.pending_client = None
        clear_current_session()

        return ChatResponse(
            success=True,
            response=response_text,
            updates=updates,
            steps=[LLMStep(**step) for step in llm_steps],
        )

    except Exception as e:
        clear_current_session()
        return ChatResponse(success=False, response="", error=str(e))


# =============================================================================
# Logging Configuration
# =============================================================================

class HealthCheckFilter(logging.Filter):
    """Filter out health check request logs to reduce noise."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "GET /health" in message:
            return False
        return True


# Apply filter at module load time (works with uvicorn)
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    PORT = int(os.getenv("PLAYGROUND_PORT", "8888"))
    HOST = os.getenv("HOST", "0.0.0.0")

    print("\n" + "=" * 50)
    print("  AI Notebook Playground (Headless)")
    print("=" * 50)
    print(f"  Port: {PORT}")
    print(f"  LLM Provider: {cfg.LLM_PROVIDER}")
    print("=" * 50 + "\n")

    uvicorn.run(
        "backend.server:app",
        host=HOST,
        port=PORT,
        log_level="info",
    )
