"""
Notebook State Manager - Session-aware state for LLM to access and modify notebooks

This module provides functions for LLM tools to access notebook state.
It works with the session manager to provide isolated state per session.
"""

from typing import List, Dict, Any, Optional


def set_notebook(cells: List[Dict[str, Any]], session_id: Optional[str] = None) -> None:
    """
    Set the notebook cells for LLM to operate on.

    Args:
        cells: List of cell dictionaries with structure:
            {id: str, type: str, content: str, output: str, cellNumber: int}
        session_id: Optional session ID. If provided, uses session-scoped state.
    """
    if session_id:
        # Use session-scoped state
        from backend.session_manager import get_session_manager
        session = get_session_manager().get_session(session_id)
        if session:
            session.set_notebook_cells(cells)
            print(f"✓ Session {session_id}: Notebook state updated: {len(cells)} cells loaded")
        else:
            print(f"✗ Session {session_id} not found")
    else:
        # Fallback to current session
        from backend.session_manager import get_current_session
        session = get_current_session()
        if session:
            session.set_notebook_cells(cells)
            print(f"✓ Notebook state updated: {len(cells)} cells loaded")
        else:
            # Legacy: use global state if no session
            _legacy_set_notebook(cells)


def get_notebook(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get the current notebook cells.

    Args:
        session_id: Optional session ID. If provided, uses session-scoped state.

    Returns:
        List of cell dictionaries
    """
    if session_id:
        from backend.session_manager import get_session_manager
        session = get_session_manager().get_session(session_id)
        if session:
            return session.get_notebook_cells()
        return []
    else:
        # Use current session
        from backend.session_manager import get_current_session
        session = get_current_session()
        if session:
            return session.get_notebook_cells()
        # Legacy fallback
        return _legacy_get_notebook()


def update_notebook(cells: List[Dict[str, Any]], session_id: Optional[str] = None) -> None:
    """
    Update the entire notebook cells array.

    Args:
        cells: Updated list of cell dictionaries
        session_id: Optional session ID
    """
    if session_id:
        from backend.session_manager import get_session_manager
        session = get_session_manager().get_session(session_id)
        if session:
            session.update_notebook_cells(cells)
    else:
        from backend.session_manager import get_current_session
        session = get_current_session()
        if session:
            session.update_notebook_cells(cells)
        else:
            _legacy_update_notebook(cells)


def add_notebook_update(update_type: str, data: Dict[str, Any], session_id: Optional[str] = None) -> None:
    """
    Track an update made by LLM to send back to frontend.

    Args:
        update_type: Type of update ("update_cell", "insert_cell", "delete_cell", "execute_cell")
        data: Update data specific to the update type
        session_id: Optional session ID
    """
    if session_id:
        from backend.session_manager import get_session_manager
        session = get_session_manager().get_session(session_id)
        if session:
            session.add_notebook_update(update_type, data)
    else:
        from backend.session_manager import get_current_session
        session = get_current_session()
        if session:
            session.add_notebook_update(update_type, data)
        else:
            _legacy_add_update(update_type, data)


def get_notebook_updates(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get and clear pending notebook updates.

    Args:
        session_id: Optional session ID

    Returns:
        List of update dictionaries
    """
    if session_id:
        from backend.session_manager import get_session_manager
        session = get_session_manager().get_session(session_id)
        if session:
            return session.get_notebook_updates()
        return []
    else:
        from backend.session_manager import get_current_session
        session = get_current_session()
        if session:
            return session.get_notebook_updates()
        return _legacy_get_updates()


def clear_notebook(session_id: Optional[str] = None) -> None:
    """Clear notebook state"""
    if session_id:
        from backend.session_manager import get_session_manager
        session = get_session_manager().get_session(session_id)
        if session:
            session.notebook_state = {"cells": [], "updates": []}
    else:
        from backend.session_manager import get_current_session
        session = get_current_session()
        if session:
            session.notebook_state = {"cells": [], "updates": []}
        else:
            _legacy_clear_notebook()


# ============================================================
# Legacy global state (for backward compatibility)
# ============================================================

_legacy_notebook = {
    "cells": [],
    "updates": []
}


def _legacy_set_notebook(cells: List[Dict[str, Any]]) -> None:
    global _legacy_notebook
    _legacy_notebook["cells"] = cells
    _legacy_notebook["updates"] = []
    print(f"✓ [Legacy] Notebook state updated: {len(cells)} cells loaded")


def _legacy_get_notebook() -> List[Dict[str, Any]]:
    return _legacy_notebook["cells"]


def _legacy_update_notebook(cells: List[Dict[str, Any]]) -> None:
    global _legacy_notebook
    _legacy_notebook["cells"] = cells


def _legacy_add_update(update_type: str, data: Dict[str, Any]) -> None:
    global _legacy_notebook
    _legacy_notebook["updates"].append({
        "type": update_type,
        "data": data
    })


def _legacy_get_updates() -> List[Dict[str, Any]]:
    global _legacy_notebook
    updates = _legacy_notebook["updates"].copy()
    _legacy_notebook["updates"] = []
    return updates


def _legacy_clear_notebook() -> None:
    global _legacy_notebook
    _legacy_notebook["cells"] = []
    _legacy_notebook["updates"] = []
