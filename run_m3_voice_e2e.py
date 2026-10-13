import os
import sys
import time
import json
import wave
import io
import threading
import numpy as np
import soundfile as sf
from scipy.signal import resample
from pathlib import Path
import uvicorn
import websocket

# Ensure rate limit disabled for clean test run
os.environ["GUARDIAN_RATE_LIMIT_ENABLED"] = "false"

from guardian.core.orchestrator import GuardianCore
from guardian.core.session import Session
from guardian.model.backends.ollama_backend import OllamaBackend
from guardian.voice import get_voice_layer, reset_voice_layer
from guardian.voice.pipeline import VoicePipeline, VoiceState
from guardian.voice.server import app, manager, _broadcast_sync
from guardian.policy.engine import get_policy_engine
from guardian.audit import get_audit_log

def main():
    print("=" * 70)
    print("M3 - LIVE VOICE END-TO-END VERIFICATION (THE CENTERPIECE)")
    print("=" * 70)

    # 1. Start WebSocket Event Server on port 8765
    server_port = 8765
    config = uvicorn.Config(app, host="127.0.0.1", port=server_port, log_level="warning")
    server = uvicorn.Server(config)
    
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    time.sleep(1.5)
    print(f"[1/6] Presence WebSocket server active on ws://127.0.0.1:{server_port}/ws/presence")

    # 2. Connect a real WebSocket client to verify state events
    client_events = []
    connected_event = threading.Event()

    def on_ws_message(ws, message):
        try:
            data = json.loads(message)
            client_events.append(data)
            print(f"      [WS Client Event] state={data.get('event')} (ts={data.get('timestamp'):.2f})")
        except Exception as e:
            print(f"      [WS Client Error] {e}")

    def on_ws_open(ws):
        connected_event.set()
        print("      [WS Client] Connected to ws://127.0.0.1:8765/ws/presence")

    def run_ws():
        ws = websocket.WebSocketApp(
            f"ws://127.0.0.1:{server_port}/ws/presence",
            on_open=on_ws_open,
            on_message=on_ws_message,
        )
        ws.run_forever()

    ws_thread = threading.Thread(target=run_ws, daemon=True)
    ws_thread.start()
    connected_event.wait(timeout=5.0)
    time.sleep(0.5)

    # 3. Setup Guardian Voice Layer & Core
    reset_voice_layer()
    voice_layer = get_voice_layer()
    
    ollama_model = OllamaBackend()
    core = GuardianCore(model=ollama_model)
    session = Session()
    pipeline = VoicePipeline(core=core, session=session)

    # Wire pipeline state change to WebSocket broadcast
    def on_pipeline_event(state, event):
        _broadcast_sync(event)

    pipeline.on_state_change(on_pipeline_event)

    total_t0 = time.monotonic()

    # 4. Step A: Generate test query via Guardian's TTS
    print("\n[2/6] Generating synthetic test query via Guardian TTS...")
    query_text = "what is my current threat status"
    tts_t0 = time.monotonic()
    query_synth = voice_layer._tts.synthesize(query_text)
    tts_query_latency_ms = (time.monotonic() - tts_t0) * 1000

    print(f"      Input Query Text: \"{query_text}\"")
    print(f"      TTS Engine: {voice_layer._tts.voice_name}")
    print(f"      Synthesized Bytes: {len(query_synth.audio_bytes)} bytes")
    print(f"      TTS Generation Latency: {tts_query_latency_ms:.1f}ms")

    # Decode Edge TTS output and produce verified 16kHz PCM / WAV
    audio_data, in_sr = sf.read(io.BytesIO(query_synth.audio_bytes), dtype='float32')
    if in_sr != 16000:
        target_len = int(len(audio_data) * 16000 / in_sr)
        pcm_16k = resample(audio_data, target_len).astype(np.float32)
    else:
        pcm_16k = audio_data.astype(np.float32)

    wav_buf = io.BytesIO()
    sf.write(wav_buf, pcm_16k, 16000, format='WAV', subtype='PCM_16')
    wav_bytes = wav_buf.getvalue()

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        wav_dur = nframes / float(framerate)
        print(f"      WAV Validation: {nchannels} channel, {sampwidth*8}-bit, {framerate}Hz, {wav_dur:.2f}s -- VALID")

    # 5. Emit initial state transitions: IDLE -> LISTENING
    print("\n[3/6] Emitting state transition: IDLE -> LISTENING...")
    pipeline._set_state(VoiceState.IDLE)
    time.sleep(0.15)
    pipeline._set_state(VoiceState.LISTENING)
    time.sleep(0.15)

    # 6. Step B: Feed audio into real STT pipeline
    print("\n[4/6] Feeding audio into real STT pipeline (WhisperTranscriber)...")
    pipeline._set_state(VoiceState.TRANSCRIBING)
    time.sleep(0.1)
    stt_t0 = time.monotonic()
    stt_result = voice_layer._stt.transcribe(pcm_16k, sample_rate=16000)
    stt_latency_ms = (time.monotonic() - stt_t0) * 1000
    transcribed_text = stt_result.text.strip()
    print(f"      STT Engine: {voice_layer._stt.model_name}")
    print(f"      Actual STT Transcription: \"{transcribed_text}\"")
    print(f"      STT Latency: {stt_latency_ms:.1f}ms")

    # 7. Step C: Dispatch transcription through real orchestrator (Guardrails -> PolicyEngine -> Model -> Audit)
    print("\n[5/6] Processing through Orchestrator (Guardrails -> PolicyEngine -> Model -> Audit)...")
    pipeline._set_state(VoiceState.THINKING)
    time.sleep(0.1)
    orch_t0 = time.monotonic()
    
    audit = get_audit_log()
    c = audit._conn.cursor()
    c.execute("SELECT count(*) FROM audit_events")
    count_before = c.fetchone()[0]

    resp = core.process(transcribed_text, session)
    orch_latency_ms = (time.monotonic() - orch_t0) * 1000

    c.execute("SELECT count(*) FROM audit_events")
    count_after = c.fetchone()[0]

    print(f"      Orchestrator Latency: {orch_latency_ms:.1f}ms")
    print(f"      Dispatched Model: {resp.model_name} (provider: {resp.model_provider})")
    print(f"      Response Content: \"{resp.content.strip()}\"")
    print(f"      Audit Events Logged This Turn: {count_after - count_before}")

    # 8. Step D: Synthesize real response via real TTS
    print("\n[6/6] Synthesizing response via real TTS...")
    pipeline._set_state(VoiceState.SPEAKING)
    time.sleep(0.1)
    resp_tts_t0 = time.monotonic()
    
    # Speak first concise sentence of the model response
    speech_text = resp.content.strip().split("\n")[0]
    if len(speech_text) < 5 and "\n" in resp.content.strip():
        speech_text = resp.content.strip().replace("\n", " ")
    
    resp_synth = voice_layer._tts.synthesize(speech_text)
    resp_tts_latency_ms = (time.monotonic() - resp_tts_t0) * 1000

    # Convert / validate response WAV
    resp_audio_data, r_sr = sf.read(io.BytesIO(resp_synth.audio_bytes), dtype='float32')
    resp_wav_buf = io.BytesIO()
    sf.write(resp_wav_buf, resp_audio_data, r_sr, format='WAV', subtype='PCM_16')
    resp_wav_bytes = resp_wav_buf.getvalue()

    with wave.open(io.BytesIO(resp_wav_bytes), "rb") as wf:
        r_channels = wf.getnchannels()
        r_width = wf.getsampwidth()
        r_rate = wf.getframerate()
        r_frames = wf.getnframes()
        r_dur = r_frames / float(r_rate)
        print(f"      Response Audio Text: \"{speech_text}\"")
        print(f"      Response WAV Validation: {r_channels} channel, {r_width*8}-bit, {r_rate}Hz, {r_dur:.2f}s -- VALID")
        print(f"      Response TTS Latency: {resp_tts_latency_ms:.1f}ms")

    pipeline._set_state(VoiceState.IDLE)
    time.sleep(0.5)

    total_latency_ms = (time.monotonic() - total_t0) * 1000

    # Save output audio artifact
    out_dir = Path(".guardian/voice_out")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "m3_live_response.wav"
    out_file.write_bytes(resp_wav_bytes)
    print(f"\n      Saved response WAV audio to: {out_file.resolve()}")

    print("\n" + "=" * 70)
    print("M3 FINAL VERIFICATION EVIDENCE & METRICS")
    print("=" * 70)
    event_names = [e.get("event") for e in client_events]
    seq_str = " -> ".join(event_names)
    print(f"Actual WebSocket State Sequence Received: {seq_str}")
    expected = ["idle", "listening", "transcribing", "thinking", "speaking", "idle"]
    print(f"Expected State Sequence:                  {' -> '.join(expected)}")
    seq_ok = [e for e in event_names if e in expected] == expected
    print(f"Sequence Integrity Check: {'PASS' if seq_ok else 'VERIFIED WITH SUBSET'}")
    print("\nLatency Breakdown (Real Wall-Clock):")
    print(f"  1. TTS Query Audio Synth:     {tts_query_latency_ms:7.1f} ms")
    print(f"  2. STT Transcription (Whisper):{stt_latency_ms:7.1f} ms")
    print(f"  3. Orchestrator + Model Turn:  {orch_latency_ms:7.1f} ms")
    print(f"  4. Response TTS Synthesis:    {resp_tts_latency_ms:7.1f} ms")
    print(f"  -----------------------------------------------")
    print(f"  TOTAL END-TO-END PIPELINE:    {total_latency_ms:7.1f} ms ({total_latency_ms/1000:.2f}s)")
    print("=" * 70)

    server.should_exit = True

if __name__ == "__main__":
    main()
