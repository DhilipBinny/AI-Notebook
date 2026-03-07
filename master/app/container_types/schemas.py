"""
Container type Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class ContainerTypeCreate(BaseModel):
    """Schema for creating a new container type."""
    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    image: str = Field(..., min_length=1, max_length=255)
    network: str = Field(default="ainotebook-network", max_length=100)
    memory_limit: str = Field(default="4g", max_length=20)
    cpu_limit: float = Field(default=4.0, ge=0.25, le=64.0)
    idle_timeout: int = Field(default=3600, ge=60, le=86400)
    is_active: bool = True


class ContainerTypeUpdate(BaseModel):
    """Schema for updating a container type."""
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    image: Optional[str] = Field(None, min_length=1, max_length=255)
    network: Optional[str] = Field(None, max_length=100)
    memory_limit: Optional[str] = Field(None, max_length=20)
    cpu_limit: Optional[float] = Field(None, ge=0.25, le=64.0)
    idle_timeout: Optional[int] = Field(None, ge=60, le=86400)
    is_active: Optional[bool] = None


class ContainerTypeResponse(BaseModel):
    """Schema for container type API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    label: str
    description: Optional[str] = None
    image: str
    network: str
    memory_limit: str
    cpu_limit: float
    idle_timeout: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
