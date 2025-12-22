"""
Session Manager - Manages isolated sessions for each notebook

Each session has:
- Unique session ID
- Its own Jupyter kernel (isolated Python environment)
- Its own notebook state (for LLM tools)
- Associated notebook name

Thread Safety:
- Uses contextvars for current session to support concurrent requests
- Each async request gets its own context, preventing race conditions
"""

import uuid
import threading
import contextvars
from datetime import datetime
from typing import Dict, Any, Optional, List

from backend.kernel_manager import NotebookKernel


class Session:
    """Represents a single notebook session with isolated resources"""

    def __init__(self, session_id: str, notebook_name: str):
        self.session_id = session_id
        self.notebook_name = notebook_name
        self.kernel = NotebookKernel()
        self.notebook_state = {
            "cells": [],
            "updates": []
        }
        self.created_at = datetime.now()
        self.last_activity = datetime.now()

        # Thread lock for session-level operations
        self._lock = threading.Lock()

        # Pending tool calls state (for manual function calling approval)
        self.pending_client = None  # LLM client with pending state
        self.pending_messages = []  # Chat messages awaiting tool execution
        self.pending_notebook_name = ""  # Notebook name for saving history

        # LLM steps tracking (tool calls, results - for UI display only)
        self.llm_steps = []  # List of {"type": "tool_call"|"tool_result"|"text", "name": str, "content": str}

    def add_llm_step(self, step_type: str, content: str, name: str = None):
        """Add a step to the LLM steps list (thread-safe)"""
        with self._lock:
            step = {
                "type": step_type,
                "content": content,
                "timestamp": datetime.now().isoformat()
            }
            if name:
                step["name"] = name
            self.llm_steps.append(step)
            self.last_activity = datetime.now()

    def get_llm_steps(self) -> List[Dict[str, Any]]:
        """Get and clear the LLM steps list (thread-safe)"""
        with self._lock:
            steps = self.llm_steps.copy()
            self.llm_steps = []
            return steps

    def clear_llm_steps(self):
        """Clear the LLM steps list (thread-safe)"""
        with self._lock:
            self.llm_steps = []

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()

    def set_notebook_cells(self, cells: List[Dict[str, Any]]):
        """Set notebook cells for this session (thread-safe)"""
        with self._lock:
            self.notebook_state["cells"] = cells
            self.notebook_state["updates"] = []
            self.last_activity = datetime.now()

    def get_notebook_cells(self) -> List[Dict[str, Any]]:
        """Get notebook cells for this session (thread-safe)"""
        with self._lock:
            return self.notebook_state["cells"].copy()

    def update_notebook_cells(self, cells: List[Dict[str, Any]]):
        """Update notebook cells (thread-safe)"""
        with self._lock:
            self.notebook_state["cells"] = cells
            self.last_activity = datetime.now()

    def add_notebook_update(self, update_type: str, data: Dict[str, Any]):
        """Track a notebook update for this session (thread-safe)"""
        with self._lock:
            self.notebook_state["updates"].append({
                "type": update_type,
                "data": data
            })
            self.last_activity = datetime.now()

    def get_notebook_updates(self) -> List[Dict[str, Any]]:
        """Get and clear pending notebook updates (thread-safe)"""
        with self._lock:
            updates = self.notebook_state["updates"].copy()
            self.notebook_state["updates"] = []
            return updates

    def cleanup(self):
        """Cleanup session resources (thread-safe with exception handling)"""
        from backend.utils.util_func import log
        try:
            # Stop kernel first
            if self.kernel.is_alive():
                self.kernel.stop()
        except Exception as e:
            log(f"[Session] Error stopping kernel: {e}")

        try:
            # Cleanup sandbox kernel for this session
            from backend.llm_tools.tool_sandbox import cleanup_sandbox
            cleanup_sandbox(self.session_id)
        except Exception as e:
            log(f"[Session] Error cleaning up sandbox: {e}")

        # Always clear state, even if cleanup failed
        with self._lock:
            self.notebook_state = {"cells": [], "updates": []}
            self.llm_steps = []

        log(f"[Session] Cleaned up session {self.session_id}")


class SessionManager:
    """Manages all notebook sessions"""

    def __init__(self, max_sessions: int = 10, session_timeout_minutes: int = 60):
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()
        self.max_sessions = max_sessions
        self.session_timeout_minutes = session_timeout_minutes

    def create_session(self, notebook_name: str, session_id: str = None) -> Session:
        """
        Create a new session for a notebook.

        Args:
            notebook_name: Name of the notebook file
            session_id: Optional custom session ID. If not provided, generates one.

        Returns:
            New Session object
        """
        with self._lock:
            # Check if we've reached max sessions
            if len(self._sessions) >= self.max_sessions:
                # Try to cleanup inactive sessions first
                self._cleanup_inactive_sessions()

                # If still at max, raise error
                if len(self._sessions) >= self.max_sessions:
                    raise RuntimeError(f"Maximum sessions ({self.max_sessions}) reached. Close some notebooks first.")

            # Use provided session ID or generate one
            if session_id is None:
                session_id = uuid.uuid4().hex[:12]

            # Create new session
            session = Session(session_id, notebook_name)
            self._sessions[session_id] = session

            print(f"[SessionManager] Created session {session_id} for {notebook_name}")
            print(f"[SessionManager] Active sessions: {len(self._sessions)}")

            return session

    def get_or_create_session(self, session_id: str, notebook_name: str = "default") -> Session:
        """
        Get an existing session or create a new one with the given ID.

        Args:
            session_id: The session ID to look up or use for creation
            notebook_name: Name for the notebook if creating new session

        Returns:
            Session object
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.update_activity()
                return session

            # Create new session inside the lock to prevent race condition
            # Check if we've reached max sessions
            if len(self._sessions) >= self.max_sessions:
                # Try to cleanup inactive sessions first
                self._cleanup_inactive_sessions()

                # If still at max, raise error
                if len(self._sessions) >= self.max_sessions:
                    raise RuntimeError(f"Maximum sessions ({self.max_sessions}) reached. Close some notebooks first.")

            # Create new session
            session = Session(session_id, notebook_name)
            self._sessions[session_id] = session

            print(f"[SessionManager] Created session {session_id} for {notebook_name}")
            print(f"[SessionManager] Active sessions: {len(self._sessions)}")

            return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.

        Args:
            session_id: The session ID

        Returns:
            Session object or None if not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.update_activity()
            return session

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and cleanup its resources.

        Args:
            session_id: The session ID

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                session.cleanup()
                print(f"[SessionManager] Deleted session {session_id}")
                print(f"[SessionManager] Active sessions: {len(self._sessions)}")
                return True
            return False

    @property
    def session_count(self) -> int:
        """Get the number of active sessions."""
        with self._lock:
            return len(self._sessions)

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """
        Get info about all active sessions.

        Returns:
            List of session info dictionaries
        """
        with self._lock:
            sessions_info = []
            for session_id, session in self._sessions.items():
                sessions_info.append({
                    "session_id": session_id,
                    "notebook_name": session.notebook_name,
                    "kernel_alive": session.kernel.is_alive(),
                    "created_at": session.created_at.isoformat(),
                    "last_activity": session.last_activity.isoformat(),
                    "cell_count": len(session.notebook_state["cells"])
                })
            return sessions_info

    def _cleanup_inactive_sessions(self):
        """Remove sessions that have been inactive for too long"""
        now = datetime.now()
        to_delete = []

        for session_id, session in self._sessions.items():
            inactive_minutes = (now - session.last_activity).total_seconds() / 60
            if inactive_minutes > self.session_timeout_minutes:
                to_delete.append(session_id)

        for session_id in to_delete:
            session = self._sessions.pop(session_id, None)
            if session:
                session.cleanup()
                print(f"[SessionManager] Auto-cleaned inactive session {session_id}")

    def cleanup_all(self):
        """Cleanup all sessions (for server shutdown)"""
        with self._lock:
            for session_id, session in list(self._sessions.items()):
                session.cleanup()
            self._sessions.clear()
            print("[SessionManager] All sessions cleaned up")


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create the global session manager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


# Convenience functions for LLM tools (session-aware)
# Uses contextvars for thread/async safety - each request gets its own context
_current_session_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'current_session_id', default=None
)


def set_current_session(session_id: str):
    """
    Set the current session ID for LLM tools.

    Uses contextvars for thread safety - safe for concurrent requests
    with different sessions.
    """
    _current_session_id.set(session_id)


def get_current_session() -> Optional[Session]:
    """
    Get the current session for LLM tools (LAZY KERNEL).

    Returns the session associated with the current request context.
    Creates the session/kernel on first access (lazy initialization).
    This allows LLM calls to run in parallel - kernel is only created
    when tools actually need to execute code.

    Thread-safe for concurrent requests.
    """
    session_id = _current_session_id.get()
    if session_id is None:
        return None
    # LAZY: Create session with kernel only when first accessed by a tool
    # This allows parallel LLM requests - kernel created on-demand
    return get_session_manager().get_or_create_session(session_id)


def clear_current_session():
    """Clear the current session ID for this context"""
    _current_session_id.set(None)
