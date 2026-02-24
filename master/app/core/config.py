"""
Application configuration using Pydantic Settings.
Loads from environment variables with .env file support.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
from functools import lru_cache
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "AI Notebook Platform"
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="APP_DEBUG")  # Default to False for security

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

    # Google OAuth
    google_client_id: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    oauth_redirect_base_url: str = Field(default="http://localhost:8001", alias="OAUTH_REDIRECT_BASE_URL")

    # Optional LLM settings for playground containers
    # If set in env, passed to playground; otherwise playground uses its own defaults
    default_llm_provider: Optional[str] = Field(default=None, alias="DEFAULT_LLM_PROVIDER")
    default_tool_mode: Optional[str] = Field(default=None, alias="DEFAULT_TOOL_MODE")
    default_context_format: Optional[str] = Field(default=None, alias="DEFAULT_CONTEXT_FORMAT")
    ai_cell_streaming_enabled: Optional[str] = Field(default=None, alias="AI_CELL_STREAMING_ENABLED")

    # Playground settings
    playground_image: str = Field(default="ainotebook-playground:latest", alias="PLAYGROUND_IMAGE")
    playground_network: str = Field(default="ainotebook-network", alias="PLAYGROUND_NETWORK")
    playground_memory_limit: str = Field(default="4g", alias="PLAYGROUND_MEMORY_LIMIT")
    playground_cpu_limit: float = Field(default=4.0, alias="PLAYGROUND_CPU_LIMIT")
    playground_idle_timeout: int = Field(default=3600, alias="PLAYGROUND_IDLE_TIMEOUT")
    master_api_url: str = Field(default="http://ainotebook-master-api:8001/api", alias="MASTER_API_URL")

    # Invite system
    require_invite_code: bool = Field(default=False, alias="REQUIRE_INVITE_CODE")

    # SMTP (for invitation emails)
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", alias="SMTP_FROM")
    smtp_tls: bool = Field(default=True, alias="SMTP_TLS")

    # Encryption key for user API keys (Fernet)
    encryption_key: Optional[str] = Field(default=None, alias="ENCRYPTION_KEY")

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

    @model_validator(mode='after')
    def validate_production_settings(self) -> 'Settings':
        """Validate critical settings in production environment."""
        if self.app_env == "production":
            # JWT secret must be explicitly set in production
            default_secret = "dev_secret_key_change_in_production_must_be_32_chars"
            if self.jwt_secret == default_secret:
                raise ValueError(
                    "JWT_SECRET must be set to a secure value in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            # Ensure debug is off in production
            if self.debug:
                raise ValueError("APP_DEBUG must be False in production")
        return self

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
