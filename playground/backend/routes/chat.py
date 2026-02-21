"""
Chat Routes - Chat with LLM assistant with tool calling support

Endpoints:
- POST /chat - JSON request/response (original, backward compatible)
- POST /chat/stream - SSE streaming with real-time progress events
- POST /chat/execute-tools - JSON tool execution (original)
- POST /chat/execute-tools/stream - SSE streaming tool execution
"""

import json
import queue
import asyncio
import contextvars
from typing import Dict, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

import backend.config as cfg
from backend.llm_clients import get_llm_client
from backend.middleware.security import verify_internal_secret, extract_key_overrides
from backend.models import ChatRequest, ExecuteToolsRequest
from backend.context_manager import ContextManager, ContextFormat
from backend.session_manager import (
    get_session_manager,
    set_current_session,
    clear_current_session,
)
from backend.utils.util_func import (
    log,
    log_user,
    log_resp_box,
    log_request,
)
from backend.utils.sse_utils import format_sse_event, format_progress_event

router = APIRouter(prefix="/chat", tags=["chat"])


# =============================================================================
# DEPRECATED: JSON ENDPOINTS - Replaced by SSE streaming endpoints below
# =============================================================================
# These endpoints have been replaced by /chat/stream and /chat/execute-tools/stream
# which provide real-time progress updates via Server-Sent Events.
# Kept commented for reference.

# @router.post("", response_model=ChatResponse)
# async def chat_with_llm(
#     request: ChatRequest,
#     authorized: bool = Depends(verify_internal_secret),
# ):
#     """Chat with the LLM assistant."""
#     try:
#         # Use provider and tool_mode from request body if specified
#         provider = request.llm_provider or cfg.LLM_PROVIDER
#         tool_mode = request.tool_mode or cfg.TOOL_EXECUTION_MODE
#
#         # Pretty print chat request header
#         log_chat(provider.upper(), tool_mode, len(request.context) if request.context else 0)
#         log_user(request.message)
#
#         # Get or create session - ensures session exists for tool execution
#         if request.session_id:
#             try:
#                 session = get_session_manager().get_or_create_session(request.session_id)
#                 set_current_session(request.session_id)
#                 log(f"Session ready: {request.session_id}, kernel_alive: {session.kernel.is_alive()}")
#             except RuntimeError as e:
#                 log(f"Chat session error: {e}")
#                 return ChatResponse(success=False, response="", error=str(e))
#
#         # Build context using ContextManager - returns FormattedContext with separate parts
#         format_map = {
#             "xml": ContextFormat.XML,
#             "json": ContextFormat.JSON,
#             "plain": ContextFormat.PLAIN
#             }
#         ctx_format = format_map.get(request.context_format, ContextFormat.XML)
#         context_manager = ContextManager()
#
#         try:
#             formatted_ctx = context_manager.build_chat_context(
#                 cells=request.context or [],
#                 user_prompt=request.message,
#                 format=ctx_format
#             )
#             notebook_context = formatted_ctx.notebook_context
#             user_prompt = formatted_ctx.user_prompt
#         except Exception as e:
#             # Context manager failed - don't proceed without context
#             log(f"Context manager error: {e}")
#             return ChatResponse(success=False, response="", error=f"Failed to build context: {e}")
#
#         # Initialize LLM client with provider and tool mode from request
#         # auto -> client handles tools automatically (loops until done)
#         # ai_decide/manual -> client returns pending tools for route to handle
#         auto_func = (tool_mode == "auto")
#         try:
#             client = get_llm_client(provider=provider, auto_function_calling=auto_func)
#         except Exception as e:
#             return ChatResponse(success=False, response="", error=str(e))
#
#         # Convert history to neutral format - each LLM client handles role conversion
#         # Uses "assistant" (standard) which Gemini converts to "model" in set_history
#         llm_history = []
#         for msg in request.history:
#             llm_history.append({
#                 "role": msg.role,  # "user" or "assistant" - client handles conversion
#                 "content": msg.content,
#                 "parts": [msg.content],  # For backward compatibility with Gemini format
#             })
#         client.set_history(llm_history)
#
#         # Log the full context being sent to LLM
#         log_request(
#             source="CHAT",
#             provider=provider,
#             context_format=ctx_format.value,
#             notebook_context=notebook_context,
#             user_prompt=user_prompt,
#             context_cells=len(request.context or []),
#             tool_mode=tool_mode,
#         )
#
#         log(f"Sending to {client.provider_name}...")
#
#         # Convert images to dict format if present
#         images_data = None
#         if request.images:
#             images_data = [
#                 {
#                     "data": img.data,
#                     "mime_type": img.mime_type,
#                     "url": img.url,
#                     "filename": img.filename,
#                 }
#                 for img in request.images
#                 if img.data or img.url
#             ]
#             if images_data:
#                 log(f"Chat: {len(images_data)} image(s) attached")
#
#         # Pass separate notebook_context and user_prompt to LLM client
#         # This allows each provider to handle caching appropriately
#         llm_response = client.chat_panel_send(
#             notebook_context=notebook_context,
#             user_prompt=user_prompt,
#             images=images_data
#         )
#
#         # Process response
#         pending_tools = []
#         llm_steps = []
#         session_for_steps = None
#
#         if request.session_id:
#             session_for_steps = get_session_manager().get_session(request.session_id)
#             if session_for_steps:
#                 session_for_steps.clear_llm_steps()
#
#         if isinstance(llm_response, dict) and "pending_tool_calls" in llm_response:
#             tools_list = [t.get("name") for t in llm_response.get("pending_tool_calls", [])]
#             log(f"TOOLS CALLED: {', '.join(tools_list)}")
#             response_text = llm_response.get("response_text", "")
#             all_pending_tools = llm_response.get("pending_tool_calls", [])
#
#             # Record tool call steps
#             for tool in all_pending_tools:
#                 args_str = json.dumps(tool.get("arguments", {}), indent=2)
#                 if session_for_steps:
#                     session_for_steps.add_llm_step("tool_call", args_str, tool.get("name"))
#
#             # Handle based on tool mode
#             if tool_mode == "auto":
#                 # Auto-execute all tools
#                 tool_calls = [
#                     {"id": t["id"], "name": t["name"], "arguments": t["arguments"]}
#                     for t in all_pending_tools
#                 ]
#                 exec_response = client.execute_approved_tools(tool_calls)
#
#                 if isinstance(exec_response, dict):
#                     response_text = exec_response.get("response_text", "")
#                 else:
#                     response_text = exec_response
#
#                 llm_steps = session_for_steps.get_llm_steps() if session_for_steps else []
#
#             elif tool_mode == "ai_decide":
#                 # AI decides which tools need approval
#                 from backend.agent_roles import validate_tool_calls
#                 validation_result = validate_tool_calls(all_pending_tools, provider=provider)
#                 safe_tools = validation_result["safe_tools"]
#                 unsafe_tools = validation_result["unsafe_tools"]
#
#                 if safe_tools:
#                     safe_tool_calls = [
#                         {"id": t["id"], "name": t["name"], "arguments": t["arguments"]}
#                         for t in safe_tools
#                     ]
#                     exec_response = client.execute_approved_tools(safe_tool_calls)
#
#                     if isinstance(exec_response, dict) and "pending_tool_calls" in exec_response:
#                         additional_tools = exec_response.get("pending_tool_calls", [])
#                         response_text = exec_response.get("response_text", "")
#                         for t in additional_tools:
#                             unsafe_tools.append({
#                                 "id": t["id"],
#                                 "name": t["name"],
#                                 "arguments": t["arguments"],
#                                 "validation": {"reason": "Additional tool requested"},
#                             })
#
#                     if isinstance(exec_response, dict):
#                         response_text = exec_response.get("response_text", "")
#                     else:
#                         response_text = exec_response
#
#                 if unsafe_tools:
#                     pending_tools = [
#                         {
#                             "id": t["id"],
#                             "name": t["name"],
#                             "arguments": t["arguments"],
#                             "validation_reason": t.get("validation", {}).get("reason", "Requires approval"),
#                         }
#                         for t in unsafe_tools
#                     ]
#
#                     # Store client state
#                     if request.session_id:
#                         session = get_session_manager().get_session(request.session_id)
#                         if session:
#                             session.pending_client = client
#                 else:
#                     llm_steps = session_for_steps.get_llm_steps() if session_for_steps else []
#
#             else:
#                 # Manual mode - all tools need approval
#                 log(f"Manual mode - returning {len(all_pending_tools)} tools for approval")
#                 pending_tools = all_pending_tools
#                 if request.session_id:
#                     session = get_session_manager().get_session(request.session_id)
#                     if session:
#                         session.pending_client = client
#                         log(f"Stored pending_client in session {request.session_id}")
#                     else:
#                         log(f"WARNING: Session {request.session_id} not found!")
#                 else:
#                     log("WARNING: No session_id provided - cannot store pending_client!")
#         else:
#             response_text = llm_response if isinstance(llm_response, str) else str(llm_response)
#             llm_steps = session_for_steps.get_llm_steps() if session_for_steps else []
#             log("NO TOOLS - Direct response")
#
#         # Get notebook updates from session
#         session = get_session_manager().get_session(request.session_id) if request.session_id else None
#         updates = session.get_notebook_updates() if session else []
#
#         # Get remaining steps
#         if session_for_steps and len(llm_steps) == 0:
#             llm_steps = session_for_steps.get_llm_steps()
#
#         clear_current_session()
#
#         # Pretty print final response
#         log_resp_box(response_text)
#
#         return ChatResponse(
#             success=True,
#             response=response_text,
#             updates=updates,
#             pending_tool_calls=pending_tools,
#             steps=[LLMStep(**step) for step in llm_steps],
#         )
#
#     except Exception as e:
#         clear_current_session()
#         return ChatResponse(success=False, response="", error=str(e))


# @router.post("/execute-tools", response_model=ChatResponse)
# async def execute_approved_tools(
#     request: ExecuteToolsRequest,
#     authorized: bool = Depends(verify_internal_secret),
# ):
#     """Execute approved tool calls."""
#     try:
#         log(f"Execute-tools request: session_id={request.session_id}, tools={[t.name for t in request.approved_tools]}")
#
#         session = get_session_manager().get_session(request.session_id)
#
#         if not session:
#             log(f"Session not found: {request.session_id}")
#             return ChatResponse(success=False, response="", error="Session not found")
#
#         log(f"Session ready: {request.session_id}, kernel_alive: {session.kernel.is_alive()}")
#
#         client = session.pending_client
#         if not client:
#             log("No pending client found!")
#             return ChatResponse(success=False, response="", error="No pending tool calls")
#
#         set_current_session(request.session_id)
#
#         approved_tools_list = [tool.dict() for tool in request.approved_tools]
#         log(f"Executing approved tools: {approved_tools_list}")
#         exec_result = client.execute_approved_tools(approved_tools_list)
#         log(f"Execution result: {exec_result}")
#
#         if isinstance(exec_result, dict) and "pending_tool_calls" in exec_result:
#             response_text = exec_result.get("response_text", "")
#             pending_tools = exec_result.get("pending_tool_calls", [])
#             tool_results = exec_result.get("tool_results", [])
#
#             for tr in tool_results:
#                 result_str = str(tr.get("result", ""))[:500]
#                 session.add_llm_step("tool_result", result_str, tr.get("name"))
#
#             for tool in pending_tools:
#                 args_str = json.dumps(tool.get("arguments", {}), indent=2)
#                 session.add_llm_step("tool_call", args_str, tool.get("name"))
#
#             session.pending_client = client
#             updates = session.get_notebook_updates()
#             llm_steps = session.llm_steps.copy()
#             clear_current_session()
#
#             return ChatResponse(
#                 success=True,
#                 response=response_text,
#                 updates=updates,
#                 pending_tool_calls=[
#                     {"id": t["id"], "name": t["name"], "arguments": t["arguments"]}
#                     for t in pending_tools
#                 ],
#                 steps=[LLMStep(**step) for step in llm_steps],
#             )
#
#         if isinstance(exec_result, dict):
#             log(f"exec_result is dict with keys: {exec_result.keys()}")
#             response_text = exec_result.get("response_text", "")
#             tool_results = exec_result.get("tool_results", [])
#             log(f"Tool results: {len(tool_results)} results")
#             for tr in tool_results:
#                 result_str = str(tr.get("result", ""))[:500]
#                 log(f"Tool result for {tr.get('name')}: {result_str[:200]}...")
#                 session.add_llm_step("tool_result", result_str, tr.get("name"))
#         else:
#             log(f"exec_result is string: {str(exec_result)[:200]}")
#             response_text = exec_result
#
#         log(f"Final response_text: {response_text[:200] if response_text else 'EMPTY'}...")
#
#         if response_text and response_text != "Tool executed successfully.":
#             session.add_llm_step(
#                 "text",
#                 response_text[:200] + "..." if len(response_text) > 200 else response_text,
#             )
#
#         llm_steps = session.get_llm_steps()
#         updates = session.get_notebook_updates()
#
#         log(f"Returning: response_text={len(response_text) if response_text else 0} chars, steps={len(llm_steps)}, updates={len(updates)}")
#
#         session.pending_client = None
#         clear_current_session()
#
#         return ChatResponse(
#             success=True,
#             response=response_text,
#             updates=updates,
#             steps=[LLMStep(**step) for step in llm_steps],
#         )
#
#     except Exception as e:
#         clear_current_session()
#         return ChatResponse(success=False, response="", error=str(e))


# =============================================================================
# SSE STREAMING ENDPOINTS
# =============================================================================
# Track active chat clients for potential cancellation
_active_chat_clients: Dict[str, Any] = {}


@router.post("/stream")
async def chat_with_llm_stream(
    request: ChatRequest,
    raw_request: Request,
    authorized: bool = Depends(verify_internal_secret),
):
    """
    Chat with LLM assistant using SSE streaming.

    Returns Server-Sent Events stream with real-time progress updates.

    SSE Events:
    - event: thinking - Status message (e.g., "Analyzing request...")
    - event: tool_call - Tool is being called with arguments
    - event: tool_result - Tool execution result
    - event: pending_tools - Tools awaiting approval (manual/ai_decide mode)
    - event: done - Final response with all data
    - event: error - Error occurred

    In manual/ai_decide mode with pending tools:
    - Stream ends after sending pending_tools event
    - Frontend should call /chat/execute-tools/stream after user approval
    """
    session_id = request.session_id

    async def error_generator(error_msg: str):
        yield format_sse_event("error", {"error": error_msg})

    # Validate session_id - required for chat
    if not session_id:
        return StreamingResponse(
            error_generator("session_id is required for chat"),
            media_type="text/event-stream"
        )

    # Thread-safe queue for progress events
    progress_queue: queue.Queue = queue.Queue()

    def progress_callback(event_type: str, data: Any = None):
        """Callback that puts progress events into the queue."""
        progress_queue.put({"event": event_type, "data": data})

    # Capture key overrides from headers before entering generator
    _chat_raw_request = raw_request

    async def event_generator():
        """Generate SSE events for chat streaming."""
        provider = request.llm_provider or cfg.LLM_PROVIDER
        tool_mode = request.tool_mode or cfg.TOOL_EXECUTION_MODE
        auto_func = (tool_mode == "auto")

        log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log(f"📨 Chat SSE stream: provider={provider}, tool_mode={tool_mode}")
        log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        try:
            # LAZY KERNEL: Only set session ID - kernel created on-demand by tools
            # This allows parallel LLM requests (e.g., "what can you do?" runs immediately)
            set_current_session(session_id)
            log(f"Session ID set: {session_id} (kernel will be created lazily if needed)")

            # Extract per-request key overrides from headers
            key_override, model_override, base_url_override = extract_key_overrides(_chat_raw_request, provider)

            # Initialize LLM client
            try:
                client = get_llm_client(
                    provider=provider,
                    auto_function_calling=auto_func,
                    api_key_override=key_override,
                    model_override=model_override,
                    base_url_override=base_url_override,
                )
            except Exception as e:
                yield format_sse_event("error", {"error": str(e)})
                return

            # Track client for potential cancellation
            _active_chat_clients[session_id] = client

            # Build context
            format_map = {
                "xml": ContextFormat.XML,
                "json": ContextFormat.JSON,
                "plain": ContextFormat.PLAIN
            }
            ctx_format = format_map.get(request.context_format, ContextFormat.XML)
            context_manager = ContextManager()

            try:
                formatted_ctx = context_manager.build_chat_context(
                    cells=request.context or [],
                    user_prompt=request.message,
                    format=ctx_format
                )
                notebook_context = formatted_ctx.notebook_context
                user_prompt = formatted_ctx.user_prompt
            except Exception as e:
                yield format_sse_event("error", {"error": f"Failed to build context: {e}"})
                return

            # Set history
            llm_history = []
            for msg in request.history:
                llm_history.append({
                    "role": msg.role,
                    "content": msg.content,
                    "parts": [msg.content],
                })
            client.set_history(llm_history)

            # Log request (log_chat is called in LLM client with full details)
            log_user(request.message)
            log_request(
                source="CHAT_SSE",
                provider=provider,
                context_format=ctx_format.value,
                notebook_context=notebook_context,
                user_prompt=user_prompt,
                context_cells=len(request.context or []),
                tool_mode=tool_mode,
            )

            # Convert images
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

            # Send initial thinking event
            yield format_sse_event("thinking", {"message": "Analyzing your request..."})

            # Set up progress callback for real-time events
            client.set_progress_callback(progress_callback)

            # Run LLM in thread pool
            ctx = contextvars.copy_context()

            def run_llm():
                return ctx.run(
                    client.chat_panel_send,
                    notebook_context,
                    user_prompt,
                    images_data
                )

            loop = asyncio.get_event_loop()
            llm_future = loop.run_in_executor(None, run_llm)

            # Poll for progress events while LLM is running
            while not llm_future.done():
                try:
                    event = progress_queue.get_nowait()
                    sse_event = format_progress_event(event["event"], event["data"])
                    if sse_event:
                        log(f"SSE chat sending {event['event']}")
                        yield sse_event
                except queue.Empty:
                    pass
                await asyncio.sleep(0.05)

            # Get result
            llm_response = await llm_future

            # Drain remaining events
            while True:
                try:
                    event = progress_queue.get_nowait()
                    sse_event = format_progress_event(event["event"], event["data"])
                    if sse_event:
                        log(f"SSE chat sending {event['event']} (drain)")
                        yield sse_event
                except queue.Empty:
                    break

            # Get session for steps
            session_for_steps = get_session_manager().get_session(session_id)
            if session_for_steps:
                session_for_steps.clear_llm_steps()

            # Extract usage from client
            usage_data = getattr(client, '_last_usage', None)

            # Process response
            pending_tools = []
            llm_steps = []

            if isinstance(llm_response, dict) and "pending_tool_calls" in llm_response:
                # Tools were called
                all_pending_tools = llm_response.get("pending_tool_calls", [])
                response_text = llm_response.get("response_text", "")

                # Record tool call steps
                for tool in all_pending_tools:
                    args_str = json.dumps(tool.get("arguments", {}), indent=2)
                    if session_for_steps:
                        session_for_steps.add_llm_step("tool_call", args_str, tool.get("name"))
                    # Send tool_call event for each pending tool
                    yield format_sse_event("tool_call", {
                        "name": tool.get("name"),
                        "arguments": tool.get("arguments", {})
                    })

                if tool_mode == "auto":
                    # Auto mode - tools already executed, this is final response
                    llm_steps = session_for_steps.get_llm_steps() if session_for_steps else []

                elif tool_mode == "ai_decide":
                    # AI decides which tools need approval
                    from backend.agent_roles import validate_tool_calls
                    validation_result = validate_tool_calls(all_pending_tools, provider=provider)
                    safe_tools = validation_result["safe_tools"]
                    unsafe_tools = validation_result["unsafe_tools"]

                    if safe_tools:
                        # Execute safe tools
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
                        elif isinstance(exec_response, dict):
                            response_text = exec_response.get("response_text", "")
                        else:
                            response_text = exec_response

                    if unsafe_tools:
                        # Return unsafe tools for approval
                        pending_tools = [
                            {
                                "id": t["id"],
                                "name": t["name"],
                                "arguments": t["arguments"],
                                "validation_reason": t.get("validation", {}).get("reason", "Requires approval"),
                            }
                            for t in unsafe_tools
                        ]
                        # Store client for later execution
                        if session_for_steps:
                            session_for_steps.pending_client = client
                    else:
                        llm_steps = session_for_steps.get_llm_steps() if session_for_steps else []

                else:
                    # Manual mode - all tools need approval
                    pending_tools = all_pending_tools
                    if session_for_steps:
                        session_for_steps.pending_client = client
                        log(f"Stored pending_client in session {session_id}")

            else:
                # Direct response (no tools)
                response_text = llm_response if isinstance(llm_response, str) else str(llm_response)
                llm_steps = session_for_steps.get_llm_steps() if session_for_steps else []
                log("NO TOOLS - Direct response")

            # Get notebook updates
            updates = session_for_steps.get_notebook_updates() if session_for_steps else []

            # Send appropriate final event
            if pending_tools:
                # Send pending_tools event - stream will end, frontend handles approval
                log(f"SSE sending pending_tools: {[t['name'] for t in pending_tools]}")
                yield format_sse_event("pending_tools", {
                    "tools": pending_tools,
                    "response_text": response_text,
                })
                # Also send done event to signal stream end
                done_data = {
                    "success": True,
                    "response": response_text,
                    "pending_tool_calls": pending_tools,
                    "steps": [{"type": s["type"], "name": s.get("name"), "content": s["content"]} for s in llm_steps],
                    "updates": updates,
                    "has_pending_tools": True,
                }
                if usage_data:
                    done_data["usage"] = usage_data
                yield format_sse_event("done", done_data)
            else:
                # Final response
                log_resp_box(response_text)
                done_data = {
                    "success": True,
                    "response": response_text,
                    "pending_tool_calls": [],
                    "steps": [{"type": s["type"], "name": s.get("name"), "content": s["content"]} for s in llm_steps],
                    "updates": updates,
                    "has_pending_tools": False,
                }
                if usage_data:
                    done_data["usage"] = usage_data
                yield format_sse_event("done", done_data)

        except Exception as e:
            import traceback
            log(f"Chat SSE error: {e}\n{traceback.format_exc()}")
            error_msg = str(e)
            if "API" in error_msg or "key" in error_msg.lower():
                error_msg = "LLM API error. Please check your API key configuration."
            elif "timeout" in error_msg.lower():
                error_msg = "Request timed out. Please try again."
            yield format_sse_event("error", {"error": error_msg})
        finally:
            # Clean up
            if session_id in _active_chat_clients:
                del _active_chat_clients[session_id]
            clear_current_session()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/execute-tools/stream")
async def execute_tools_stream(
    request: ExecuteToolsRequest,
    raw_request: Request,
    authorized: bool = Depends(verify_internal_secret),
):
    """
    Execute approved tools with SSE streaming.

    Returns Server-Sent Events stream with real-time progress updates.

    SSE Events:
    - event: thinking - Status message
    - event: tool_executing - Tool is being executed
    - event: tool_result - Tool execution result
    - event: pending_tools - More tools need approval (chain continues)
    - event: done - Final response with all data
    - event: error - Error occurred
    """
    session_id = request.session_id

    async def error_generator(error_msg: str):
        yield format_sse_event("error", {"error": error_msg})

    # Thread-safe queue for progress events
    progress_queue: queue.Queue = queue.Queue()

    def progress_callback(event_type: str, data: Any = None):
        """Callback that puts progress events into the queue."""
        progress_queue.put({"event": event_type, "data": data})

    async def event_generator():
        """Generate SSE events for tool execution."""
        log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log(f"📨 Execute tools SSE stream: session={session_id}")
        log(f"   Tools: {[t.name for t in request.approved_tools]}")
        log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        try:
            session = get_session_manager().get_session(session_id)

            if not session:
                yield format_sse_event("error", {"error": "Session not found"})
                return

            client = session.pending_client
            if not client:
                yield format_sse_event("error", {"error": "No pending tool calls"})
                return

            set_current_session(session_id)
            _active_chat_clients[session_id] = client

            # Send initial thinking event
            yield format_sse_event("thinking", {"message": "Executing approved tools..."})

            # Send tool_executing events
            for tool in request.approved_tools:
                yield format_sse_event("tool_executing", {
                    "name": tool.name,
                    "arguments": tool.arguments
                })

            # Set up progress callback
            client.set_progress_callback(progress_callback)

            # Run tool execution in thread pool
            approved_tools_list = [tool.dict() for tool in request.approved_tools]
            ctx = contextvars.copy_context()

            def run_execution():
                return ctx.run(client.execute_approved_tools, approved_tools_list)

            loop = asyncio.get_event_loop()
            exec_future = loop.run_in_executor(None, run_execution)

            # Poll for progress events
            while not exec_future.done():
                try:
                    event = progress_queue.get_nowait()
                    sse_event = format_progress_event(event["event"], event["data"])
                    if sse_event:
                        log(f"SSE exec-tools sending {event['event']}")
                        yield sse_event
                except queue.Empty:
                    pass
                await asyncio.sleep(0.05)

            # Get result
            exec_result = await exec_future

            # Drain remaining events
            while True:
                try:
                    event = progress_queue.get_nowait()
                    sse_event = format_progress_event(event["event"], event["data"])
                    if sse_event:
                        yield sse_event
                except queue.Empty:
                    break

            # Process result
            pending_tools = []
            response_text = ""

            if isinstance(exec_result, dict) and "pending_tool_calls" in exec_result:
                # More tools needed
                response_text = exec_result.get("response_text", "")
                pending_tools = exec_result.get("pending_tool_calls", [])
                tool_results = exec_result.get("tool_results", [])

                # Record steps
                for tr in tool_results:
                    result_str = str(tr.get("result", ""))[:500]
                    session.add_llm_step("tool_result", result_str, tr.get("name"))
                    yield format_sse_event("tool_result", {
                        "name": tr.get("name"),
                        "result": result_str
                    })

                for tool in pending_tools:
                    args_str = json.dumps(tool.get("arguments", {}), indent=2)
                    session.add_llm_step("tool_call", args_str, tool.get("name"))

                # Keep client for next approval
                session.pending_client = client

            elif isinstance(exec_result, dict):
                response_text = exec_result.get("response_text", "")
                tool_results = exec_result.get("tool_results", [])
                for tr in tool_results:
                    result_str = str(tr.get("result", ""))[:500]
                    session.add_llm_step("tool_result", result_str, tr.get("name"))
                    yield format_sse_event("tool_result", {
                        "name": tr.get("name"),
                        "result": result_str
                    })
            else:
                response_text = exec_result

            # Get final data
            llm_steps = session.get_llm_steps()
            updates = session.get_notebook_updates()

            # Extract usage
            et_usage_data = getattr(client, '_last_usage', None)

            # Send final event
            if pending_tools:
                yield format_sse_event("pending_tools", {
                    "tools": pending_tools,
                    "response_text": response_text,
                })
                et_done_data = {
                    "success": True,
                    "response": response_text,
                    "pending_tool_calls": pending_tools,
                    "steps": [{"type": s["type"], "name": s.get("name"), "content": s["content"]} for s in llm_steps],
                    "updates": updates,
                    "has_pending_tools": True,
                }
                if et_usage_data:
                    et_done_data["usage"] = et_usage_data
                yield format_sse_event("done", et_done_data)
            else:
                # Final response - clear pending state
                session.pending_client = None
                log_resp_box(response_text)
                et_done_data = {
                    "success": True,
                    "response": response_text,
                    "pending_tool_calls": [],
                    "steps": [{"type": s["type"], "name": s.get("name"), "content": s["content"]} for s in llm_steps],
                    "updates": updates,
                    "has_pending_tools": False,
                }
                if et_usage_data:
                    et_done_data["usage"] = et_usage_data
                yield format_sse_event("done", et_done_data)

        except Exception as e:
            import traceback
            log(f"Execute tools SSE error: {e}\n{traceback.format_exc()}")
            yield format_sse_event("error", {"error": str(e)})
        finally:
            if session_id in _active_chat_clients:
                del _active_chat_clients[session_id]
            clear_current_session()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
