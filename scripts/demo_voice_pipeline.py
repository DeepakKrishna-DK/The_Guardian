import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from guardian.core.orchestrator import GuardianCore
from guardian.core.session import Session
from guardian.model.backends.mock import MockBackend
from guardian.voice.pipeline import VoicePipeline, VoiceState
from guardian.voice.server import start_server_thread

def main():
    print("Initializing Core (MockBackend)...")
    core = GuardianCore(model=MockBackend())
    session = Session()
    
    print("Initializing Voice Pipeline...")
    pipeline = VoicePipeline(core=core, session=session)
    
    def on_state(state, event):
        print(f">>> STATE TRANSITION: {state.value.upper()} (at {event['timestamp']:.2f})")
    
    pipeline.on_state_change(on_state)
    
    print("Starting local event server on ws://127.0.0.1:8000/ws/presence...")
    start_server_thread(pipeline)
    
    # Wait for server to bind
    time.sleep(2)
    
    # Synthesize dummy audio byte request
    print("\nSending synthetic utterance to pipeline...")
    # Using 1 second of silence just to trigger it
    dummy_audio = b"\x00" * 32000 
    
    # In order for STT to give a result, we might need a real wav or we can just mock the STT layer.
    # The pipeline uses the global voice layer.
    from guardian.voice import get_voice_layer
    # Using edge tts to generate synthetic audio for the pipeline to hear
    print("Generating synthetic input audio via TTS...")
    layer = get_voice_layer()
    synth = layer._tts.synthesize("Hello Guardian, please give me a quick status update.")
    
    print("Processing audio...")
    import soundfile as sf
    import io
    import numpy as np
    
    data, samplerate = sf.read(io.BytesIO(synth.audio_bytes))
    if len(data.shape) > 1:
        data = data[:, 0]
    
    # Resample to 16000 naive if necessary
    if samplerate != 16000:
        # naive resampling
        ratio = samplerate // 16000
        if ratio > 0:
            data = data[::ratio]
        
    data = data.astype(np.float32)
    pipeline.process_audio(data)
    
    print("Demo complete. Server will exit.")

if __name__ == "__main__":
    main()
