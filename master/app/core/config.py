"""
Application configuration using Pydantic Settings.
Loads from environment variables with .env file support.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "AI Notebook Platform"
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="APP_DEBUG")

    # Database
    database_url: str = Field(
        default="mysql+aiomysql://root:ainotebook_dev_2024@localhost:3307/ainotebook",
        alias="DATABASE_URL"
    )

    # S3/MinIO
    s3_endpoint: str = Field(default="http://localhost:9000", alias="S3_ENDPOINT")
    s3_access_key: str = Field(default="minioadmin", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="minioadmin123", alias="S3_SECRET_KEY")
    s3_bucket_notebooks: str = Field(default="notebooks", alias="S3_BUCKET_NOTEBOOKS")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")

    # JWT Authentication
    jwt_secret: str = Field(
        default="dev_secret_key_change_in_production_must_be_32_chars",
        alias="JWT_SECRET"
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=30, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=7, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS")

    # OAuth (optional)
    google_client_id: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    github_client_id: Optional[str] = Field(default=None, alias="GITHUB_CLIENT_ID")
    github_client_secret: Optional[str] = Field(default=None, alias="GITHUB_CLIENT_SECRET")

    # LLM API Keys (passed to playground containers as environment variables)
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")

    # Ollama Configuration (passed to playground containers)
    ollama_url: Optional[str] = Field(default="http://host.docker.internal:11434/v1", alias="OLLAMA_URL")
    ollama_model: Optional[str] = Field(default="qwen3-coder:30b", alias="OLLAMA_MODEL")

    # Playground settings
    playground_image: str = Field(default="ainotebook-playground:latest", alias="PLAYGROUND_IMAGE")
    playground_network: str = Field(default="ainotebook-network", alias="PLAYGROUND_NETWORK")
    playground_memory_limit: str = Field(default="4g", alias="PLAYGROUND_MEMORY_LIMIT")
    playground_cpu_limit: float = Field(default=4.0, alias="PLAYGROUND_CPU_LIMIT")
    playground_idle_timeout: int = Field(default=3600, alias="PLAYGROUND_IDLE_TIMEOUT")

    # User limits
    default_max_projects: int = Field(default=5, alias="DEFAULT_MAX_PROJECTS")

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        alias="CORS_ORIGINS"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
