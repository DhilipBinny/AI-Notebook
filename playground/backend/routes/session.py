"""
Session Routes - API endpoints for session management
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from backend.session_manager import get_session_manager

router = APIRouter(prefix="/session", tags=["session"])


class CreateSessionRequest(BaseModel):
    notebook_name: str


class CreateSessionResponse(BaseModel):
    success: bool
    session_id: str
    notebook_name: str
    kernel_status: str
    message: str


class SessionInfoResponse(BaseModel):
    session_id: str
    notebook_name: str
    kernel_alive: bool
    created_at: str
    last_activity: str
    cell_count: int


@router.post("/create", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """
    Create a new session for a notebook.
    Each session has its own isolated kernel and state.
    """
    try:
        session_manager = get_session_manager()
        session = session_manager.create_session(request.notebook_name)

        # Start kernel for this session
        kernel_started = session.kernel.start()

        return CreateSessionResponse(
            success=True,
            session_id=session.session_id,
            notebook_name=session.notebook_name,
            kernel_status="running" if kernel_started else "failed",
            message=f"Session created for {request.notebook_name}"
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a session and cleanup its resources (kernel, state).
    """
    session_manager = get_session_manager()
    deleted = session_manager.delete_session(session_id)

    if deleted:
        return {
            "success": True,
            "message": f"Session {session_id} deleted"
        }
    else:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")


@router.post("/{session_id}/delete")
async def delete_session_post(session_id: str):
    """
    Delete a session via POST (for sendBeacon on page unload).
    sendBeacon only supports POST, not DELETE.
    """
    session_manager = get_session_manager()
    deleted = session_manager.delete_session(session_id)

    # Always return success for cleanup (don't error on page unload)
    return {
        "success": deleted,
        "message": f"Session {session_id} {'deleted' if deleted else 'not found'}"
    }


@router.get("/{session_id}", response_model=SessionInfoResponse)
async def get_session_info(session_id: str):
    """
    Get information about a specific session.
    """
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)

    if session:
        return SessionInfoResponse(
            session_id=session.session_id,
            notebook_name=session.notebook_name,
            kernel_alive=session.kernel.is_alive(),
            created_at=session.created_at.isoformat(),
            last_activity=session.last_activity.isoformat(),
            cell_count=len(session.notebook_state["cells"])
        )
    else:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")


@router.get("/", response_model=List[SessionInfoResponse])
async def list_sessions():
    """
    List all active sessions.
    """
    session_manager = get_session_manager()
    sessions = session_manager.get_all_sessions()

    return [
        SessionInfoResponse(
            session_id=s["session_id"],
            notebook_name=s["notebook_name"],
            kernel_alive=s["kernel_alive"],
            created_at=s["created_at"],
            last_activity=s["last_activity"],
            cell_count=s["cell_count"]
        )
        for s in sessions
    ]


@router.post("/{session_id}/kernel/start")
async def start_session_kernel(session_id: str):
    """Start the kernel for a specific session. Creates session if it doesn't exist."""
    session_manager = get_session_manager()

    # Get or create session - this allows starting kernel even if no code was run yet
    session = session_manager.get_or_create_session(session_id, "default")

    if session.kernel.is_alive():
        return {"success": True, "status": "already_running", "message": "Kernel already running"}

    started = session.kernel.start()
    if started:
        return {"success": True, "status": "started", "message": "Kernel started"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start kernel")


@router.post("/{session_id}/kernel/stop")
async def stop_session_kernel(session_id: str):
    """Stop the kernel for a specific session"""
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)

    if not session:
        # Session not found - kernel was never started, nothing to stop
        return {"success": True, "status": "not_running", "message": "Kernel was not running (no active session)"}

    stopped = session.kernel.stop()
    if stopped:
        return {"success": True, "status": "stopped", "message": "Kernel stopped"}
    else:
        raise HTTPException(status_code=500, detail="Failed to stop kernel")


@router.post("/{session_id}/kernel/restart")
async def restart_session_kernel(session_id: str):
    """Restart the kernel for a specific session"""
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)

    if not session:
        # Session not found - kernel was never started, nothing to restart
        return {"success": True, "status": "not_running", "message": "Kernel was not running (no active session)"}

    restarted = session.kernel.restart()
    if restarted:
        return {"success": True, "status": "restarted", "message": "Kernel restarted"}
    else:
        raise HTTPException(status_code=500, detail="Failed to restart kernel")


@router.post("/{session_id}/kernel/interrupt")
async def interrupt_session_kernel(session_id: str):
    """Interrupt the kernel for a specific session"""
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)

    if not session:
        # Session not found - kernel was never started, nothing to interrupt
        return {"success": True, "message": "Kernel was not running (no active session)"}

    interrupted = session.kernel.interrupt()
    if interrupted:
        return {"success": True, "message": "Kernel interrupted"}
    else:
        raise HTTPException(status_code=500, detail="Failed to interrupt kernel")


@router.get("/{session_id}/kernel/status")
async def get_session_kernel_status(session_id: str):
    """
    Get kernel status for a specific session.

    Returns:
        status: 'idle' | 'busy' | 'stopped' | 'error'
        - idle: Kernel running and ready for execution
        - busy: Kernel is executing code
        - stopped: Kernel not started or stopped
        - error: Kernel in error state
    """
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)

    if not session:
        # Session not found - kernel not started yet
        return {
            "success": True,
            "session_id": session_id,
            "status": "stopped",
            "execution_count": 0
        }

    return {
        "success": True,
        "session_id": session_id,
        "status": session.kernel.get_status(),
        "execution_count": session.kernel.execution_count
    }
