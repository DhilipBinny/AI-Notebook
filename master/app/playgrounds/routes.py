"""
Playground API routes.
"""

import asyncio
import struct
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, AsyncSessionLocal
from app.auth.dependencies import get_current_active_user
from app.auth.jwt import verify_token
from app.users.models import User
from app.projects.service import ProjectService
from .service import PlaygroundService
from .schemas import PlaygroundResponse, PlaygroundStartResponse, PlaygroundStopResponse
from .docker_client import docker_client

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


@router.websocket("/projects/{project_id}/playground/logs/stream")
async def stream_playground_logs(
    websocket: WebSocket,
    project_id: str,
    token: str = Query(None),
):
    """
    WebSocket endpoint for streaming container logs in real-time.

    Connect with: ws://host/api/projects/{id}/playground/logs/stream?token=JWT
    Or the token can be passed via the first message after connection.
    """
    await websocket.accept()

    # Get token from query param or wait for first message
    if not token:
        try:
            # Wait for token in first message
            data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            token = data
        except asyncio.TimeoutError:
            await websocket.close(code=4001, reason="Authentication timeout")
            return

    # Validate token
    token_data = verify_token(token, expected_type="access")
    if token_data is None:
        await websocket.close(code=4002, reason="Invalid token")
        return
    user_id = token_data.sub

    # Get playground using a new session
    async with AsyncSessionLocal() as db:
        project_service = ProjectService(db)
        project = await project_service.get_by_id_for_user(project_id, user_id)

        if project is None:
            await websocket.close(code=4004, reason="Project not found")
            return

        playground_service = PlaygroundService(db)
        playground = await playground_service.get_by_project_id(project_id)

        if playground is None:
            await websocket.close(code=4004, reason="No playground found")
            return

        container_id = playground.container_id

    # Stream logs using asyncio queue to avoid blocking
    import queue
    from concurrent.futures import ThreadPoolExecutor

    log_queue: queue.Queue = queue.Queue()
    stop_event = asyncio.Event()

    def stream_logs_sync():
        """Synchronous function to stream Docker logs into a queue."""
        try:
            container = docker_client.client.containers.get(container_id)
            log_stream = container.logs(
                stream=True,
                follow=True,
                tail=0,
                timestamps=False,
            )
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
            log_queue.put(None)  # Signal end of stream

    # Start log streaming in a thread
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    log_future = loop.run_in_executor(executor, stream_logs_sync)

    try:
        while True:
            # Check for new log lines (non-blocking)
            try:
                log_line = log_queue.get_nowait()
                if log_line is None:  # End of stream
                    break
                await websocket.send_text(log_line)
            except queue.Empty:
                # No logs available, wait a bit
                await asyncio.sleep(0.1)

            # Check if WebSocket is still connected
            try:
                # Use a short timeout to check for disconnect
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=0.01
                )
            except asyncio.TimeoutError:
                pass  # No message, continue
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
    """
    WebSocket endpoint for interactive terminal access to the playground container.

    Connect with: ws://host/api/projects/{id}/playground/terminal?token=JWT

    Messages:
    - From client: JSON with type "input" (terminal input) or "resize" (terminal resize)
    - To client: terminal output as text
    """
    await websocket.accept()

    # Get token from query param or wait for first message
    if not token:
        try:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            token = data
        except asyncio.TimeoutError:
            await websocket.close(code=4001, reason="Authentication timeout")
            return

    # Validate token
    token_data = verify_token(token, expected_type="access")
    if token_data is None:
        await websocket.close(code=4002, reason="Invalid token")
        return
    user_id = token_data.sub

    # Get playground using a new session
    async with AsyncSessionLocal() as db:
        project_service = ProjectService(db)
        project = await project_service.get_by_id_for_user(project_id, user_id)

        if project is None:
            await websocket.close(code=4004, reason="Project not found")
            return

        playground_service = PlaygroundService(db)
        playground = await playground_service.get_by_project_id(project_id)

        if playground is None:
            await websocket.close(code=4004, reason="No playground found")
            return

        container_id = playground.container_id

    # Create interactive exec session
    import queue
    from concurrent.futures import ThreadPoolExecutor
    import json
    import socket as sock

    output_queue: queue.Queue = queue.Queue()
    stop_event = asyncio.Event()
    exec_socket = None
    exec_id = None

    def read_docker_stream():
        """Read from docker exec socket and put data in queue."""
        nonlocal exec_socket
        try:
            while not stop_event.is_set():
                if exec_socket is None:
                    break
                try:
                    # With TTY enabled, Docker sends raw bytes (no multiplexing)
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
        # Create exec instance with TTY
        # Run as 'nobody' user to prevent access to playground binary
        # Start in /workspace directory where user has read/write access
        container = docker_client.client.containers.get(container_id)
        exec_instance = docker_client.client.api.exec_create(
            container_id,
            cmd=["/bin/bash"],
            stdin=True,
            stdout=True,
            stderr=True,
            tty=True,
            user="nobody",
            workdir="/workspace",
            environment={"TERM": "xterm-256color", "HOME": "/workspace"},
        )
        exec_id = exec_instance['Id']

        # Start exec and get socket
        exec_socket = docker_client.client.api.exec_start(
            exec_id,
            socket=True,
            tty=True,
        )
        # Get the underlying socket
        exec_socket = exec_socket._sock
        exec_socket.settimeout(0.1)

        # Start reader thread
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        reader_future = loop.run_in_executor(executor, read_docker_stream)

        # Main loop
        while True:
            # Send any pending output to client
            try:
                while True:
                    output = output_queue.get_nowait()
                    if output is None:
                        raise WebSocketDisconnect()
                    await websocket.send_text(output)
            except queue.Empty:
                pass

            # Check for client input
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
                    # Plain text input
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
