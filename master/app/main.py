"""
AI Notebook Platform - Master API
Main FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.db.session import engine
from app.db.base import Base

# Import all models to ensure they're registered with SQLAlchemy
from app.users.models import User
from app.projects.models import Project
from app.playgrounds.models import Playground
from app.auth.models import Session
# Note: ChatMessage model removed - chat history is stored in S3/MinIO as JSON

# Import routers
from app.auth.routes import router as auth_router
from app.users.routes import router as users_router
from app.projects.routes import router as projects_router
from app.playgrounds.routes import router as playgrounds_router
from app.chat.routes import router as chat_router
from app.notebooks.routes import router as notebooks_router
from app.internal.routes import router as internal_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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

    yield

    # Shutdown
    logger.info("Shutting down application")
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
app.include_router(users_router, prefix="/api")
app.include_router(projects_router, prefix="/api")
app.include_router(playgrounds_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(notebooks_router, prefix="/api")
app.include_router(internal_router, prefix="/api")  # Internal endpoints for playground


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
