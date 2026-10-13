import asyncio
import json
import logging
import threading
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

from guardian.logging.logger import get_logger
from guardian.voice.pipeline import VoiceState, VoicePipeline

log = get_logger(__name__)

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        log.info("WebSocket client connected to Presence")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        log.info("WebSocket client disconnected")

    async def broadcast(self, message: dict):
        text = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(text)
            except Exception as e:
                log.error(f"WebSocket broadcast error: {e}")

manager = ConnectionManager()

@app.websocket("/ws/presence")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # We don't expect much from client, but keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def _broadcast_sync(message: dict):
    """Sync wrapper to run async broadcast from a sync thread."""
    try:
        # Get the running event loop for FastAPI, or create one if not in an async context
        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)
    except RuntimeError:
        # If no loop is running in this thread, we just run it directly
        asyncio.run(manager.broadcast(message))

def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the local event server."""
    log.info(f"Starting Voice Event Server on ws://{host}:{port}/ws/presence")
    # Suppress uvicorn access logs for clean CLI output
    uvicorn.run(app, host=host, port=port, log_level="warning")

def start_server_thread(pipeline: VoicePipeline, host: str = "127.0.0.1", port: int = 8000) -> threading.Thread:
    """Start the server in a background thread and hook the pipeline events."""
    
    def on_state_change(state: VoiceState, event: dict[str, Any]):
        _broadcast_sync(event)

    pipeline.on_state_change(on_state_change)
    
    thread = threading.Thread(target=run_server, args=(host, port), daemon=True)
    thread.start()
    return thread
