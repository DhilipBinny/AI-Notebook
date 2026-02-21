"""
Playground service - manages container lifecycle.
One container per user model.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
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
from app.platform_keys.service import PlatformKeyService

logger = logging.getLogger(__name__)


class PlaygroundService:
    """Service class for playground operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: str) -> Optional[Playground]:
        """Get playground for a user."""
        result = await self.db.execute(
            select(Playground).where(Playground.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_project_id(self, project_id: str) -> Optional[Playground]:
        """Get playground by active project ID (legacy compatibility)."""
        result = await self.db.execute(
            select(Playground).where(Playground.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def start(self, user: User, project: Project) -> Playground:
        """
        Start a playground for a user with a specific project.

        If a playground already exists for the user, reuses it.
        If it's running with a different project, switches project.

        Args:
            user: User requesting the playground
            project: Project to load

        Returns:
            Playground instance

        Raises:
            RuntimeError: If container creation fails
        """
        existing = await self.get_by_user_id(user.id)

        # If running with same project, just return it
        if existing and existing.status == PlaygroundStatus.RUNNING and existing.project_id == project.id:
            return existing

        # If running with different project, switch
        if existing and existing.status == PlaygroundStatus.RUNNING:
            await self.switch_project(existing, project)
            return existing

        # Clean up any stopped/error playground
        if existing:
            await self._cleanup_playground(existing)
            await self.db.commit()

        # Generate container info — named by user, not project
        short_id = user.id[:8]
        container_name = f"playground-{short_id}"
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
            memory_limit_mb=2048,
            cpu_limit=settings.playground_cpu_limit,
        )

        self.db.add(playground)
        await self.db.flush()

        try:
            # Fetch platform API keys from DB for container env
            pk_service = PlatformKeyService(self.db)
            platform_keys = await pk_service.get_all_active_keys()
            platform_models = await pk_service.get_active_models()
            platform_base_urls = await pk_service.get_active_base_urls()

            # Create Docker container
            container_id, container_ip = docker_client.create_container(
                container_name=container_name,
                project_id=project.id,
                storage_path=project.storage_path,
                internal_secret=internal_secret,
                platform_keys=platform_keys,
                platform_models=platform_models,
                platform_base_urls=platform_base_urls,
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

    async def switch_project(self, playground: Playground, project: Project) -> None:
        """
        Switch the active project in a running playground.

        1. Save current workspace to S3
        2. Restart kernel (clean state)
        3. Update active project
        4. Restore new project's workspace from S3

        Args:
            playground: Running playground
            project: New project to switch to
        """
        if playground.status != PlaygroundStatus.RUNNING:
            raise ValueError("Playground is not running")

        if playground.project_id == project.id:
            return  # Already on this project

        logger.info(f"Switching playground {playground.container_name} from project {playground.project_id} to {project.id}")

        # 1. Save current workspace files to S3
        if playground.project_id:
            try:
                old_project = await self.db.get(Project, playground.project_id)
                if old_project:
                    await self._save_workspace_files(
                        playground.container_name,
                        old_project.storage_month,
                        old_project.id,
                    )
            except Exception as e:
                logger.warning(f"Failed to save workspace before switch: {e}")

        # 2. Restart kernel via playground API (clean state)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{playground.internal_url}/kernel/restart",
                    headers={"X-Internal-Secret": playground.internal_secret},
                    timeout=30,
                )
                if resp.status_code != 200:
                    logger.warning(f"Kernel restart returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"Failed to restart kernel during switch: {e}")

        # 3. Update active project
        playground.project_id = project.id
        await self.db.flush()

        # 4. Restore new project's workspace
        try:
            await self._restore_workspace_files(
                playground.container_name,
                project.storage_month,
                project.id,
            )
        except Exception as e:
            logger.warning(f"Failed to restore workspace after switch: {e}")

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
