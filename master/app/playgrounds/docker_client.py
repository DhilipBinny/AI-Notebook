"""
Docker client for managing playground containers.
"""

import docker
from docker.errors import NotFound, APIError
from typing import Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class DockerClient:
    """Client for managing Docker containers."""

    def __init__(self):
        self.client = docker.from_env()

    def cleanup_container_by_name(self, container_name: str) -> None:
        """
        Remove any existing container with the given name.
        Handles stale/orphaned containers that Docker may not show in 'docker ps'.

        Args:
            container_name: Container name to cleanup
        """
        try:
            container = self.client.containers.get(container_name)
            logger.info(f"Found existing container {container_name} (status: {container.status}), removing...")
            container.remove(force=True)
            logger.info(f"Removed stale container {container_name}")
        except NotFound:
            # No existing container, that's fine
            pass
        except APIError as e:
            logger.warning(f"Error cleaning up container {container_name}: {e}")
            # Try force removal via low-level API
            try:
                self.client.api.remove_container(container_name, force=True)
                logger.info(f"Force removed container {container_name} via API")
            except Exception as inner_e:
                logger.error(
                    f"Failed to force-remove container {container_name}: {inner_e}. "
                    f"Container may be orphaned — manual cleanup required."
                )

    def create_container(
        self,
        container_name: str,
        project_id: str,
        internal_secret: str,
        image: Optional[str] = None,
        memory_limit: Optional[str] = None,
        cpu_limit: Optional[float] = None,
        network: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Create and start a new playground container.

        SECURITY: API keys, model configs, and S3 credentials are NOT passed as
        environment variables. Users can run os.environ in notebooks, so all
        sensitive credentials are injected exclusively via per-request HTTP headers
        by the master API (see chat/routes.py _build_proxy_headers). All S3/file
        operations go through master API endpoints — containers never touch S3 directly.

        Args:
            container_name: Unique container name
            project_id: Project ID
            internal_secret: Secret for internal auth

        Returns:
            Tuple of (container_id, container_ip)
        """
        try:
            # Always cleanup any existing container with this name first
            self.cleanup_container_by_name(container_name)
            # Build environment — infrastructure only, NO API keys or S3 credentials
            env = {
                "PROJECT_ID": project_id,
                "INTERNAL_SECRET": internal_secret,
                # Master API URL for LLM tools to fetch notebook data
                "MASTER_API_URL": settings.master_api_url,
            }

            # Add optional LLM settings if configured in master env
            # If not set, playground container uses its own defaults
            if settings.default_llm_provider:
                env["LLM_PROVIDER"] = settings.default_llm_provider
            if settings.default_tool_mode:
                env["TOOL_EXECUTION_MODE"] = settings.default_tool_mode
            if settings.default_context_format:
                env["CONTEXT_FORMAT"] = settings.default_context_format
            if settings.ai_cell_streaming_enabled:
                env["AI_CELL_STREAMING_ENABLED"] = settings.ai_cell_streaming_enabled

            # Use provided values (from container_types DB) or fall back to env var settings
            actual_image = image or settings.playground_image
            actual_memory = memory_limit or settings.playground_memory_limit
            actual_cpu = cpu_limit if cpu_limit is not None else settings.playground_cpu_limit
            actual_network = network or settings.playground_network

            container = self.client.containers.run(
                image=actual_image,
                name=container_name,
                detach=True,
                environment=env,
                mem_limit=actual_memory,
                cpu_quota=int(actual_cpu * 100000),
                network=actual_network,
                labels={
                    "app": "ainotebook-playground",
                    "project_id": project_id,  # Active project at creation
                },
                restart_policy={"Name": "unless-stopped"},
            )

            # Get container IP for host connectivity
            container.reload()
            networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
            container_ip = None
            for net_name, net_info in networks.items():
                if net_info.get("IPAddress"):
                    container_ip = net_info["IPAddress"]
                    break

            logger.info(f"Created container {container_name} with ID {container.id}, IP {container_ip}")
            return container.id, container_ip

        except APIError as e:
            logger.error(f"Failed to create container: {e}")
            raise RuntimeError(f"Failed to create playground: {e}")

    def stop_container(self, container_id: str, timeout: int = 10) -> None:
        """
        Stop a container.

        Args:
            container_id: Container ID or name
            timeout: Seconds to wait before killing
        """
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info(f"Stopped container {container_id}")
        except NotFound:
            logger.warning(f"Container {container_id} not found")
        except APIError as e:
            logger.error(f"Failed to stop container: {e}")
            raise RuntimeError(f"Failed to stop playground: {e}")

    def remove_container(self, container_id: str, force: bool = False) -> None:
        """
        Remove a container.

        Args:
            container_id: Container ID or name
            force: Force removal of running container
        """
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=force)
            logger.info(f"Removed container {container_id}")
        except NotFound:
            logger.warning(f"Container {container_id} not found")
        except APIError as e:
            logger.error(f"Failed to remove container: {e}")
            raise RuntimeError(f"Failed to remove playground: {e}")

    def get_container_status(self, container_id: str) -> Optional[str]:
        """
        Get container status.

        Args:
            container_id: Container ID or name

        Returns:
            Status string or None if not found
        """
        try:
            container = self.client.containers.get(container_id)
            return container.status
        except NotFound:
            return None
        except APIError as e:
            logger.error(f"Failed to get container status: {e}")
            return None

    def is_container_healthy(self, container_id: str) -> bool:
        """
        Check if container is running and healthy.

        Args:
            container_id: Container ID or name

        Returns:
            True if healthy, False otherwise
        """
        status = self.get_container_status(container_id)
        return status == "running"

    def get_container_logs(
        self,
        container_id: str,
        tail: int = 100,
        since: Optional[int] = None,
    ) -> str:
        """
        Get container logs.

        Args:
            container_id: Container ID or name
            tail: Number of lines from end
            since: Unix timestamp to start from

        Returns:
            Log output string
        """
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, since=since)
            return logs.decode("utf-8")
        except NotFound:
            return ""
        except APIError as e:
            logger.error(f"Failed to get container logs: {e}")
            return ""

    def list_playground_containers(self) -> list:
        """
        List all playground containers.

        Returns:
            List of container info dicts
        """
        try:
            containers = self.client.containers.list(
                all=True,
                filters={"label": "app=ainotebook-playground"},
            )

            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "status": c.status,
                    "project_id": c.labels.get("project_id"),
                }
                for c in containers
            ]
        except APIError as e:
            logger.error(f"Failed to list containers: {e}")
            return []


# Singleton instance
docker_client = DockerClient()
