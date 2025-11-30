"""
WebSocket endpoints for Web Terminal
"""
import json
import asyncio
import os
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TerminalSession
from app.services.auth_service import get_current_user_ws
from app.services.ssh_service import get_ssh_connection
from app.config import get_settings

router = APIRouter(tags=["Terminal"])
settings = get_settings()

RECORDING_DIR = settings.recording_dir
os.makedirs(RECORDING_DIR, exist_ok=True)

@router.websocket("/ws/terminal/{server_id}")
async def terminal_websocket(
    websocket: WebSocket,
    server_id: UUID,
    token: str = Query(...),
    cols: int = Query(80),
    rows: int = Query(24),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for SSH terminal.
    """
    # Authenticate
    user = await get_current_user_ws(token, db)
    if not user:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    
    ssh_client = None
    process = None
    recording_file = None
    
    try:
        # 1. Get SSH Connection
        ssh_client = await get_ssh_connection(db, server_id)
        await ssh_client.connect()
        
        # 2. Start Shell
        process = await ssh_client.start_shell(term_size=(cols, rows))
        
        # 3. Create Session Record & Recording File
        timestamp = int(datetime.utcnow().timestamp())
        filename = f"{user.username}_{server_id}_{timestamp}.log"
        filepath = os.path.join(RECORDING_DIR, filename)
        
        # Create the file immediately
        recording_file = open(filepath, "w", encoding="utf-8")
        
        session_record = TerminalSession(
            user_id=user.id,
            server_credential_id=server_id,
            recording_path=filepath
        )
        db.add(session_record)
        db.commit()
        
        # 4. Pipe Data
        async def forward_output():
            """Read from SSH stdout and send to WebSocket"""
            try:
                while not process.stdout.at_eof():
                    data = await process.stdout.read(1024)
                    if data:
                        # Record output
                        if recording_file:
                            recording_file.write(data)
                            recording_file.flush()
                            
                        # Send as text (xterm.js expects string)
                        await websocket.send_text(data)
            except Exception:
                pass

        async def forward_input():
            """Read from WebSocket and send to SSH stdin"""
            try:
                while True:
                    data = await websocket.receive_text()
                    
                    # Check for resize event (custom protocol)
                    if data.startswith('{"type":"resize"'):
                        try:
                            resize_data = json.loads(data)
                            process.set_terminal_size(
                                resize_data["cols"], 
                                resize_data["rows"]
                            )
                            continue
                        except:
                            pass
                    
                    # We could record input here too, but output usually contains the echoed input
                    process.stdin.write(data)
            except WebSocketDisconnect:
                pass
            except Exception:
                pass

        async def heartbeat():
            """Send periodic pings to keep connection alive"""
            while True:
                try:
                    await asyncio.sleep(30)
                    await websocket.send_text('{"type":"ping"}')
                except:
                    break

        # Run tasks
        output_task = asyncio.create_task(forward_output())
        input_task = asyncio.create_task(forward_input())
        heartbeat_task = asyncio.create_task(heartbeat())
        
        # Wait for either to finish
        done, pending = await asyncio.wait(
            [output_task, input_task, heartbeat_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        for task in pending:
            task.cancel()
            
        # Update session end time
        session_record.ended_at = datetime.utcnow()
        db.commit()
            
    except Exception as e:
        await websocket.send_text(f"\r\nConnection Error: {str(e)}\r\n")
        
    finally:
        if recording_file:
            recording_file.close()
        if ssh_client:
            await ssh_client.close()
        await websocket.close()
