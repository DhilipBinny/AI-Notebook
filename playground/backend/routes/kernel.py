"""
Kernel Routes - Handles WebSocket connections for code execution

All kernel operations use session-based kernels via session_id.
Session management endpoints are in routes/session.py.
"""

import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from backend.session_manager import get_session_manager


def get_kernel_for_session(session_id: str):
    """Get kernel for session. Requires session_id."""
    if not session_id:
        raise ValueError("session_id is required for kernel operations")
    # Get or create session with the given session_id
    session = get_session_manager().get_or_create_session(session_id, f"notebook-{session_id}")
    return session.kernel


# Create API Router
router = APIRouter(prefix="", tags=["kernel"])


# === Pydantic Models ===

class ExecuteRequest(BaseModel):
    code: str
    cell_id: Optional[str] = None
    session_id: str  # Required for session-scoped execution


class ExecuteResponse(BaseModel):
    success: bool
    execution_count: Optional[int]
    outputs: List[Dict[str, Any]]
    error: Optional[Any]


# === Code Execution Endpoints ===

@router.post("/execute", response_model=ExecuteResponse)
async def execute_code(request: ExecuteRequest):
    """Execute code in the kernel (session-aware)"""
    kernel = get_kernel_for_session(request.session_id)

    # Auto-start kernel if not running
    if not kernel.is_alive():
        if not kernel.start():
            raise HTTPException(status_code=500, detail="Failed to start kernel")

    result = kernel.execute(request.code)

    return ExecuteResponse(
        success=result["success"],
        execution_count=result["execution_count"],
        outputs=result["outputs"],
        error=result["error"]
    )


@router.websocket("/ws/execute")
async def websocket_execute(websocket: WebSocket):
    """WebSocket endpoint for streaming code execution (session-aware)"""
    await websocket.accept()

    try:
        while True:
            # Wait for code to execute
            data = await websocket.receive_json()
            code = data.get("code", "")
            cell_id = data.get("cell_id", "")
            session_id = data.get("session_id", None)  # Session ID for isolated kernel

            if not code.strip():
                await websocket.send_json({
                    "type": "error",
                    "cell_id": cell_id,
                    "ename": "EmptyCode",
                    "evalue": "No code to execute",
                    "traceback": []
                })
                await websocket.send_json({"type": "status", "cell_id": cell_id, "status": "error"})
                continue

            if not session_id:
                await websocket.send_json({
                    "type": "error",
                    "cell_id": cell_id,
                    "ename": "SessionError",
                    "evalue": "session_id is required",
                    "traceback": []
                })
                await websocket.send_json({"type": "status", "cell_id": cell_id, "status": "error"})
                continue

            # Get session-specific kernel
            kernel = get_kernel_for_session(session_id)

            # Auto-start kernel if not running
            if not kernel.is_alive():
                if not kernel.start():
                    await websocket.send_json({
                        "type": "error",
                        "cell_id": cell_id,
                        "ename": "KernelError",
                        "evalue": "Failed to start kernel",
                        "traceback": []
                    })
                    await websocket.send_json({"type": "status", "cell_id": cell_id, "status": "error"})
                    continue

            # Stream execution outputs
            for output in kernel.execute_streaming(code):
                # Add cell_id to every output message
                output["cell_id"] = cell_id
                await websocket.send_json(output)
                await asyncio.sleep(0)  # Yield to event loop for immediate sending

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket execute error: {e}")
