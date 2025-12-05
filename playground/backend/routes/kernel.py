"""
Kernel Routes - Handles Jupyter kernel operations and WebSocket connections

Now session-aware: uses session kernel when session_id is provided,
falls back to global kernel for backward compatibility.
"""

import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Set

from backend.kernel_manager import get_kernel
from backend.session_manager import get_session_manager


def get_kernel_for_session(session_id: Optional[str] = None):
    """Get kernel for session, creating session if needed, or global kernel if no session_id"""
    if session_id:
        # Get or create session with the given session_id
        session = get_session_manager().get_or_create_session(session_id, f"notebook-{session_id}")
        return session.kernel
    # Fallback to global kernel (backward compatibility)
    return get_kernel()

# Create API Router
router = APIRouter(prefix="", tags=["kernel"])


# === WebSocket Connection Manager ===
class ConnectionManager:
    """Manages WebSocket connections for kernel status updates"""
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._last_status: Optional[bool] = None
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)

    async def broadcast_status(self, running: bool, execution_count: int):
        """Broadcast kernel status to all connected clients"""
        message = {"type": "kernel_status", "running": running, "execution_count": execution_count}
        disconnected = set()
        async with self._lock:
            connections = self.active_connections.copy()
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        # Clean up disconnected
        if disconnected:
            async with self._lock:
                self.active_connections -= disconnected

ws_manager = ConnectionManager()


# === Pydantic Models ===

class ExecuteRequest(BaseModel):
    code: str
    cell_id: Optional[str] = None
    session_id: Optional[str] = None  # For session-scoped execution


class ExecuteResponse(BaseModel):
    success: bool
    execution_count: Optional[int]
    outputs: List[Dict[str, Any]]
    error: Optional[Any]


class KernelStatus(BaseModel):
    running: bool
    execution_count: int


# === Kernel Control Endpoints ===

@router.post("/kernel/start")
async def start_kernel():
    """Start the Jupyter kernel"""
    kernel = get_kernel()
    if kernel.is_alive():
        return {"success": True, "message": "Kernel already running"}

    success = kernel.start()
    if success:
        return {"success": True, "message": "Kernel started"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start kernel")


@router.post("/kernel/stop")
async def stop_kernel():
    """Stop the Jupyter kernel"""
    kernel = get_kernel()
    success = kernel.stop()
    if success:
        return {"success": True, "message": "Kernel stopped"}
    else:
        raise HTTPException(status_code=500, detail="Failed to stop kernel")


@router.post("/kernel/restart")
async def restart_kernel():
    """Restart the Jupyter kernel"""
    kernel = get_kernel()
    success = kernel.restart()
    if success:
        return {"success": True, "message": "Kernel restarted"}
    else:
        raise HTTPException(status_code=500, detail="Failed to restart kernel")


@router.post("/kernel/interrupt")
async def interrupt_kernel():
    """Interrupt the currently running code"""
    kernel = get_kernel()
    success = kernel.interrupt()
    if success:
        return {"success": True, "message": "Kernel interrupted"}
    else:
        raise HTTPException(status_code=500, detail="Failed to interrupt kernel")


@router.get("/kernel/status", response_model=KernelStatus)
async def kernel_status():
    """Get kernel status (HTTP fallback)"""
    kernel = get_kernel()
    return KernelStatus(
        running=kernel.is_alive(),
        execution_count=kernel.execution_count
    )


# === WebSocket Endpoints ===

@router.websocket("/ws/kernel")
async def websocket_kernel_status(websocket: WebSocket):
    """WebSocket endpoint for kernel status updates (no polling needed)"""
    await ws_manager.connect(websocket)
    kernel = get_kernel()

    try:
        # Send initial status
        await websocket.send_json({
            "type": "kernel_status",
            "running": kernel.is_alive(),
            "execution_count": kernel.execution_count
        })

        # Keep connection alive and send periodic updates
        last_status = kernel.is_alive()
        while True:
            await asyncio.sleep(3)  # Check every 3 seconds (server-side, no client spam)
            current_status = kernel.is_alive()
            # Only send if status changed
            if current_status != last_status:
                await websocket.send_json({
                    "type": "kernel_status",
                    "running": current_status,
                    "execution_count": kernel.execution_count
                })
                last_status = current_status

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


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

            # Get session-specific kernel or fall back to global
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
