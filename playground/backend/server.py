"""
AI Notebook Playground - Headless FastAPI Server
Container-based kernel execution and LLM chat API.
No frontend - pure API for Master backend to proxy.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import backend.config as cfg
from backend.llm_client import LLMClient
from backend.utils.util_func import log_debug_message
from backend.notebook_state import get_notebook_updates
from backend.session_manager import get_session_manager, set_current_session, clear_current_session

from backend.route_kernel import router as kernel_router
from backend.route_notebook import router as notebook_router
from backend.route_session import router as session_router

# Initialize FastAPI
app = FastAPI(
    title="AI Notebook Playground",
    version="0.1.0",
    description="Headless notebook execution container"
)

# Get internal secret from environment (set by Master when spawning container)
INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "")


# === Security ===

async def verify_internal_secret(x_internal_secret: str = Header(None)):
    """Verify requests come from Master API"""
    if not INTERNAL_SECRET:
        # No secret configured - development mode
        return True

    if x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Invalid internal secret")

    return True


# === Pydantic Models ===

class CellContext(BaseModel):
    id: str
    type: str  # "code" or "markdown"
    content: str
    output: Optional[str] = None
    cellNumber: Optional[int] = None


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    context: List[CellContext] = []
    history: List[ChatMessage] = []
    session_id: Optional[str] = None
    # Note: all_cells removed - LLM tools now fetch from Master API directly


class PendingToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]


class LLMStep(BaseModel):
    type: str
    name: Optional[str] = None
    content: str
    timestamp: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool
    response: str
    error: Optional[str] = None
    updates: List[Dict[str, Any]] = []
    pending_tool_calls: List[PendingToolCall] = []
    steps: List[LLMStep] = []


# Note: NotebookSyncRequest removed - LLM tools now fetch from Master API directly


# === Include Routers ===

app.include_router(kernel_router)
app.include_router(notebook_router)
app.include_router(session_router)


# === Health & Status ===

@app.get("/health")
async def health_check():
    """Health check endpoint (no auth required)"""
    return {
        "status": "ok",
        "service": "playground",
        "provider": cfg.LLM_PROVIDER
    }


@app.get("/status")
async def status(authorized: bool = Depends(verify_internal_secret)):
    """Detailed status (auth required)"""
    session_manager = get_session_manager()
    return {
        "status": "ok",
        "llm_provider": cfg.LLM_PROVIDER,
        "tool_mode": cfg.TOOL_EXECUTION_MODE,
        "active_sessions": len(session_manager.sessions)
    }


# === LLM Configuration ===

@app.get("/llm/provider")
async def get_llm_provider(authorized: bool = Depends(verify_internal_secret)):
    """Get current LLM provider configuration"""
    return cfg.get_provider_info()


class SetProviderRequest(BaseModel):
    provider: str


@app.post("/llm/provider")
async def set_llm_provider(
    request: SetProviderRequest,
    authorized: bool = Depends(verify_internal_secret)
):
    """Switch LLM provider at runtime"""
    provider = request.provider.lower()

    if provider not in ["ollama", "gemini", "openai", "anthropic"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider: {provider}"
        )

    # Check API keys
    if provider == "gemini" and not cfg.GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")
    if provider == "openai" and not cfg.OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured")
    if provider == "anthropic" and not cfg.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured")

    cfg.LLM_PROVIDER = provider

    return {
        "success": True,
        "provider": provider,
        "message": f"LLM provider switched to {provider}"
    }


class SetToolModeRequest(BaseModel):
    mode: str


@app.post("/llm/tool-mode")
async def set_tool_mode(
    request: SetToolModeRequest,
    authorized: bool = Depends(verify_internal_secret)
):
    """Set tool execution mode"""
    mode = request.mode.lower()

    if mode not in ["auto", "manual", "ai_decide"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {mode}"
        )

    cfg.TOOL_EXECUTION_MODE = mode
    cfg.AUTO_FUNCTION_CALLING = (mode == "auto")

    log_debug_message(f"Tool mode set to: {mode}, AUTO_FUNCTION_CALLING: {cfg.AUTO_FUNCTION_CALLING}")

    return {
        "success": True,
        "mode": cfg.TOOL_EXECUTION_MODE
    }


@app.get("/llm/tool-mode")
async def get_tool_mode(authorized: bool = Depends(verify_internal_secret)):
    """Get current tool execution mode"""
    return {
        "mode": cfg.TOOL_EXECUTION_MODE,
        "auto_function_calling": cfg.AUTO_FUNCTION_CALLING
    }


# === Chat Endpoints ===
# Note: Notebook sync endpoint removed - LLM tools now fetch from Master API directly

@app.post("/chat", response_model=ChatResponse)
async def chat_with_llm(
    request: ChatRequest,
    authorized: bool = Depends(verify_internal_secret)
):
    """Chat with the LLM assistant"""
    try:
        from datetime import datetime

        log_debug_message(f"=== CHAT REQUEST ===")
        log_debug_message(f"User message: {request.message[:200]}..." if len(request.message) > 200 else f"User message: {request.message}")
        log_debug_message(f"Session ID: {request.session_id}")
        log_debug_message(f"History length: {len(request.history) if request.history else 0}")
        log_debug_message(f"Context cells: {len(request.context) if request.context else 0}")
        log_debug_message(f"Tool mode: {cfg.TOOL_EXECUTION_MODE}, Auto function calling: {cfg.AUTO_FUNCTION_CALLING}")

        # Get or create session - this ensures the session exists for tool execution
        # Note: LLM tools now fetch notebook data from Master API (no local sync needed)
        if request.session_id:
            session_manager = get_session_manager()
            session = session_manager.get_or_create_session(request.session_id, "notebook")
            log_debug_message(f"Session ready: {request.session_id}, kernel_alive: {session.kernel.is_alive()}")
            set_current_session(request.session_id)

        # Build context string
        context_str = ""
        if request.context:
            context_str = "\n\n--- NOTEBOOK CONTEXT ---\n"
            for cell in request.context:
                cell_num = cell.cellNumber if cell.cellNumber else "?"
                context_str += f"\n[Cell {cell_num}] ({cell.type.upper()}):\n```\n{cell.content}\n```"
                if cell.output:
                    context_str += f"\nOutput:\n```\n{cell.output}\n```"
            context_str += "\n--- END CONTEXT ---\n"

        # Initialize LLM client
        try:
            client = LLMClient()
        except Exception as e:
            return ChatResponse(success=False, response="", error=str(e))

        # Convert history to LLM format
        llm_history = []
        for msg in request.history:
            llm_history.append({
                "role": "user" if msg.role == "user" else "model",
                "parts": [msg.content]
            })
        client.set_history(llm_history)

        # Send message
        full_message = request.message
        if context_str:
            full_message = f"{context_str}\n\nUser message: {request.message}"

        log_debug_message(f"Sending to LLM: {full_message[:300]}..." if len(full_message) > 300 else f"Sending to LLM: {full_message}")
        llm_response = client.send_message(full_message)
        log_debug_message(f"LLM response type: {type(llm_response)}")
        log_debug_message(f"LLM response: {str(llm_response)[:500]}...")

        # Process response
        pending_tools = []
        llm_steps = []
        session_for_steps = None

        if request.session_id:
            session_for_steps = get_session_manager().get_session(request.session_id)
            if session_for_steps:
                session_for_steps.clear_llm_steps()

        if isinstance(llm_response, dict) and "pending_tool_calls" in llm_response:
            log_debug_message(f"LLM wants to call tools: {[t.get('name') for t in llm_response.get('pending_tool_calls', [])]}")
            response_text = llm_response.get("response_text", "")
            all_pending_tools = llm_response.get("pending_tool_calls", [])

            # Record tool call steps
            for tool in all_pending_tools:
                import json
                args_str = json.dumps(tool.get("arguments", {}), indent=2)
                if session_for_steps:
                    session_for_steps.add_llm_step("tool_call", args_str, tool.get("name"))

            # Handle based on tool mode
            if cfg.TOOL_EXECUTION_MODE == "auto":
                # Auto-execute all tools
                tool_calls = [{"id": t["id"], "name": t["name"], "arguments": t["arguments"]}
                             for t in all_pending_tools]
                exec_response = client.execute_approved_tools(tool_calls)

                if isinstance(exec_response, dict):
                    response_text = exec_response.get("response_text", "")
                else:
                    response_text = exec_response

                llm_steps = session_for_steps.get_llm_steps() if session_for_steps else []

            elif cfg.TOOL_EXECUTION_MODE == "ai_decide":
                # AI decides which tools need approval
                from backend.agent_roles import validate_tool_calls
                validation_result = validate_tool_calls(all_pending_tools, provider=cfg.LLM_PROVIDER)
                safe_tools = validation_result["safe_tools"]
                unsafe_tools = validation_result["unsafe_tools"]

                if safe_tools:
                    safe_tool_calls = [{"id": t["id"], "name": t["name"], "arguments": t["arguments"]}
                                      for t in safe_tools]
                    exec_response = client.execute_approved_tools(safe_tool_calls)

                    if isinstance(exec_response, dict) and "pending_tool_calls" in exec_response:
                        additional_tools = exec_response.get("pending_tool_calls", [])
                        response_text = exec_response.get("response_text", "")
                        for t in additional_tools:
                            unsafe_tools.append({
                                "id": t["id"], "name": t["name"], "arguments": t["arguments"],
                                "validation": {"reason": "Additional tool requested"}
                            })

                    if isinstance(exec_response, dict):
                        response_text = exec_response.get("response_text", "")
                    else:
                        response_text = exec_response

                if unsafe_tools:
                    pending_tools = [{
                        "id": t["id"], "name": t["name"], "arguments": t["arguments"],
                        "validation_reason": t.get("validation", {}).get("reason", "Requires approval")
                    } for t in unsafe_tools]

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

        # Get notebook updates
        updates = get_notebook_updates(session_id=request.session_id)

        # Get remaining steps
        if session_for_steps and len(llm_steps) == 0:
            llm_steps = session_for_steps.get_llm_steps()

        clear_current_session()

        return ChatResponse(
            success=True,
            response=response_text,
            updates=updates,
            pending_tool_calls=pending_tools,
            steps=[LLMStep(**step) for step in llm_steps]
        )

    except Exception as e:
        clear_current_session()
        return ChatResponse(success=False, response="", error=str(e))


class ExecuteToolsRequest(BaseModel):
    session_id: str
    approved_tools: List[PendingToolCall]


@app.post("/chat/execute-tools", response_model=ChatResponse)
async def execute_approved_tools(
    request: ExecuteToolsRequest,
    authorized: bool = Depends(verify_internal_secret)
):
    """Execute approved tool calls"""
    try:
        from datetime import datetime
        import json

        log_debug_message(f"Execute-tools request: session_id={request.session_id}, tools={[t.name for t in request.approved_tools]}")

        session_manager = get_session_manager()
        session = session_manager.get_session(request.session_id)

        if not session:
            log_debug_message(f"Session not found: {request.session_id}")
            return ChatResponse(success=False, response="", error="Session not found")

        client = session.pending_client
        log_debug_message(f"Pending client: {client}, type: {type(client)}")
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
                steps=[LLMStep(**step) for step in llm_steps]
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
            session.add_llm_step("text", response_text[:200] + "..." if len(response_text) > 200 else response_text)

        llm_steps = session.get_llm_steps()
        updates = get_notebook_updates(session_id=request.session_id)

        log_debug_message(f"Returning: response_text={len(response_text) if response_text else 0} chars, steps={len(llm_steps)}, updates={len(updates)}")

        session.pending_client = None
        clear_current_session()

        return ChatResponse(
            success=True,
            response=response_text,
            updates=updates,
            steps=[LLMStep(**step) for step in llm_steps]
        )

    except Exception as e:
        clear_current_session()
        return ChatResponse(success=False, response="", error=str(e))


# === Run Server ===

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
        log_level="info"
    )
