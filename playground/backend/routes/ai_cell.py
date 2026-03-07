"""
AI Cell Routes - AI Cell execution with SSE streaming
"""

import queue
import asyncio
import contextvars
from typing import Dict, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

import backend.config as cfg
from backend.llm_clients import get_llm_client
from backend.llm_clients.base import CancelledException
from backend.middleware.security import verify_internal_secret, extract_key_overrides
from backend.models import (
    AICellRequest,
    AICellCancelRequest,
    AICellCancelResponse,
)
from backend.context_manager import ContextManager, ContextFormat
from backend.session_manager import set_current_session
from backend.utils.util_func import log, log_request
from backend.utils.sse_utils import format_sse_event, format_progress_event

router = APIRouter(prefix="/ai-cell", tags=["ai-cell"])

# Track active AI Cell clients for cancellation
# Key: session_id, Value: BaseLLMClient instance
_active_ai_cell_clients: Dict[str, Any] = {}


@router.post("/run")
async def run_ai_cell(
    request: AICellRequest,
    raw_request: Request,
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
            yield format_sse_event("error", {"error": "session_id is required for AI cell execution"})
        return StreamingResponse(error_generator(), media_type="text/event-stream")

    # Thread-safe queue for progress events (only used in streaming mode)
    progress_queue: queue.Queue = queue.Queue()

    def progress_callback(event_type: str, data: Any = None):
        """Callback that puts progress events into the queue."""
        progress_queue.put({"event": event_type, "data": data})

    # Capture key overrides from headers
    _ai_raw_request = raw_request

    async def event_generator():
        """Generate SSE events - unified for both streaming and non-streaming modes."""
        provider = request.llm_provider or cfg.LLM_PROVIDER
        key_override, model_override, base_url_override, auth_type = extract_key_overrides(_ai_raw_request, provider)
        client = get_llm_client(
            provider=provider,
            api_key_override=key_override,
            model_override=model_override,
            base_url_override=base_url_override,
            auth_type=auth_type,
        )

        # Override system prompt if provided by master (admin DB)
        if request.system_prompt:
            client.AI_CELL_SYSTEM_PROMPT = request.system_prompt

        _active_ai_cell_clients[session_id] = client

        streaming_enabled = cfg.AI_CELL_STREAMING_ENABLED
        log(f"AI Cell: session={session_id}, provider={provider}, streaming={streaming_enabled}")

        try:
            # Build context using ContextManager - returns FormattedContext with separate parts
            format_map = {"xml": ContextFormat.XML, "json": ContextFormat.JSON, "plain": ContextFormat.PLAIN}
            ctx_format = format_map.get(request.context_format, ContextFormat.XML)
            ai_cell_index = request.ai_cell_index if request.ai_cell_index is not None else -1

            context_manager = ContextManager()
            formatted_ctx = context_manager.build_ai_cell_context(
                cells=request.context or [],
                ai_cell_index=ai_cell_index,
                user_prompt=request.prompt,
                format=ctx_format
            )
            notebook_context = formatted_ctx.notebook_context
            user_prompt = formatted_ctx.user_prompt

            # Log the full context being sent to LLM (detailed log_ai_cell is called in base.py)
            total_cells = len(request.context or []) + 1
            log_request(
                source="AI_CELL",
                provider=provider,
                context_format=ctx_format.value,
                notebook_context=notebook_context,
                user_prompt=user_prompt,
                context_cells=len(request.context or []),
                position_info=f"Cell #{ai_cell_index + 1} of {total_cells}",
            )

            # Convert images to LLM format
            llm_images = None
            if request.images:
                llm_images = [
                    {"data": img.data, "mime_type": img.mime_type or "image/png"}
                    for img in request.images if img.data
                ] or None

            # LAZY KERNEL: Only set session ID - kernel created on-demand by tools
            # This allows parallel LLM requests (queries without code execution run immediately)
            set_current_session(session_id)
            log(f"Session ID set: {session_id} (kernel will be created lazily if needed)")

            # Pass allowed_tools from mode if provided
            allowed_tools = request.allowed_tools

            if streaming_enabled:
                # === STREAMING MODE: Send real-time progress events ===
                client.set_progress_callback(progress_callback)

                # Send initial "thinking" event
                yield format_sse_event("thinking", {"message": "Starting AI analysis..."})

                # Run LLM in thread pool (allows progress events to be sent)
                ctx = contextvars.copy_context()
                def run_llm():
                    return ctx.run(client.ai_cell_execute, notebook_context, user_prompt, images=llm_images, allowed_tools=allowed_tools)

                loop = asyncio.get_event_loop()
                llm_future = loop.run_in_executor(None, run_llm)

                # Poll for progress events while LLM is running
                while not llm_future.done():
                    try:
                        try:
                            event = progress_queue.get_nowait()
                            sse_event = format_progress_event(event["event"], event["data"])
                            if sse_event:
                                log(f"SSE sending {event['event']}")
                                yield sse_event
                        except queue.Empty:
                            pass

                        await asyncio.sleep(0.05)
                    except Exception as e:
                        log(f"Error in progress polling: {e}")

                # Get final result
                result = await llm_future

                # Drain any remaining events from the queue
                while True:
                    try:
                        event = progress_queue.get_nowait()
                        sse_event = format_progress_event(event["event"], event["data"])
                        if sse_event:
                            log(f"SSE sending {event['event']} (drain)")
                            yield sse_event
                    except queue.Empty:
                        break

            else:
                # === NON-STREAMING MODE: Just run and return final result ===
                log("AI Cell running in non-streaming mode")
                result = await asyncio.to_thread(client.ai_cell_execute, notebook_context, user_prompt, images=llm_images, allowed_tools=allowed_tools)

            # Send final 'done' event (both modes)
            response_text = result.get("response", "")
            llm_steps = result.get("steps", [])
            was_cancelled = result.get("cancelled", False)
            thinking_content = result.get("thinking", "")
            usage_data = result.get("usage")

            final_data = {
                "success": not was_cancelled,
                "response": response_text,
                "model": provider,
                "steps": llm_steps,
                "cancelled": was_cancelled,
                "thinking": thinking_content if thinking_content else None,
            }
            if usage_data:
                final_data["usage"] = usage_data
            log(f"SSE sending done event (thinking: {len(thinking_content)} chars, usage: {usage_data})")
            yield format_sse_event("done", final_data)

        except CancelledException:
            yield format_sse_event("done", {
                "success": False,
                "response": "[Cancelled by user]",
                "cancelled": True,
                "steps": []
            })
        except Exception as e:
            import traceback
            log(f"AI Cell error: {e}\n{traceback.format_exc()}")
            error_msg = str(e)
            if "API" in error_msg or "key" in error_msg.lower():
                error_msg = "LLM API error. Please check your API key configuration."
            elif "timeout" in error_msg.lower():
                error_msg = "Request timed out. Please try again."
            yield format_sse_event("error", {"error": error_msg})
        finally:
            # Clean up - close client connections and remove from active dict
            client_ref = _active_ai_cell_clients.pop(session_id, None)
            if client_ref is not None:
                try:
                    client_ref.close()
                except Exception:
                    pass
                log(f"AI Cell: Unregistered client for session {session_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/cancel", response_model=AICellCancelResponse)
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
            log(f"Cancel request: No active AI Cell for session {session_id}")
            return AICellCancelResponse(
                success=False,
                message="No active AI Cell execution found for this session",
            )

        client = _active_ai_cell_clients[session_id]
        client.cancel()

        log(f"Cancel request: Sent cancellation signal for session {session_id}")

        return AICellCancelResponse(
            success=True,
            message="Cancellation signal sent. The AI Cell will stop at the next check point.",
        )

    except Exception as e:
        log(f"Cancel request error: {e}")
        return AICellCancelResponse(
            success=False,
            message=f"Failed to cancel: {str(e)}",
        )
