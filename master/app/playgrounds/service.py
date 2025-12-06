"""
Playground service - manages container lifecycle.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional
from datetime import datetime, timezone
from uuid import uuid4
import asyncio
import httpx
import logging

from .models import Playground, PlaygroundStatus
from .docker_client import docker_client
from app.projects.models import Project
from app.core.config import settings

logger = logging.getLogger(__name__)


class PlaygroundService:
    """Service class for playground operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_project_id(self, project_id: str) -> Optional[Playground]:
        """Get playground for a project."""
        result = await self.db.execute(
            select(Playground).where(Playground.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def start(self, project: Project) -> Playground:
        """
        Start a new playground for a project.

        Args:
            project: Project to start playground for

        Returns:
            Playground instance

        Raises:
            ValueError: If playground already running
            RuntimeError: If container creation fails
        """
        # Check if already running
        existing = await self.get_by_project_id(project.id)
        if existing and existing.status == PlaygroundStatus.RUNNING:
            raise ValueError("Playground already running")

        # Clean up any stopped playground
        if existing:
            await self._cleanup_playground(existing)

        # Generate container info
        short_id = project.id[:8]
        container_name = f"playground-{short_id}"
        internal_secret = str(uuid4())

        # Create database record first (URL will be updated after container creation)
        playground = Playground(
            project_id=project.id,
            container_id="pending",
            container_name=container_name,
            internal_url="pending",
            internal_secret=internal_secret,
            status=PlaygroundStatus.STARTING,
            memory_limit_mb=2048,
            cpu_limit=settings.playground_cpu_limit,
        )

        self.db.add(playground)
        await self.db.flush()

        try:
            # Create Docker container
            container_id, container_ip = docker_client.create_container(
                container_name=container_name,
                project_id=project.id,
                storage_path=project.storage_path,
                internal_secret=internal_secret,
            )

            # Update with actual container ID and URL (use IP for host connectivity)
            playground.container_id = container_id
            internal_url = f"http://{container_ip}:8888"
            playground.internal_url = internal_url

            # Wait for container to be ready
            is_ready = await self._wait_for_ready(internal_url, timeout=60)

            if is_ready:
                playground.status = PlaygroundStatus.RUNNING
            else:
                playground.status = PlaygroundStatus.ERROR
                playground.error_message = "Container failed to start within timeout"

            await self.db.flush()
            # Refresh to get server-generated timestamps
            await self.db.refresh(playground)

        except Exception as e:
            logger.error(f"Failed to start playground: {e}")
            playground.status = PlaygroundStatus.ERROR
            playground.error_message = str(e)
            await self.db.flush()
            raise RuntimeError(f"Failed to start playground: {e}")

        return playground

    async def stop(self, playground: Playground) -> None:
        """
        Stop a running playground.

        Args:
            playground: Playground to stop
        """
        if playground.status not in [PlaygroundStatus.RUNNING, PlaygroundStatus.STARTING]:
            return

        playground.status = PlaygroundStatus.STOPPING
        await self.db.flush()

        try:
            docker_client.stop_container(playground.container_id)
            docker_client.remove_container(playground.container_id)
        except Exception as e:
            logger.error(f"Error stopping container: {e}")

        playground.status = PlaygroundStatus.STOPPED
        playground.stopped_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def update_activity(self, playground: Playground) -> None:
        """Update last activity timestamp."""
        playground.last_activity_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def get_status(self, playground: Playground) -> dict:
        """
        Get playground status including container health.

        Args:
            playground: Playground to check

        Returns:
            Status dict
        """
        # Check actual container status
        container_status = docker_client.get_container_status(playground.container_id)

        # Sync database status if needed
        if container_status is None and playground.status == PlaygroundStatus.RUNNING:
            playground.status = PlaygroundStatus.STOPPED
            playground.stopped_at = datetime.now(timezone.utc)
            await self.db.flush()

        return {
            "id": playground.id,
            "project_id": playground.project_id,
            "status": playground.status.value,
            "container_status": container_status,
            "started_at": playground.started_at.isoformat(),
            "last_activity_at": playground.last_activity_at.isoformat(),
            "url": f"/playground/{playground.container_name}" if playground.status == PlaygroundStatus.RUNNING else None,
        }

    async def get_logs(self, playground: Playground, tail: int = 100) -> str:
        """Get container logs."""
        return docker_client.get_container_logs(playground.container_id, tail=tail)

    async def cleanup_stale_playgrounds(self, idle_timeout: int = None) -> int:
        """
        Stop playgrounds that have been idle too long.

        Args:
            idle_timeout: Seconds of idle time before cleanup (default from settings)

        Returns:
            Number of playgrounds cleaned up
        """
        if idle_timeout is None:
            idle_timeout = settings.playground_idle_timeout

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=idle_timeout)

        result = await self.db.execute(
            select(Playground).where(
                Playground.status == PlaygroundStatus.RUNNING,
                Playground.last_activity_at < cutoff,
            )
        )
        stale = result.scalars().all()

        count = 0
        for playground in stale:
            try:
                await self.stop(playground)
                count += 1
            except Exception as e:
                logger.error(f"Failed to cleanup playground {playground.id}: {e}")

        return count

    async def _wait_for_ready(self, url: str, timeout: int = 60) -> bool:
        """
        Wait for playground to be ready.

        Args:
            url: Internal URL to health check
            timeout: Seconds to wait

        Returns:
            True if ready, False if timeout
        """
        health_url = f"{url}/health"
        start_time = asyncio.get_event_loop().time()

        async with httpx.AsyncClient() as client:
            while asyncio.get_event_loop().time() - start_time < timeout:
                try:
                    response = await client.get(health_url, timeout=5)
                    if response.status_code == 200:
                        return True
                except Exception:
                    pass

                await asyncio.sleep(1)

        return False

    async def _cleanup_playground(self, playground: Playground) -> None:
        """Remove a playground record and container."""
        try:
            docker_client.stop_container(playground.container_id)
            docker_client.remove_container(playground.container_id, force=True)
        except Exception as e:
            # Log container cleanup failures for debugging orphaned containers
            logger.warning(
                f"Failed to cleanup container {playground.container_id} "
                f"for project {playground.project_id}: {e}"
            )

        self.db.delete(playground)  # delete() is sync, marks for deletion
        await self.db.flush()


# Import here to avoid circular imports
from datetime import timedelta
