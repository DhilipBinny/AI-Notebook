"""
Notebook Update Broadcaster - Real-time cell updates via WebSocket

Broadcasts cell changes to connected frontend clients when LLM tools
modify cells through the internal API.
"""

import asyncio
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class NotebookUpdate:
    """Represents a cell update to broadcast"""
    update_type: str  # 'cell_created', 'cell_updated', 'cell_deleted', 'cell_executed'
    cell_id: str
    cell_index: Optional[int] = None
    content: Optional[str] = None
    cell_type: Optional[str] = None
    outputs: Optional[list] = None
    execution_count: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "type": "notebook_update",
            "update_type": self.update_type,
            "cell_id": self.cell_id,
            "cell_index": self.cell_index,
            "content": self.content,
            "cell_type": self.cell_type,
            "outputs": self.outputs,
            "execution_count": self.execution_count,
        }


class NotebookBroadcaster:
    """
    Manages WebSocket connections and broadcasts notebook updates.

    Usage:
        broadcaster = get_notebook_broadcaster()

        # In WebSocket endpoint:
        await broadcaster.connect(websocket, project_id)

        # In internal API routes (after saving to S3):
        await broadcaster.broadcast_update(project_id, NotebookUpdate(...))
    """

    def __init__(self):
        # Map project_id -> set of connected WebSockets
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, project_id: str):
        """Add a WebSocket connection for a project"""
        async with self._lock:
            if project_id not in self._connections:
                self._connections[project_id] = set()
            self._connections[project_id].add(websocket)
            logger.info(f"Notebook WS connected: project={project_id}, total={len(self._connections[project_id])}")

    async def disconnect(self, websocket: WebSocket, project_id: str):
        """Remove a WebSocket connection"""
        async with self._lock:
            if project_id in self._connections:
                self._connections[project_id].discard(websocket)
                if not self._connections[project_id]:
                    del self._connections[project_id]
                logger.info(f"Notebook WS disconnected: project={project_id}")

    async def broadcast_update(self, project_id: str, update: NotebookUpdate):
        """Broadcast an update to all connected clients for a project"""
        async with self._lock:
            connections = self._connections.get(project_id, set()).copy()

        if not connections:
            logger.debug(f"No WS clients for project {project_id}, skipping broadcast")
            return

        message = update.to_dict()
        logger.info(f"Broadcasting {update.update_type} for cell {update.cell_id} to {len(connections)} clients")

        # Send to all connected clients
        disconnected = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WS client: {e}")
                disconnected.append(ws)

        # Clean up disconnected clients
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    if project_id in self._connections:
                        self._connections[project_id].discard(ws)

    def get_connection_count(self, project_id: str) -> int:
        """Get number of connected clients for a project"""
        return len(self._connections.get(project_id, set()))


# Global singleton
_broadcaster: Optional[NotebookBroadcaster] = None


def get_notebook_broadcaster() -> NotebookBroadcaster:
    """Get the global notebook broadcaster instance"""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = NotebookBroadcaster()
    return _broadcaster
