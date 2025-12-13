"""
Chat Routes - Chat with LLM assistant with tool calling support
"""

import json
from fastapi import APIRouter, Depends

import backend.config as cfg
from backend.llm_clients import get_llm_client
from backend.middleware.security import verify_internal_secret
from backend.models import (
    ChatRequest,
    ChatResponse,
    ExecuteToolsRequest,
    LLMStep,
)
from backend.context_manager import ContextManager, ContextFormat
from backend.session_manager import (
    get_session_manager,
    set_current_session,
    clear_current_session,
)
from backend.utils.util_func import (
    log,
    log_chat,
    log_user,
    log_resp_box,
    log_request,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
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
        log_chat(provider.upper(), tool_mode, len(request.context) if request.context else 0)
        log_user(request.message)

        # Get or create session - ensures session exists for tool execution
        if request.session_id:
            try:
                session = get_session_manager().get_or_create_session(request.session_id)
                set_current_session(request.session_id)
                log(f"Session ready: {request.session_id}, kernel_alive: {session.kernel.is_alive()}")
            except RuntimeError as e:
                log(f"Chat session error: {e}")
                return ChatResponse(success=False, response="", error=str(e))

        # Build context using ContextManager - returns FormattedContext with separate parts
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
            # Context manager failed - don't proceed without context
            log(f"Context manager error: {e}")
            return ChatResponse(success=False, response="", error=f"Failed to build context: {e}")

        # Initialize LLM client with provider and tool mode from request
        # auto -> client handles tools automatically (loops until done)
        # ai_decide/manual -> client returns pending tools for route to handle
        auto_func = (tool_mode == "auto")
        try:
            client = get_llm_client(provider=provider, auto_function_calling=auto_func)
        except Exception as e:
            return ChatResponse(success=False, response="", error=str(e))

        # Convert history to neutral format - each LLM client handles role conversion
        # Uses "assistant" (standard) which Gemini converts to "model" in set_history
        llm_history = []
        for msg in request.history:
            llm_history.append({
                "role": msg.role,  # "user" or "assistant" - client handles conversion
                "content": msg.content,
                "parts": [msg.content],  # For backward compatibility with Gemini format
            })
        client.set_history(llm_history)

        # Log the full context being sent to LLM
        log_request(
            source="CHAT",
            provider=provider,
            context_format=ctx_format.value,
            notebook_context=notebook_context,
            user_prompt=user_prompt,
            context_cells=len(request.context or []),
            tool_mode=tool_mode,
        )

        log(f"Sending to {client.provider_name}...")

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
                log(f"Chat: {len(images_data)} image(s) attached")

        # Pass separate notebook_context and user_prompt to LLM client
        # This allows each provider to handle caching appropriately
        llm_response = client.chat_panel_send(
            notebook_context=notebook_context,
            user_prompt=user_prompt,
            images=images_data
        )

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
            log(f"TOOLS CALLED: {', '.join(tools_list)}")
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
                log(f"Manual mode - returning {len(all_pending_tools)} tools for approval")
                pending_tools = all_pending_tools
                if request.session_id:
                    session = get_session_manager().get_session(request.session_id)
                    if session:
                        session.pending_client = client
                        log(f"Stored pending_client in session {request.session_id}")
                    else:
                        log(f"WARNING: Session {request.session_id} not found!")
                else:
                    log("WARNING: No session_id provided - cannot store pending_client!")
        else:
            response_text = llm_response if isinstance(llm_response, str) else str(llm_response)
            llm_steps = session_for_steps.get_llm_steps() if session_for_steps else []
            log("NO TOOLS - Direct response")

        # Get notebook updates from session
        session = get_session_manager().get_session(request.session_id) if request.session_id else None
        updates = session.get_notebook_updates() if session else []

        # Get remaining steps
        if session_for_steps and len(llm_steps) == 0:
            llm_steps = session_for_steps.get_llm_steps()

        clear_current_session()

        # Pretty print final response
        log_resp_box(response_text)

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


@router.post("/execute-tools", response_model=ChatResponse)
async def execute_approved_tools(
    request: ExecuteToolsRequest,
    authorized: bool = Depends(verify_internal_secret),
):
    """Execute approved tool calls."""
    try:
        log(f"Execute-tools request: session_id={request.session_id}, tools={[t.name for t in request.approved_tools]}")

        session = get_session_manager().get_session(request.session_id)

        if not session:
            log(f"Session not found: {request.session_id}")
            return ChatResponse(success=False, response="", error="Session not found")

        log(f"Session ready: {request.session_id}, kernel_alive: {session.kernel.is_alive()}")

        client = session.pending_client
        if not client:
            log("No pending client found!")
            return ChatResponse(success=False, response="", error="No pending tool calls")

        set_current_session(request.session_id)

        approved_tools_list = [tool.dict() for tool in request.approved_tools]
        log(f"Executing approved tools: {approved_tools_list}")
        exec_result = client.execute_approved_tools(approved_tools_list)
        log(f"Execution result: {exec_result}")

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
            updates = session.get_notebook_updates()
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
            log(f"exec_result is dict with keys: {exec_result.keys()}")
            response_text = exec_result.get("response_text", "")
            tool_results = exec_result.get("tool_results", [])
            log(f"Tool results: {len(tool_results)} results")
            for tr in tool_results:
                result_str = str(tr.get("result", ""))[:500]
                log(f"Tool result for {tr.get('name')}: {result_str[:200]}...")
                session.add_llm_step("tool_result", result_str, tr.get("name"))
        else:
            log(f"exec_result is string: {str(exec_result)[:200]}")
            response_text = exec_result

        log(f"Final response_text: {response_text[:200] if response_text else 'EMPTY'}...")

        if response_text and response_text != "Tool executed successfully.":
            session.add_llm_step(
                "text",
                response_text[:200] + "..." if len(response_text) > 200 else response_text,
            )

        llm_steps = session.get_llm_steps()
        updates = session.get_notebook_updates()

        log(f"Returning: response_text={len(response_text) if response_text else 0} chars, steps={len(llm_steps)}, updates={len(updates)}")

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
