"""WebSocket endpoints for Web Terminal."""
import json
import asyncio
import logging
import os
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState
import aiofiles

from app.database import get_db
from app.models import TerminalSession
from app.services.auth_service import get_current_user_ws
from app.services.ssh_service import get_ssh_connection
from app.config import get_settings
from app.metrics import TERMINAL_SESSIONS, TERMINAL_CONNECTIONS

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Terminal"])
settings = get_settings()

RECORDING_DIR = settings.recording_dir
os.makedirs(RECORDING_DIR, exist_ok=True)

# WebSocket close codes
WS_CLOSE_AUTH_FAILED = 4001
WS_CLOSE_SERVER_NOT_FOUND = 4004
WS_CLOSE_SSH_FAILED = 4010
WS_CLOSE_INTERNAL_ERROR = 4500


async def safe_send(websocket: WebSocket, message: str) -> bool:
    """Safely send a message to WebSocket, returning False if connection is closed."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(message)
            return True
    except Exception as e:
        logger.debug(f"Failed to send WebSocket message: {e}")
    return False


async def safe_close(websocket: WebSocket, code: int = 1000) -> None:
    """Safely close a WebSocket connection."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=code)
    except Exception as e:
        logger.debug(f"Error closing WebSocket: {e}")


# NOTE: Ad-hoc endpoint MUST be defined before the parameterized {server_id} route
# to prevent FastAPI from trying to parse "adhoc" as a UUID
@router.websocket("/ws/terminal/adhoc")
async def terminal_adhoc_websocket(
    websocket: WebSocket,
    token: str = Query(...),
    host: str = Query(...),
    port: int = Query(22),
    username: str = Query(...),
    password: str = Query(None),
    cols: int = Query(80, ge=10, le=500),
    rows: int = Query(24, ge=5, le=200),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for ad-hoc SSH terminal connections.
    Allows connecting to any server without saving credentials.
    """
    from app.services.ssh_service import SSHClient
    
    # Authenticate
    user = await get_current_user_ws(token, db)
    if not user:
        logger.warning(f"Ad-hoc terminal WebSocket auth failed")
        TERMINAL_CONNECTIONS.labels(status="auth_failed").inc()
        await websocket.close(code=WS_CLOSE_AUTH_FAILED)
        return

    await websocket.accept()
    logger.info(f"Ad-hoc terminal WebSocket connected: user={user.username}, host={host}")
    TERMINAL_SESSIONS.inc()
    
    ssh_client = None
    process = None
    tasks = []
    
    try:
        ssh_client = SSHClient(host=host, port=port, username=username, password=password)
        
        try:
            await ssh_client.connect()
        except Exception as e:
            logger.error(f"Ad-hoc SSH connection failed to {host}: {e}")
            TERMINAL_CONNECTIONS.labels(status="ssh_failed").inc()
            await safe_send(websocket, f"\r\nSSH Connection Error: {str(e)}\r\n")
            await safe_close(websocket, WS_CLOSE_SSH_FAILED)
            return
        
        try:
            process = await ssh_client.start_shell(term_size=(cols, rows))
            TERMINAL_CONNECTIONS.labels(status="success").inc()
        except Exception as e:
            logger.error(f"Failed to start shell on {host}: {e}")
            await safe_send(websocket, f"\r\nFailed to start shell: {str(e)}\r\n")
            await safe_close(websocket, WS_CLOSE_SSH_FAILED)
            return
        
        async def forward_output():
            try:
                while process and not process.stdout.at_eof():
                    data = await process.stdout.read(1024)
                    if data:
                        if not await safe_send(websocket, data):
                            break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"Output forwarding ended: {e}")

        async def forward_input():
            try:
                while True:
                    data = await websocket.receive_text()
                    if data.startswith('{"type":'):
                        try:
                            msg = json.loads(data)
                            if msg.get("type") == "resize":
                                if process:
                                    process.set_terminal_size(msg.get("cols", cols), msg.get("rows", rows))
                                continue
                        except json.JSONDecodeError:
                            pass
                    if process and process.stdin:
                        process.stdin.write(data)
            except WebSocketDisconnect:
                logger.debug(f"WebSocket disconnected for ad-hoc terminal {host}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"Input forwarding ended: {e}")

        async def heartbeat():
            try:
                while True:
                    await asyncio.sleep(30)
                    if not await safe_send(websocket, '{"type":"ping"}'):
                        break
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

        output_task = asyncio.create_task(forward_output())
        input_task = asyncio.create_task(forward_input())
        heartbeat_task = asyncio.create_task(heartbeat())
        tasks = [output_task, input_task, heartbeat_task]
        
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
    except WebSocketDisconnect:
        logger.info(f"Ad-hoc terminal WebSocket disconnected: user={user.username}, host={host}")
    except Exception as e:
        logger.error(f"Ad-hoc terminal WebSocket error: {e}", exc_info=True)
        await safe_send(websocket, f"\r\nInternal Error: {str(e)}\r\n")
        
    finally:
        TERMINAL_SESSIONS.dec()
        for task in tasks:
            if not task.done():
                task.cancel()
        if ssh_client:
            try:
                await ssh_client.close()
            except Exception as e:
                logger.warning(f"Error closing SSH connection: {e}")
        await safe_close(websocket)


@router.websocket("/ws/terminal/{server_id}")
async def terminal_websocket(
    websocket: WebSocket,
    server_id: UUID,
    token: str = Query(...),
    cols: int = Query(80, ge=10, le=500),
    rows: int = Query(24, ge=5, le=200),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for SSH terminal.
    
    Close codes:
        - 4001: Authentication failed
        - 4004: Server not found
        - 4010: SSH connection failed
        - 4500: Internal server error
    """
    # Authenticate
    user = await get_current_user_ws(token, db)
    if not user:
        logger.warning(f"Terminal WebSocket auth failed for server {server_id}")
        TERMINAL_CONNECTIONS.labels(status="auth_failed").inc()
        await websocket.close(code=WS_CLOSE_AUTH_FAILED)
        return

    await websocket.accept()
    logger.info(f"Terminal WebSocket connected: user={user.username}, server={server_id}")
    TERMINAL_SESSIONS.inc()  # Increment active sessions
    
    ssh_client = None
    process = None
    session_record = None
    recording_task = None
    recording_queue = None
    tasks = []
    
    try:
        # 1. Get SSH Connection
        try:
            ssh_client = await get_ssh_connection(db, server_id)
        except ValueError as e:
            logger.error(f"Server credentials not found: {server_id}")
            TERMINAL_CONNECTIONS.labels(status="server_not_found").inc()
            await safe_send(websocket, f"\r\nError: Server not found\r\n")
            await safe_close(websocket, WS_CLOSE_SERVER_NOT_FOUND)
            return
        
        try:
            await ssh_client.connect()
        except Exception as e:
            logger.error(f"SSH connection failed to {server_id}: {e}")
            TERMINAL_CONNECTIONS.labels(status="ssh_failed").inc()
            await safe_send(websocket, f"\r\nSSH Connection Error: {str(e)}\r\n")
            await safe_close(websocket, WS_CLOSE_SSH_FAILED)
            return
        
        # 2. Start Shell
        try:
            process = await ssh_client.start_shell(term_size=(cols, rows))
            TERMINAL_CONNECTIONS.labels(status="success").inc()
        except Exception as e:
            logger.error(f"Failed to start shell on {server_id}: {e}")
            await safe_send(websocket, f"\r\nFailed to start shell: {str(e)}\r\n")
            await safe_close(websocket, WS_CLOSE_SSH_FAILED)
            return
        
        # 3. Create Session Record & Recording File
        timestamp = int(datetime.now(timezone.utc).timestamp())
        filename = f"{user.username}_{server_id}_{timestamp}.log"
        filepath = os.path.join(RECORDING_DIR, filename)
        
        # Queue for async recording
        recording_queue: asyncio.Queue = asyncio.Queue()
        recording_enabled = True
        
        session_record = TerminalSession(
            user_id=user.id,
            server_credential_id=server_id,
            recording_path=filepath
        )
        db.add(session_record)
        db.commit()
        
        # 4. Async recording writer task
        async def record_output():
            """Async task to write terminal output to file."""
            nonlocal recording_enabled
            try:
                async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
                    while True:
                        data = await recording_queue.get()
                        if data is None:  # Shutdown signal
                            break
                        try:
                            await f.write(data)
                            await f.flush()
                        except Exception as e:
                            logger.warning(f"Failed to write to recording: {e}")
                            recording_enabled = False
                            break
            except Exception as e:
                logger.warning(f"Recording task error: {e}")
                recording_enabled = False
        
        # 5. Pipe Data
        async def forward_output():
            """Read from SSH stdout and send to WebSocket."""
            try:
                while process and not process.stdout.at_eof():
                    data = await process.stdout.read(1024)
                    if data:
                        # Queue output for async recording (non-blocking)
                        if recording_enabled:
                            try:
                                recording_queue.put_nowait(data)
                            except asyncio.QueueFull:
                                logger.warning("Recording queue full, dropping data")
                            
                        # Send to WebSocket
                        if not await safe_send(websocket, data):
                            break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"Output forwarding ended: {e}")

        async def forward_input():
            """Read from WebSocket and send to SSH stdin."""
            try:
                while True:
                    data = await websocket.receive_text()
                    
                    # Check for resize event (custom protocol)
                    if data.startswith('{"type":'):
                        try:
                            msg = json.loads(data)
                            if msg.get("type") == "resize":
                                new_cols = msg.get("cols", cols)
                                new_rows = msg.get("rows", rows)
                                if process:
                                    process.set_terminal_size(new_cols, new_rows)
                                continue
                        except json.JSONDecodeError:
                            pass  # Not JSON, treat as regular input
                    
                    if process and process.stdin:
                        process.stdin.write(data)
            except WebSocketDisconnect:
                logger.debug(f"WebSocket disconnected for terminal {server_id}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"Input forwarding ended: {e}")

        async def heartbeat():
            """Send periodic pings to keep connection alive."""
            try:
                while True:
                    await asyncio.sleep(30)
                    if not await safe_send(websocket, '{"type":"ping"}'):
                        break
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

        # Run tasks
        recording_task = asyncio.create_task(record_output())
        output_task = asyncio.create_task(forward_output())
        input_task = asyncio.create_task(forward_input())
        heartbeat_task = asyncio.create_task(heartbeat())
        tasks = [output_task, input_task, heartbeat_task]
        
        # Wait for any task to finish
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Signal recording task to stop
        await recording_queue.put(None)
        
        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
    except WebSocketDisconnect:
        logger.info(f"Terminal WebSocket disconnected: user={user.username}, server={server_id}")
    except Exception as e:
        logger.error(f"Terminal WebSocket error: {e}", exc_info=True)
        await safe_send(websocket, f"\r\nInternal Error: {str(e)}\r\n")
        
    finally:
        # Cleanup in order
        logger.debug(f"Cleaning up terminal session for server {server_id}")
        
        # Decrement active sessions
        TERMINAL_SESSIONS.dec()
        
        # Signal recording task to stop and wait for it
        try:
            await recording_queue.put(None)
            await asyncio.wait_for(recording_task, timeout=2.0)
        except (asyncio.TimeoutError, NameError):
            pass
        except Exception as e:
            logger.debug(f"Error stopping recording task: {e}")
        
        # Cancel any remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
        
        # Update session end time
        if session_record:
            try:
                session_record.ended_at = datetime.now(timezone.utc)
                db.commit()
            except Exception as e:
                logger.error(f"Failed to update session end time: {e}")
        
        # Close SSH connection
        if ssh_client:
            try:
                await ssh_client.close()
            except Exception as e:
                logger.warning(f"Error closing SSH connection: {e}")
        
        # Close WebSocket
        await safe_close(websocket)
