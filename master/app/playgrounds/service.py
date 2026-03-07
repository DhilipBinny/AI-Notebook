"""
Playground service - manages container lifecycle.
Multiple containers per user (up to max_containers), one per project.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sql_func
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import asyncio
import httpx
import logging

from .models import Playground, PlaygroundStatus
from .docker_client import docker_client
from app.projects.models import Project
from app.users.models import User
from app.core.config import settings
from app.container_types.models import ContainerType

logger = logging.getLogger(__name__)


class PlaygroundService:
    """Service class for playground operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: str) -> List[Playground]:
        """Get all playgrounds for a user."""
        result = await self.db.execute(
            select(Playground).where(Playground.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_running_by_user_id(self, user_id: str) -> List[Playground]:
        """Get all running playgrounds for a user."""
        result = await self.db.execute(
            select(Playground).where(
                Playground.user_id == user_id,
                Playground.status == PlaygroundStatus.RUNNING,
            )
        )
        return list(result.scalars().all())

    async def get_running_count(self, user_id: str) -> int:
        """Get count of running/starting playgrounds for a user."""
        result = await self.db.execute(
            select(sql_func.count(Playground.id)).where(
                Playground.user_id == user_id,
                Playground.status.in_([PlaygroundStatus.RUNNING, PlaygroundStatus.STARTING]),
            )
        )
        return result.scalar() or 0

    async def get_by_user_and_project(self, user_id: str, project_id: str) -> Optional[Playground]:
        """Get playground for a specific user and project."""
        result = await self.db.execute(
            select(Playground).where(
                Playground.user_id == user_id,
                Playground.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _parse_memory_mb(mem_str: str) -> int:
        """Convert memory string like '4g', '512m' to MB."""
        mem_str = mem_str.strip().lower()
        if mem_str.endswith('g'):
            return int(float(mem_str[:-1]) * 1024)
        if mem_str.endswith('m'):
            return int(float(mem_str[:-1]))
        logger.warning(f"Unrecognized memory format '{mem_str}', defaulting to 2048 MB")
        return 2048

    async def _get_container_config(self) -> Optional[ContainerType]:
        """
        Get the playground container type config from DB.
        Raises RuntimeError if the type exists but is disabled by admin.
        Returns None if no DB row exists (falls back to env vars).
        """
        result = await self.db.execute(
            select(ContainerType).where(ContainerType.name == "playground")
        )
        ct = result.scalar_one_or_none()
        if ct and not ct.is_active:
            raise ValueError("Playground containers are currently disabled by admin")
        return ct

    async def get_by_project_id(self, project_id: str) -> Optional[Playground]:
        """Get playground by project ID."""
        result = await self.db.execute(
            select(Playground).where(Playground.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def start(self, user: User, project: Project) -> Playground:
        """
        Start a playground for a user with a specific project.

        - If a playground already exists and is running for this project, return it.
        - If user is at their container limit, raise ValueError.
        - Otherwise, create a new container.

        Args:
            user: User requesting the playground
            project: Project to load

        Returns:
            Playground instance

        Raises:
            ValueError: If container limit reached or containers disabled
            RuntimeError: If container creation fails
        """
        # Check for existing playground for this user+project
        existing = await self.get_by_user_and_project(user.id, project.id)

        # If running for this project, just return it
        if existing and existing.status == PlaygroundStatus.RUNNING:
            existing.last_activity_at = datetime.now(timezone.utc)
            await self.db.flush()
            return existing

        # Clean up any stopped/error playground for this project
        if existing:
            await self._cleanup_playground(existing)
            await self.db.commit()

        # Check container limit
        running_count = await self.get_running_count(user.id)
        if running_count >= user.max_containers:
            raise ValueError(
                f"Container limit reached ({running_count}/{user.max_containers}). "
                f"Stop an existing container before starting a new one."
            )

        # Load container type config from DB (falls back to env var settings)
        ct_config = await self._get_container_config()

        # Generate container info — named by user + project
        short_user = user.id[:8]
        short_project = project.id[:8]
        container_name = f"playground-{short_user}-{short_project}"
        internal_secret = str(uuid4())

        # Create database record
        playground = Playground(
            user_id=user.id,
            project_id=project.id,
            container_id="pending",
            container_name=container_name,
            internal_url="pending",
            internal_secret=internal_secret,
            status=PlaygroundStatus.STARTING,
            memory_limit_mb=self._parse_memory_mb(ct_config.memory_limit if ct_config else settings.playground_memory_limit),
            cpu_limit=float(ct_config.cpu_limit) if ct_config else settings.playground_cpu_limit,
        )

        self.db.add(playground)
        await self.db.flush()

        try:
            # Create Docker container
            container_id, container_ip = docker_client.create_container(
                container_name=container_name,
                project_id=project.id,
                internal_secret=internal_secret,
                image=ct_config.image if ct_config else None,
                memory_limit=ct_config.memory_limit if ct_config else None,
                cpu_limit=float(ct_config.cpu_limit) if ct_config else None,
                network=ct_config.network if ct_config else None,
            )

            playground.container_id = container_id
            internal_url = f"http://{container_ip}:8888"
            playground.internal_url = internal_url

            # Wait for container to be ready
            is_ready = await self._wait_for_ready(internal_url, timeout=60)

            if is_ready:
                playground.status = PlaygroundStatus.RUNNING

                # Auto-restore workspace files from S3
                try:
                    await self._restore_workspace_files(
                        container_name,
                        project.storage_month,
                        project.id,
                    )
                except Exception as e:
                    logger.warning(f"Failed to restore workspace files: {e}")
            else:
                playground.status = PlaygroundStatus.ERROR
                playground.error_message = "Container failed to start within timeout"

            await self.db.flush()
            await self.db.refresh(playground)

        except Exception as e:
            logger.error(f"Failed to start playground: {e}")
            playground.status = PlaygroundStatus.ERROR
            playground.error_message = str(e)
            await self.db.flush()
            raise RuntimeError(f"Failed to start playground: {e}")

        return playground

    async def stop(self, playground: Playground) -> None:
        """Stop a running playground."""
        if playground.status not in [PlaygroundStatus.RUNNING, PlaygroundStatus.STARTING]:
            return

        playground.status = PlaygroundStatus.STOPPING
        await self.db.flush()

        # Save workspace before stopping
        if playground.project_id:
            try:
                project = await self.db.get(Project, playground.project_id)
                if project:
                    await self._save_workspace_files(
                        playground.container_name,
                        project.storage_month,
                        project.id,
                    )
            except Exception as e:
                logger.warning(f"Failed to save workspace before stop: {e}")

        try:
            docker_client.stop_container(playground.container_id)
            docker_client.remove_container(playground.container_id)
        except Exception as e:
            logger.error(f"Error stopping container: {e}")

        playground.status = PlaygroundStatus.STOPPED
        playground.stopped_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def stop_by_user_and_project(self, user_id: str, project_id: str) -> bool:
        """Stop a specific playground by user and project. Returns True if stopped."""
        playground = await self.get_by_user_and_project(user_id, project_id)
        if playground is None:
            return False
        await self.stop(playground)
        return True

    async def stop_all_for_user(self, user_id: str) -> int:
        """Stop all running playgrounds for a user. Returns count stopped."""
        running = await self.get_running_by_user_id(user_id)
        count = 0
        for playground in running:
            try:
                await self.stop(playground)
                count += 1
            except Exception as e:
                logger.error(f"Failed to stop playground {playground.id}: {e}")
        return count

    async def update_activity(self, playground: Playground) -> None:
        """Update last activity timestamp."""
        playground.last_activity_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def get_status(self, playground: Playground) -> dict:
        """Get playground status including container health."""
        container_status = docker_client.get_container_status(playground.container_id)

        # Sync database status if needed
        if container_status is None and playground.status == PlaygroundStatus.RUNNING:
            playground.status = PlaygroundStatus.STOPPED
            playground.stopped_at = datetime.now(timezone.utc)
            await self.db.flush()

        return {
            "id": playground.id,
            "user_id": playground.user_id,
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
        """Stop playgrounds that have been idle too long."""
        if idle_timeout is None:
            try:
                ct_config = await self._get_container_config()
                idle_timeout = ct_config.idle_timeout if ct_config else settings.playground_idle_timeout
            except ValueError:
                # Type is disabled — still clean up existing containers using fallback
                logger.info("Playground type is disabled, using fallback idle timeout for cleanup")
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
        """Wait for playground to be ready."""
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
        container_removed = False
        try:
            docker_client.stop_container(playground.container_id)
            docker_client.remove_container(playground.container_id, force=True)
            container_removed = True
        except RuntimeError as e:
            if "not found" in str(e).lower():
                container_removed = True
            else:
                logger.error(
                    f"Failed to cleanup container {playground.container_id}: {e}. "
                    f"DB record kept to prevent orphaning."
                )
        except Exception as e:
            logger.error(
                f"Unexpected error cleaning up container {playground.container_id}: {e}. "
                f"DB record kept to prevent orphaning."
            )

        if container_removed:
            await self.db.delete(playground)
            await self.db.flush()
        else:
            playground.status = PlaygroundStatus.ERROR
            playground.error_message = "Container cleanup failed — manual removal required"
            await self.db.flush()

    async def _save_workspace_files(
        self,
        container_name: str,
        storage_month: str,
        project_id: str,
    ) -> None:
        """Save workspace files from container to S3."""
        from app.files.service import file_service

        saved_files, total_size, errors = await file_service.save_to_s3(
            container_name,
            storage_month,
            project_id,
        )

        if saved_files:
            logger.info(
                f"Saved {len(saved_files)} files ({total_size} bytes) "
                f"for project {project_id}"
            )
        if errors:
            logger.warning(f"File save errors for project {project_id}: {errors}")

    async def _restore_workspace_files(
        self,
        container_name: str,
        storage_month: str,
        project_id: str,
    ) -> None:
        """Restore workspace files from S3 to container."""
        from app.files.service import file_service

        restored_files, total_size, errors = await file_service.restore_from_s3(
            container_name,
            storage_month,
            project_id,
        )

        if restored_files:
            logger.info(
                f"Restored {len(restored_files)} files ({total_size} bytes) "
                f"for project {project_id}"
            )
        if errors:
            logger.warning(f"File restore errors for project {project_id}: {errors}")
