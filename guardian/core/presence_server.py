import asyncio
import base64
import json
import logging
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)

class PresenceBroadcaster:
    """Manages active WebSocket connections and broadcasts events."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        log.info(f"Presence frontend connected. Active clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            log.info(f"Presence frontend disconnected. Active clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcasts a JSON message to all connected clients."""
        if not self.active_connections:
            return
            
        json_str = json.dumps(message)
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_text(json_str)
            except Exception as e:
                log.warning(f"Failed to send to client: {e}")
                disconnected.add(connection)
                
        # Clean up dead connections
        for dead_conn in disconnected:
            self.disconnect(dead_conn)

    def broadcast_sync(self, message: dict):
        """Synchronous wrapper for broadcasting events."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(message))
        except RuntimeError:
            # No running event loop, create a temporary one
            asyncio.run(self.broadcast(message))

# Global singleton
broadcaster = PresenceBroadcaster()
app = FastAPI(title="Guardian Presence Bridge")

@app.websocket("/ws/presence")
async def websocket_endpoint(websocket: WebSocket):
    await broadcaster.connect(websocket)
    try:
        while True:
            # Keep connection alive and listen for client messages (e.g. playback complete)
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                log.debug(f"Received from frontend: {msg}")
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)

def start_server(host="127.0.0.1", port=8000):
    """Start the FastAPI server (blocking)."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    # Test the server standalone
    logging.basicConfig(level=logging.INFO)
    start_server()
