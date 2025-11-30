"""
Playground Pydantic schemas.
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

from .models import PlaygroundStatus


class PlaygroundCreate(BaseModel):
    """Schema for creating a playground (internal use)."""
    project_id: str
    container_id: str
    container_name: str
    internal_url: str
    internal_secret: str
    memory_limit_mb: int = 2048
    cpu_limit: float = 1.0


class PlaygroundResponse(BaseModel):
    """Schema for playground response."""
    id: str
    project_id: str
    container_name: str
    status: PlaygroundStatus
    error_message: Optional[str]
    memory_limit_mb: int
    cpu_limit: float
    started_at: datetime
    last_activity_at: datetime
    stopped_at: Optional[datetime]

    # URL for client to connect (proxied through nginx)
    url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PlaygroundStartResponse(BaseModel):
    """Response when starting a playground."""
    playground: PlaygroundResponse
    message: str = "Playground started successfully"


class PlaygroundStopResponse(BaseModel):
    """Response when stopping a playground."""
    message: str = "Playground stopped successfully"
