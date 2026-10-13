import time
import os
import io
import wave
from guardian.voice.tts import auto_synthesizer
from guardian.voice.stt import WhisperTranscriber

def test_tts_stt():
    print("=== TESTING TTS SYNTHESIS ===")
    t0 = time.monotonic()
    tts = auto_synthesizer()
    print(f"TTS Engine: {tts.voice_name}")
    query_text = "what is my current threat status"
    synth_res = tts.synthesize(query_text)
    t_synth = time.monotonic() - t0
    print(f"Synthesized query '{query_text}' in {t_synth:.2f}s")
    print(f"Audio bytes length: {len(synth_res.audio_bytes)}")
    print(f"Reported duration: {synth_res.duration_s:.2f}s, format: {synth_res.format}")

    # Verify wave file
    try:
        with wave.open(io.BytesIO(synth_res.audio_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            calc_duration = nframes / float(framerate)
            print(f"Valid WAV: channels={channels}, width={sampwidth}, rate={framerate}, frames={nframes}, duration={calc_duration:.2f}s")
    except Exception as e:
        print(f"WAV check error: {e}")

    print("\n=== TESTING STT TRANSCRIPTION ===")
    t1 = time.monotonic()
    stt = WhisperTranscriber(model="tiny", device="cpu")
    print(f"STT Model: {stt.model_name}")
    transcript_res = stt.transcribe(synth_res.audio_bytes)
    t_stt = time.monotonic() - t1
    print(f"Transcribed in {t_stt:.2f}s: '{transcript_res.text}'")

if __name__ == "__main__":
    test_tts_stt()
