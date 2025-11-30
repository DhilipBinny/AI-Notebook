"""
Playground API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_active_user
from app.users.models import User
from app.projects.service import ProjectService
from .service import PlaygroundService
from .schemas import PlaygroundResponse, PlaygroundStartResponse, PlaygroundStopResponse

router = APIRouter(tags=["Playgrounds"])


from typing import Optional

@router.get("/projects/{project_id}/playground", response_model=Optional[PlaygroundResponse])
async def get_playground(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get playground status for a project.

    Returns null if no playground exists.
    Verifies actual container status and syncs database if container is stopped.
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Get playground
    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_project_id(project_id)

    if playground is None:
        return None

    # Verify actual container status if database says it's running
    # This syncs the database if the container was stopped externally
    if playground.status.value == "running":
        await playground_service.get_status(playground)
        await db.commit()  # Commit any status changes

    response = PlaygroundResponse.model_validate(playground)
    if playground.status.value == "running":
        response.url = f"/playground/{playground.container_name}"

    return response


@router.post("/projects/{project_id}/playground/start", response_model=PlaygroundStartResponse)
async def start_playground(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start a playground for a project.

    Creates a new container with isolated Jupyter kernel.
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(
        project_id, current_user.id, include_playground=True
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Start playground
    playground_service = PlaygroundService(db)

    try:
        playground = await playground_service.start(project)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Update project last opened
    await project_service.update_last_opened(project)

    response = PlaygroundResponse.model_validate(playground)
    if playground.status.value == "running":
        response.url = f"/playground/{playground.container_name}"

    return PlaygroundStartResponse(
        playground=response,
        message="Playground started successfully",
    )


@router.post("/projects/{project_id}/playground/stop", response_model=PlaygroundStopResponse)
async def stop_playground(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Stop a running playground.

    Saves notebook state and removes the container.
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Get and stop playground
    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_project_id(project_id)

    if playground is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No playground running",
        )

    await playground_service.stop(playground)

    return PlaygroundStopResponse(message="Playground stopped successfully")


@router.get("/projects/{project_id}/playground/logs")
async def get_playground_logs(
    project_id: str,
    tail: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get container logs for a playground.
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Get playground
    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_project_id(project_id)

    if playground is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No playground found",
        )

    logs = await playground_service.get_logs(playground, tail=tail)

    return {"logs": logs}


@router.post("/projects/{project_id}/playground/activity")
async def update_playground_activity(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update playground activity timestamp.

    Call this periodically to prevent idle timeout.
    """
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Get and update playground
    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_project_id(project_id)

    if playground is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No playground running",
        )

    await playground_service.update_activity(playground)

    return {"message": "Activity updated"}
