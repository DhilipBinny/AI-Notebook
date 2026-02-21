"""
AI Notebook Platform - Master API
Main FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
import logging
import asyncio

from app.core.config import settings
from app.db.session import engine, AsyncSessionLocal
from app.db.base import Base

# Import all models to ensure they're registered with SQLAlchemy
from app.users.models import User
from app.projects.models import Project
from app.workspaces.models import Workspace
from app.playgrounds.models import Playground
from app.auth.models import Session
from app.invitations.models import Invitation, InvitationUse
from app.api_keys.models import UserApiKey
from app.credits.models import UserCredit, LLMPricing, UsageRecord
from app.templates.models import NotebookTemplate
# Note: ChatMessage model removed - chat history is stored in S3/MinIO as JSON

# Import routers
from app.auth.routes import router as auth_router
from app.auth.oauth import router as oauth_router
from app.users.routes import router as users_router
from app.projects.routes import router as projects_router
from app.workspaces.routes import router as workspaces_router
from app.playgrounds.routes import router as playgrounds_router
from app.chat.routes import router as chat_router
from app.notebooks.routes import router as notebooks_router
from app.internal.routes import router as internal_router
from app.files.routes import router as files_router
from app.invitations.routes import router as invitations_router
from app.api_keys.routes import router as api_keys_router
from app.credits.routes import router as credits_router
from app.templates.routes import router as templates_router

# Import playground service for cleanup
from app.playgrounds.service import PlaygroundService

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def cleanup_idle_playgrounds_task():
    """
    Background task that periodically cleans up idle playgrounds.
    Runs every 5 minutes and stops containers that have been idle
    longer than the configured timeout.
    """
    cleanup_interval = 5 * 60  # 5 minutes

    logger.info(f"Starting idle playground cleanup task (interval: {cleanup_interval}s, timeout: {settings.playground_idle_timeout}s)")

    while True:
        try:
            await asyncio.sleep(cleanup_interval)

            # Create a new database session for this cleanup run
            async with AsyncSessionLocal() as db:
                playground_service = PlaygroundService(db)
                cleaned_count = await playground_service.cleanup_stale_playgrounds()

                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} idle playground(s)")
                    await db.commit()

        except asyncio.CancelledError:
            logger.info("Idle playground cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in idle playground cleanup task: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs on startup and shutdown.
    """
    # Startup
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug mode: {settings.debug}")

    # Create tables if they don't exist (development only)
    if settings.debug:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified")

    # Start background cleanup task
    cleanup_task = asyncio.create_task(cleanup_idle_playgrounds_task())

    yield

    # Shutdown
    logger.info("Shutting down application")

    # Cancel cleanup task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    await engine.dispose()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Multi-tenant Jupyter Notebook platform with LLM capabilities",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add Session middleware (required for OAuth state management)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.jwt_secret,
    max_age=3600,  # 1 hour session for OAuth flow
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(oauth_router, prefix="/api")  # Google OAuth routes
app.include_router(users_router, prefix="/api")
app.include_router(projects_router, prefix="/api")
app.include_router(workspaces_router, prefix="/api")
app.include_router(playgrounds_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(notebooks_router, prefix="/api")
app.include_router(files_router, prefix="/api")  # File management endpoints
app.include_router(internal_router, prefix="/api")  # Internal endpoints for playground
app.include_router(invitations_router, prefix="/api")  # Admin invitation management
app.include_router(api_keys_router, prefix="/api")  # User API key management
app.include_router(credits_router, prefix="/api")  # Credits and usage tracking
app.include_router(templates_router, prefix="/api")  # Notebook templates


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "env": settings.app_env,
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs" if settings.debug else None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
