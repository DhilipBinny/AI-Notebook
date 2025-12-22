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
            except Exception:
                pass

    def create_container(
        self,
        container_name: str,
        project_id: str,
        storage_path: str,
        internal_secret: str,
    ) -> tuple[str, str]:
        """
        Create and start a new playground container.

        Args:
            container_name: Unique container name
            project_id: Project ID
            storage_path: S3 path to notebook
            internal_secret: Secret for internal auth

        Returns:
            Tuple of (container_id, container_ip)
        """
        try:
            # Always cleanup any existing container with this name first
            self.cleanup_container_by_name(container_name)
            # Build environment with LLM API keys
            env = {
                "PROJECT_ID": project_id,
                "INTERNAL_SECRET": internal_secret,
                "S3_NOTEBOOK_PATH": storage_path,
                "S3_ENDPOINT": settings.s3_endpoint,
                "S3_ACCESS_KEY": settings.s3_access_key,
                "S3_SECRET_KEY": settings.s3_secret_key,
                "S3_BUCKET": settings.s3_bucket_notebooks,
                # Master API URL for LLM tools to fetch notebook data
                "MASTER_API_URL": settings.master_api_url,
            }
            # Add LLM API keys if configured (passed as env vars, not via .env file)
            if settings.gemini_api_key:
                env["GEMINI_API_KEY"] = settings.gemini_api_key
            if settings.openai_api_key:
                env["OPENAI_API_KEY"] = settings.openai_api_key
            if settings.anthropic_api_key:
                env["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

            # OpenRouter configuration for OpenAI
            if settings.use_openrouter:
                env["USE_OPENROUTER"] = "true"
            if settings.openrouter_api_key:
                env["OPENROUTER_API_KEY"] = settings.openrouter_api_key
            if settings.openrouter_openai_url:
                env["OPENROUTER_OPENAI_URL"] = settings.openrouter_openai_url
            if settings.openrouter_openai_model:
                env["OPENROUTER_OPENAI_MODEL"] = settings.openrouter_openai_model
            if settings.openrouter_max_tokens:
                env["OPENROUTER_MAX_TOKENS"] = str(settings.openrouter_max_tokens)

            # Add LLM model configurations
            if settings.gemini_model:
                env["GEMINI_MODEL"] = settings.gemini_model
            if settings.openai_model:
                env["OPENAI_MODEL"] = settings.openai_model
            if settings.anthropic_model:
                env["ANTHROPIC_MODEL"] = settings.anthropic_model

            # Add Ollama configuration
            if settings.ollama_url:
                env["OLLAMA_URL"] = settings.ollama_url
            if settings.ollama_model:
                env["OLLAMA_MODEL"] = settings.ollama_model

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

            container = self.client.containers.run(
                image=settings.playground_image,
                name=container_name,
                detach=True,
                environment=env,
                mem_limit=settings.playground_memory_limit,
                cpu_quota=int(settings.playground_cpu_limit * 100000),
                network=settings.playground_network,
                labels={
                    "app": "ainotebook-playground",
                    "project_id": project_id,
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
