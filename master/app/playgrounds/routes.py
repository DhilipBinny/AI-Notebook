"""
Playground API routes.
User-scoped with multiple containers per user (up to max_containers), one per project.
"""

import asyncio
import json
import queue
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, AsyncSessionLocal
from app.auth.dependencies import get_current_active_user
from app.auth.jwt import verify_token
from app.users.models import User
from app.projects.service import ProjectService
from .service import PlaygroundService
from .schemas import (
    PlaygroundResponse,
    PlaygroundStartResponse,
    PlaygroundStopRequest,
    PlaygroundStopResponse,
    PlaygroundListResponse,
)
from .docker_client import docker_client

router = APIRouter(tags=["Playgrounds"])


class PlaygroundStartRequest(BaseModel):
    """Request body for starting a playground."""
    project_id: str


# ===== User-Scoped Routes =====

@router.get("/playground", response_model=PlaygroundListResponse)
async def get_user_playgrounds(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all playgrounds for the current user."""
    playground_service = PlaygroundService(db)
    all_playgrounds = await playground_service.get_by_user_id(current_user.id)

    # Sync container status for running ones
    for pg in all_playgrounds:
        if pg.status.value == "running":
            await playground_service.get_status(pg)

    await db.commit()

    responses = []
    for pg in all_playgrounds:
        response = PlaygroundResponse.model_validate(pg)
        if pg.status.value == "running":
            response.url = f"/playground/{pg.container_name}"
        responses.append(response)

    running_count = sum(1 for pg in all_playgrounds if pg.status.value in ("running", "starting"))

    return PlaygroundListResponse(
        playgrounds=responses,
        running_count=running_count,
        max_containers=current_user.max_containers,
    )


@router.post("/playground/start", response_model=PlaygroundStartResponse)
async def start_user_playground(
    request: PlaygroundStartRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a playground for a specific project."""
    # Verify project ownership
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(request.project_id, current_user.id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    playground_service = PlaygroundService(db)

    try:
        playground = await playground_service.start(current_user, project)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Update project last opened
    await project_service.update_last_opened(project)

    response = PlaygroundResponse.model_validate(playground)
    if playground.status.value == "running":
        response.url = f"/playground/{playground.container_name}"

    return PlaygroundStartResponse(playground=response, message="Playground started successfully")


@router.post("/playground/stop", response_model=PlaygroundStopResponse)
async def stop_user_playground(
    request: PlaygroundStopRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop a specific playground by project ID."""
    playground_service = PlaygroundService(db)
    stopped = await playground_service.stop_by_user_and_project(current_user.id, request.project_id)

    if not stopped:
        raise HTTPException(status_code=404, detail="No playground found for this project")

    return PlaygroundStopResponse(message="Playground stopped successfully")


@router.post("/playground/stop-all", response_model=PlaygroundStopResponse)
async def stop_all_user_playgrounds(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop all running playgrounds for the current user."""
    playground_service = PlaygroundService(db)
    count = await playground_service.stop_all_for_user(current_user.id)

    return PlaygroundStopResponse(message=f"Stopped {count} playground(s)")


@router.post("/playground/activity")
async def update_user_playground_activity(
    request: PlaygroundStopRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update playground activity timestamp to prevent idle timeout."""
    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_user_and_project(current_user.id, request.project_id)

    if playground is None:
        raise HTTPException(status_code=404, detail="No playground found for this project")

    await playground_service.update_activity(playground)

    return {"message": "Activity updated"}


@router.get("/playground/logs")
async def get_user_playground_logs(
    project_id: str = Query(...),
    tail: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get container logs for a specific playground."""
    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_user_and_project(current_user.id, project_id)

    if playground is None:
        raise HTTPException(status_code=404, detail="No playground found for this project")

    logs = await playground_service.get_logs(playground, tail=tail)
    return {"logs": logs}


# ===== Legacy Project-Scoped Routes =====

@router.get("/projects/{project_id}/playground", response_model=Optional[PlaygroundResponse])
async def get_playground(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get playground status for a project."""
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_user_and_project(current_user.id, project_id)

    if playground is None:
        return None

    # Sync container status
    if playground.status.value == "running":
        await playground_service.get_status(playground)
        await db.commit()

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
    """Start playground for a project (legacy route)."""
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id, include_playground=True)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    playground_service = PlaygroundService(db)

    try:
        playground = await playground_service.start(current_user, project)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    await project_service.update_last_opened(project)

    response = PlaygroundResponse.model_validate(playground)
    if playground.status.value == "running":
        response.url = f"/playground/{playground.container_name}"

    return PlaygroundStartResponse(playground=response, message="Playground started successfully")


@router.post("/projects/{project_id}/playground/stop", response_model=PlaygroundStopResponse)
async def stop_playground(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop playground for a project (legacy route)."""
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    playground_service = PlaygroundService(db)
    stopped = await playground_service.stop_by_user_and_project(current_user.id, project_id)

    if not stopped:
        raise HTTPException(status_code=404, detail="No playground running for this project")

    return PlaygroundStopResponse(message="Playground stopped successfully")


@router.get("/projects/{project_id}/playground/logs")
async def get_playground_logs(
    project_id: str,
    tail: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get container logs (legacy)."""
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_user_and_project(current_user.id, project_id)

    if playground is None:
        raise HTTPException(status_code=404, detail="No playground found")

    logs = await playground_service.get_logs(playground, tail=tail)
    return {"logs": logs}


@router.post("/projects/{project_id}/playground/activity")
async def update_playground_activity(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update playground activity (legacy)."""
    project_service = ProjectService(db)
    project = await project_service.get_by_id_for_user(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    playground_service = PlaygroundService(db)
    playground = await playground_service.get_by_user_and_project(current_user.id, project_id)

    if playground is None:
        raise HTTPException(status_code=404, detail="No playground running")

    await playground_service.update_activity(playground)
    return {"message": "Activity updated"}


# ===== WebSocket Routes =====

@router.websocket("/projects/{project_id}/playground/logs/stream")
async def stream_playground_logs(
    websocket: WebSocket,
    project_id: str,
    token: str = Query(None),
):
    """WebSocket for streaming container logs."""
    await websocket.accept()

    if not token:
        try:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            token = data
        except asyncio.TimeoutError:
            await websocket.close(code=4001, reason="Authentication timeout")
            return

    token_data = verify_token(token, expected_type="access")
    if token_data is None:
        await websocket.close(code=4002, reason="Invalid token")
        return
    user_id = token_data.sub

    async with AsyncSessionLocal() as db:
        project_service = ProjectService(db)
        project = await project_service.get_by_id_for_user(project_id, user_id)
        if project is None:
            await websocket.close(code=4004, reason="Project not found")
            return

        playground_service = PlaygroundService(db)
        playground = await playground_service.get_by_user_and_project(user_id, project_id)
        if playground is None:
            await websocket.close(code=4004, reason="No playground found")
            return

        container_id = playground.container_id

    log_queue: queue.Queue = queue.Queue()
    stop_event = asyncio.Event()

    def stream_logs_sync():
        try:
            container = docker_client.client.containers.get(container_id)
            log_stream = container.logs(stream=True, follow=True, tail=0, timestamps=False)
            for log_chunk in log_stream:
                if stop_event.is_set():
                    break
                if log_chunk:
                    log_line = log_chunk.decode('utf-8').rstrip('\n')
                    if log_line:
                        log_queue.put(log_line)
        except Exception as e:
            log_queue.put(f"Error: {e}")
        finally:
            log_queue.put(None)

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    loop.run_in_executor(executor, stream_logs_sync)

    try:
        while True:
            try:
                log_line = log_queue.get_nowait()
                if log_line is None:
                    break
                await websocket.send_text(log_line)
            except queue.Empty:
                await asyncio.sleep(0.1)

            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(f"Error streaming logs: {e}")
        except Exception:
            pass
    finally:
        stop_event.set()
        executor.shutdown(wait=False)
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/projects/{project_id}/playground/terminal")
async def terminal_websocket(
    websocket: WebSocket,
    project_id: str,
    token: str = Query(None),
):
    """WebSocket for interactive terminal access."""
    import socket as sock

    await websocket.accept()

    if not token:
        try:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            token = data
        except asyncio.TimeoutError:
            await websocket.close(code=4001, reason="Authentication timeout")
            return

    token_data = verify_token(token, expected_type="access")
    if token_data is None:
        await websocket.close(code=4002, reason="Invalid token")
        return
    user_id = token_data.sub

    async with AsyncSessionLocal() as db:
        project_service = ProjectService(db)
        project = await project_service.get_by_id_for_user(project_id, user_id)
        if project is None:
            await websocket.close(code=4004, reason="Project not found")
            return

        playground_service = PlaygroundService(db)
        playground = await playground_service.get_by_user_and_project(user_id, project_id)
        if playground is None:
            await websocket.close(code=4004, reason="No playground found")
            return

        container_id = playground.container_id

    output_queue: queue.Queue = queue.Queue()
    stop_event = asyncio.Event()
    exec_socket = None
    exec_id = None

    def read_docker_stream():
        nonlocal exec_socket
        try:
            while not stop_event.is_set():
                if exec_socket is None:
                    break
                try:
                    data = exec_socket.recv(4096)
                    if not data:
                        break
                    output_queue.put(data.decode('utf-8', errors='replace'))
                except sock.timeout:
                    continue
                except Exception as e:
                    if not stop_event.is_set():
                        output_queue.put(f"\r\n[Connection error: {e}]\r\n")
                    break
        finally:
            output_queue.put(None)

    try:
        docker_client.client.containers.get(container_id)
        exec_instance = docker_client.client.api.exec_create(
            container_id,
            cmd=["/bin/bash"],
            stdin=True, stdout=True, stderr=True, tty=True,
            user="nobody", workdir="/workspace",
            environment={"TERM": "xterm-256color", "HOME": "/workspace"},
        )
        exec_id = exec_instance['Id']

        exec_socket = docker_client.client.api.exec_start(exec_id, socket=True, tty=True)
        exec_socket = exec_socket._sock
        exec_socket.settimeout(0.1)

        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        loop.run_in_executor(executor, read_docker_stream)

        while True:
            try:
                while True:
                    output = output_queue.get_nowait()
                    if output is None:
                        raise WebSocketDisconnect()
                    await websocket.send_text(output)
            except queue.Empty:
                pass

            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
                try:
                    data = json.loads(msg)
                    if data.get("type") == "input":
                        input_data = data.get("data", "")
                        if input_data and exec_socket:
                            exec_socket.send(input_data.encode('utf-8'))
                    elif data.get("type") == "resize":
                        cols = data.get("cols", 80)
                        rows = data.get("rows", 24)
                        if exec_id:
                            docker_client.client.api.exec_resize(exec_id, height=rows, width=cols)
                except json.JSONDecodeError:
                    if msg and exec_socket:
                        exec_socket.send(msg.encode('utf-8'))
            except asyncio.TimeoutError:
                pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(f"\r\n[Terminal error: {e}]\r\n")
        except Exception:
            pass
    finally:
        stop_event.set()
        if exec_socket:
            try:
                exec_socket.close()
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass
