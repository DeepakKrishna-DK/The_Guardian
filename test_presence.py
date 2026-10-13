import asyncio
import threading
import time
import logging

from guardian.core.presence_server import start_server
from guardian.voice import get_voice_layer

logging.basicConfig(level=logging.INFO)

def run_server():
    print("Starting WebSocket Server on port 8000...")
    start_server(host="127.0.0.1", port=8000)

if __name__ == "__main__":
    # Start the server in a background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait a moment for server to bind
    time.sleep(2)
    
    print("Initializing Voice Layer...")
    # Initialize voice layer (this will download the TTS model if first run, which takes a few seconds)
    vl = get_voice_layer()
    
    # Wait for the user to open the frontend and connect
    input("Press ENTER once the Vite frontend (http://localhost:5199) is open and connected...")
    
    print("Synthesizing and broadcasting...")
    text = (
        "Hello, I am Guardian. My lip sync audio routing is now fully operational. "
        "The web audio API is currently driving my three-dimensional morph targets in real-time."
    )
    
    # We call say with blocking=True. It will play locally via PyAudio as well.
    vl.say(text, blocking=True)
    
    print("Done. Keeping server alive for 5 seconds...")
    time.sleep(5)
