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
from backend.utils.util_func import log_debug_message, log_chat_header, log_user_message, log_llm_response_box
from backend.notebook_state import get_notebook_updates
from backend.context_manager import ContextManager
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


class LLMCompleteRequest(BaseModel):
    prompt: str
    max_tokens: int = 1000


class AICellRequest(BaseModel):
    """Request for AI Cell execution"""
    prompt: str
    context: List[CellContext] = []  # Full notebook context
    ai_cell_id: Optional[str] = None  # The AI cell's own ID for positional awareness
    ai_cell_index: Optional[int] = None  # The AI cell's position (0-based)
    session_id: Optional[str] = None


class AICellResponse(BaseModel):
    """Response from AI Cell"""
    success: bool
    response: str
    model: str = ""
    error: Optional[str] = None


# AI Cell system prompt - focused on notebook analysis with tools for inspection and experimentation
AI_CELL_SYSTEM_PROMPT = """You are an AI assistant embedded in a notebook cell. You can INSPECT and TEST but NOT modify the notebook directly.

POSITION: {position_info}

CRITICAL - RUNTIME vs STATIC DATA:
- The NOTEBOOK CONTEXT below shows STATIC cell previews (code text, not executed results)
- For RUNTIME data (actual variable values, types, errors), you MUST use kernel inspection tools
- ALWAYS use inspect_variables() for "what variables?" questions - don't just read cell text!

CELL REFERENCES:
- Cells shown as @cell-xxx or `cell-xxx` (e.g., @cell-abc123 or `cell-abc123`)
- "above" = cells BEFORE your position, "below" = cells AFTER
- Use these formats in your responses so users can click to navigate

TOOL PRIORITY (MUST follow this order):

1. **FIRST - Kernel Inspection** (ALWAYS start here for runtime questions):
   - inspect_variables() - List all RUNTIME variables with actual types, shapes, values
   - inspect_variable(name) - Detailed info: DataFrame columns, dtypes, sample rows
   - list_functions() - User-defined functions with signatures
   - list_imports() - Actually imported modules (not just written in cells)
   - kernel_info() - Memory usage, execution count
   - get_last_error() - Get most recent error with traceback
   - get_dataframe_info(name) - Detailed DataFrame inspection
   - get_cell_outputs(cell_id) - Get execution outputs from a cell
   - search_notebook(query) - Search for text in cells

   USE FOR: "what variables?", "show my data", "what type is x?", "why error?"

2. **SECOND - Sandbox Testing** (verify code before suggesting):
   - sandbox_execute(code) - Run code in ISOLATED kernel (safe testing)
   - sandbox_sync_from_main(["var1", "var2"]) - Copy variables to sandbox
   - sandbox_reset() - Clear sandbox state

EXAMPLES - Correct Tool Usage:
- "What variables do I have?" → inspect_variables() (NOT reading cell previews)
- "What's in my DataFrame?" → inspect_variable("df") or get_dataframe_info("df")
- "Why did this error?" → get_last_error() then inspect relevant variables
- "Where is X defined?" → search_notebook("X =") to find the cell

WORKFLOW:
1. User asks about data → inspect_variables() first (RUNTIME values)
2. Need details → inspect_variable("df") to see columns, types, sample
3. Suggesting code → sandbox_execute() to verify it works
4. Reference the cell where code should go using @cell-xxx or `cell-xxx`

OUTPUT FORMAT:
- Wrap code in ```python blocks
- Show sandbox output when helpful
- Reference cells as @cell-xxx or `cell-xxx` (clickable in UI)
- Be concise

{notebook_context}

USER QUESTION:
{user_prompt}
"""


@app.post("/ai-cell/run", response_model=AICellResponse)
async def run_ai_cell(
    request: AICellRequest,
    authorized: bool = Depends(verify_internal_secret)
):
    """
    Run an AI Cell - inline Q&A with notebook context and web search.
    No tool calling for cell modification - just analysis and suggestions.
    """
    try:
        log_debug_message(f"🤖 AI Cell request: {request.prompt[:100]}...")

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

        # Build notebook context with positional sections
        cells_above = []
        cells_below = []

        if request.context:
            for i, cell in enumerate(request.context):
                cell_type = "Code" if cell.type == "code" else cell.type.capitalize()

                # Build cell info with @cell_id reference
                cell_info = f"[@{cell.id}] ({cell_type}):\n"
                cell_info += cell.content
                if cell.output:
                    cell_info += f"\n[Output]: {cell.output[:500]}"

                # Determine if this cell is above or below the AI cell
                # Context cells are ordered, but we need to map their original position
                cell_position = cell.cellNumber - 1 if cell.cellNumber else i

                if ai_cell_index >= 0 and cell_position < ai_cell_index:
                    cells_above.append((cell_position, cell_info, cell.id))
                else:
                    cells_below.append((cell_position, cell_info, cell.id))

        # Sort by position
        cells_above.sort(key=lambda x: x[0])
        cells_below.sort(key=lambda x: x[0])

        # Build structured context
        notebook_context = ""

        if cells_above:
            notebook_context += "=== CELLS ABOVE YOU ===\n"
            for pos, info, cell_id in cells_above:
                # Mark the immediately above cell
                if pos == ai_cell_index - 1:
                    notebook_context += f"\n[IMMEDIATELY ABOVE] {info}\n"
                else:
                    notebook_context += f"\n{info}\n"

        notebook_context += f"\n=== YOUR POSITION (AI Cell #{ai_cell_index + 1}) ===\n"

        if cells_below:
            notebook_context += "\n=== CELLS BELOW YOU ===\n"
            for pos, info, cell_id in cells_below:
                # Mark the immediately below cell
                if pos == ai_cell_index + 1:
                    notebook_context += f"\n[IMMEDIATELY BELOW] {info}\n"
                else:
                    notebook_context += f"\n{info}\n"

        if not cells_above and not cells_below:
            notebook_context = "(No other cells in notebook)"

        # Build the prompt with context
        full_prompt = AI_CELL_SYSTEM_PROMPT.format(
            position_info=position_info,
            notebook_context=notebook_context,
            user_prompt=request.prompt
        )

        log_debug_message(f"📋 AI Cell context: {len(notebook_context)} chars, position: {ai_cell_index + 1}/{total_cells}")

        # Set up session for AI cell tools to access main kernel
        from backend.session_manager import get_session_manager, set_current_session
        session_id = request.session_id or "ai-cell-default"
        session = get_session_manager().get_or_create_session(session_id, "ai-cell")
        set_current_session(session_id)

        # Use LLM client with AI cell tools (inspection + sandbox)
        from backend.llm_client import LLMClient
        client = LLMClient()

        # AI cells now have access to kernel inspection and sandbox tools
        response_text = client.ai_cell_with_tools(full_prompt)

        log_debug_message(f"🤖 AI Cell response: {len(response_text)} chars")

        return AICellResponse(
            success=True,
            response=response_text,
            model=cfg.LLM_PROVIDER
        )

    except Exception as e:
        log_debug_message(f"🤖 AI Cell error: {e}")
        import traceback
        traceback.print_exc()
        return AICellResponse(
            success=False,
            response="",
            error=str(e)
        )


@app.post("/llm/complete")
async def llm_complete(
    request: LLMCompleteRequest,
    authorized: bool = Depends(verify_internal_secret)
):
    """
    Simple text completion without tools.
    Used for summarization and other simple LLM tasks.
    """
    try:
        log_debug_message(f"LLM complete request: {request.prompt[:200]}...")

        # Use LLMClient's chat_completion method
        client = LLMClient()
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

        # Pretty print chat request header
        log_chat_header(cfg.LLM_PROVIDER.upper(), cfg.TOOL_EXECUTION_MODE, len(request.context) if request.context else 0)
        log_user_message(request.message)

        # Get or create session - this ensures the session exists for tool execution
        # Note: LLM tools now fetch notebook data from Master API (no local sync needed)
        if request.session_id:
            session_manager = get_session_manager()
            session = session_manager.get_or_create_session(request.session_id, "notebook")
            log_debug_message(f"Session ready: {request.session_id}, kernel_alive: {session.kernel.is_alive()}")
            set_current_session(request.session_id)

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
                        "cellNumber": cell.cellNumber
                    }
                    for cell in request.context
                ]
                context_str = context_manager.process_context(cells_data)
            except Exception as e:
                # Fallback to simple format if context manager fails
                log_debug_message(f"⚠️ Context manager error, using simple format: {e}")
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
            full_message = f"=== NOTEBOOK CONTEXT ===\n\n{context_str}\n\n[MESSAGE]\n{request.message}"
            # Log the full context being sent to LLM
            log_debug_message(f"📋 Context prepared: {len(context_str)} chars, {len(request.context) if request.context else 0} cells")
            print(f"\n{'='*60}")
            print(f"CONTEXT SENT TO LLM ({len(context_str)} chars):")
            print(f"{'='*60}")
            print(context_str)
            print(f"{'='*60}\n")

        log_debug_message(f"📤 Sending to {client.provider_name}...")
        llm_response = client.send_message(full_message)

        # Process response
        pending_tools = []
        llm_steps = []
        session_for_steps = None

        if request.session_id:
            session_for_steps = get_session_manager().get_session(request.session_id)
            if session_for_steps:
                session_for_steps.clear_llm_steps()

        if isinstance(llm_response, dict) and "pending_tool_calls" in llm_response:
            tools_list = [t.get('name') for t in llm_response.get('pending_tool_calls', [])]
            log_debug_message(f"🔧 TOOLS CALLED: {', '.join(tools_list)}")
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
            log_debug_message(f"💭 NO TOOLS - Direct response")

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


# === Logging Filter ===

import logging

class HealthCheckFilter(logging.Filter):
    """Filter out health check request logs to reduce noise"""
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        # Skip health check logs
        if 'GET /health' in message:
            return False
        return True

# Apply filter at module load time (works with uvicorn)
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


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
