"""
Guardian Voice -- VoiceLayer Facade
=====================================
Unified voice API wrapping STT + TTS + Wake + Audio capture.

VoiceLayer.transcribe_file(path)      -- Transcribe a WAV/MP3/etc file
VoiceLayer.transcribe_bytes(pcm)      -- Transcribe raw PCM bytes
VoiceLayer.say(text)                  -- Synthesize and play
VoiceLayer.synthesize(text)           -- Synthesize, return bytes (no play)
VoiceLayer.listen_once()              -- Record one utterance, return text
VoiceLayer.voice_chat_turn(text)      -- STT input already done: TTS output
VoiceLayer.start_wake_loop(callback)  -- Background thread wake detection

Singletons:
    get_voice_layer()       -- production (lazy model load)
    reset_voice_layer()     -- test teardown
    make_test_voice_layer() -- MockTranscriber + MockSynthesizer + MockWake

Apache-2.0.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from guardian.logging.logger import get_logger
from guardian.voice.stt import MockTranscriber, Transcriber, TranscriptResult, WhisperTranscriber
from guardian.voice.tts import (
    EdgeTTSSynthesizer,
    MockSynthesizer,
    PiperSynthesizer,
    SynthesisResult,
    Synthesizer,
    auto_synthesizer,
)
from guardian.voice.wake import MockWakeWordDetector, WakeResult, WakeWordDetector

log = get_logger(__name__)


@dataclass
class VoiceStatus:
    stt_model: str
    tts_voice: str
    wake_word: str
    audio_capture: bool


class VoiceLayer:
    """
    Unified voice facade.

    All heavy resources (models, microphone stream) are lazy-loaded.
    Safe to construct without GPU or microphone — only fails on first use.
    """

    def __init__(
        self,
        transcriber: Transcriber,
        synthesizer: Synthesizer,
        wake_detector: WakeWordDetector,
    ) -> None:
        self._stt   = transcriber
        self._tts   = synthesizer
        self._wake  = wake_detector
        self._capture: Any | None = None   # AudioCapture, lazy
        self._wake_thread: threading.Thread | None = None
        self._wake_running = False

    # ── STT ───────────────────────────────────────────────────────────────────

    def transcribe_bytes(
        self,
        audio: bytes | np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptResult:
        """Transcribe raw 16kHz PCM bytes or numpy array."""
        return self._stt.transcribe(audio, sample_rate=sample_rate, language=language)

    def transcribe_file(
        self,
        path: str | Path,
        language: str | None = None,
    ) -> TranscriptResult:
        """Transcribe an audio file (WAV, MP3, FLAC, etc.)."""
        try:
            import soundfile as sf
            data, sr = sf.read(str(path), dtype="int16", always_2d=False)
            return self._stt.transcribe(data, sample_rate=sr, language=language)
        except ImportError:
            # Fallback: read as raw bytes
            raw = Path(path).read_bytes()
            return self._stt.transcribe(raw, sample_rate=16000, language=language)

    # ── TTS ───────────────────────────────────────────────────────────────────

    def synthesize(self, text: str) -> SynthesisResult:
        """Synthesize speech and return WAV bytes without playing."""
        return self._tts.synthesize(text)

    def say(self, text: str, blocking: bool = True) -> SynthesisResult:
        """Synthesize speech and broadcast to frontend, optionally playing locally."""
        result = self._tts.synthesize(text)
        if result.audio_bytes:
            # Broadcast to visualization frontend
            try:
                from guardian.core.presence_server import broadcaster
                import base64
                audio_b64 = base64.b64encode(result.audio_bytes).decode('utf-8')
                broadcaster.broadcast_sync({
                    "event": "speaking",
                    "text": text,
                    "audio_b64": audio_b64
                })
            except Exception as e:
                log.warning(f"Failed to broadcast audio to presence: {e}")

            from guardian.voice.audio import play_audio
            play_audio(result.audio_bytes, blocking=blocking)
        
        # Broadcast idle when done
        try:
            from guardian.core.presence_server import broadcaster
            broadcaster.broadcast_sync({"event": "idle"})
        except Exception:
            pass
            
        return result

    # ── Microphone ───────────────────────────────────────────────────────────

    def _ensure_capture(self) -> Any:
        if self._capture is None:
            from guardian.voice.audio import AudioCapture
            self._capture = AudioCapture()
            self._capture.start()
        return self._capture

    def listen_once(
        self,
        max_seconds: float = 10.0,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> TranscriptResult:
        """Record one utterance (until silence) and transcribe."""
        cap = self._ensure_capture()
        log.info("Listening...")
        pcm = cap.record_utterance(max_seconds=max_seconds)
        log.info(f"Recorded {len(pcm)/16000:.1f}s audio, transcribing...")
        return self._stt.transcribe(pcm, sample_rate=16000, language=language, initial_prompt=initial_prompt)

    # ── Wake word loop ────────────────────────────────────────────────────────

    def start_wake_loop(self, on_wake: Callable[[WakeResult], None]) -> None:
        """
        Start background thread that watches for wake word.
        Calls on_wake(result) when detected, then resets detector.

        Stop with stop_wake_loop().
        """
        if self._wake_running:
            return
        self._wake_running = True
        cap = self._ensure_capture()
        detector = self._wake

        def _loop() -> None:
            log.info(f"Wake word loop started: listening for '{detector.wake_word}'")
            while self._wake_running:
                chunk = cap.get_chunk(timeout=0.1)
                if chunk is None:
                    continue
                result = detector.process_chunk(chunk.pcm)
                if result.detected:
                    log.info(f"Wake word detected: score={result.score:.3f}")
                    try:
                        on_wake(result)
                    except Exception as exc:
                        log.warning(f"on_wake callback error: {exc}")
                    detector.reset()
            log.info("Wake word loop stopped")

        self._wake_thread = threading.Thread(target=_loop, daemon=True, name="guardian-wake")
        self._wake_thread.start()

    def stop_wake_loop(self) -> None:
        self._wake_running = False
        if self._wake_thread:
            self._wake_thread.join(timeout=2.0)
            self._wake_thread = None

    def start_vad_wake_loop(self, wake_words: list[str], on_command: Callable[[str], None]) -> None:
        """
        Optimized rolling-window hotword detector.
        
        Speed optimizations applied:
         1. 1.5s chunks (was 3s) — halves wake detection latency
         2. Dual model: tiny Whisper for wake scanning (fast), base for command (accurate)
         3. Both models pre-warmed before loop starts — no cold-start delay
         4. on_command runs in a worker thread — audio capture never pauses
        """
        if self._wake_running:
            return
        self._wake_running = True

        def _loop() -> None:
            import re
            import numpy as np
            import time

            log.info(f"Optimized hotword loop started. Listening for: {wake_words}")
            sorted_ww = sorted([w.lower().strip() for w in wake_words], key=len, reverse=True)
            prompt = ", ".join(sorted_ww)
            cap = self._ensure_capture()

            # ── Pre-warm BOTH models right now (eliminates cold-start delay) ──
            from faster_whisper import WhisperModel
            log.info("Pre-warming Whisper tiny (wake) and base (command) models...")
            silence = np.zeros(16000, dtype=np.float32)

            # Tiny model for fast wake word scanning
            tiny_model = WhisperModel("tiny", device="cpu", compute_type="int8")
            list(tiny_model.transcribe(silence, beam_size=1)[0])  # warm up

            # Main STT model (already loaded or will load)
            self._stt._load()
            log.info("Both Whisper models ready — listening!")

            CHUNK_SECONDS = 1.5          # 1.5s chunks = fast wake detection
            SILENCE_THRESHOLD = 250      # slightly more sensitive
            SAMPLE_RATE = 16000
            busy = False                 # prevents overlapping on_command calls

            while self._wake_running:
                try:
                    if busy:
                        # Drain audio while processing previous command
                        cap.get_chunk(timeout=0.05)
                        continue

                    # ── Phase 1: collect 1.5s of audio ──
                    deadline = time.monotonic() + CHUNK_SECONDS
                    frames = []
                    while time.monotonic() < deadline and self._wake_running:
                        chunk = cap.get_chunk(timeout=0.05)
                        if chunk is not None:
                            frames.append(chunk.pcm)

                    if not frames:
                        continue

                    pcm = np.concatenate(frames).astype(np.float32)
                    rms = int(np.sqrt(np.mean(pcm ** 2)))
                    if rms < SILENCE_THRESHOLD:
                        continue

                    # ── Phase 2: FAST scan with tiny model ──
                    pcm_norm = pcm / 32768.0 if pcm.max() > 1.0 else pcm
                    segs, _ = tiny_model.transcribe(
                        pcm_norm, beam_size=1, vad_filter=True, initial_prompt=prompt
                    )
                    text = " ".join(s.text for s in segs).strip()
                    if not text:
                        continue

                    safe = text.encode('ascii', 'ignore').decode('ascii').strip()
                    if safe:
                        log.info(f"Chunk: '{safe}'")

                    clean = re.sub(r'[^\w\s]', '', text.lower().strip())

                    matched_ww = None
                    for ww in sorted_ww:
                        if ww in clean:
                            matched_ww = ww
                            break

                    if not matched_ww:
                        continue

                    log.info(f"Wake word '{matched_ww}' detected!")
                    busy = True

                    # Extract inline command from same chunk
                    idx = clean.find(matched_ww)
                    inline_command = clean[idx + len(matched_ww):].strip()

                    def _handle(cmd: str) -> None:
                        nonlocal busy
                        try:
                            if cmd:
                                log.info(f"Command: '{cmd}'")
                                on_command(cmd)
                            else:
                                # Listen for follow-up with accurate base model
                                log.info("Listening for follow-up command...")
                                cap.flush()
                                result = self.listen_once(max_seconds=8.0)
                                cmd2 = re.sub(r'[^\w\s\']', '', result.text.lower().strip())
                                log.info(f"Follow-up: '{cmd2}'")
                                on_command(cmd2)
                        except Exception as exc:
                            log.warning(f"on_command error: {exc}")
                        finally:
                            busy = False

                    # Run in thread so audio capture keeps flowing
                    threading.Thread(
                        target=_handle, args=(inline_command,), daemon=True
                    ).start()

                except Exception as exc:
                    log.warning(f"Hotword loop error: {exc}")
                    busy = False
                    time.sleep(0.5)

            log.info("Optimized hotword loop stopped")

        self._wake_thread = threading.Thread(target=_loop, daemon=True, name="guardian-hotword")
        self._wake_thread.start()

    def stop(self) -> None:
        """Stop all voice resources."""
        self.stop_wake_loop()
        if self._capture is not None:
            self._capture.stop()
            self._capture = None

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self) -> VoiceStatus:
        return VoiceStatus(
            stt_model=self._stt.model_name,
            tts_voice=self._tts.voice_name,
            wake_word=self._wake.wake_word,
            audio_capture=self._capture is not None,
        )


# ── Singletons ────────────────────────────────────────────────────────────────

_layer: VoiceLayer | None = None


def get_voice_layer(
    stt_model: str = "base",
    tts_voice: str = "en-US-GuyNeural",
    wake_word: str = "hey_mycroft",
    piper_model: str | None = None,
) -> VoiceLayer:
    """
    Return the shared VoiceLayer singleton.
    All models are lazy-loaded on first use.
    """
    global _layer
    if _layer is None:
        stt = WhisperTranscriber(model=stt_model, device="auto", compute_type="int8")
        tts = auto_synthesizer(piper_model=piper_model, voice=tts_voice)
        from guardian.voice.wake import OpenWakeWordDetector
        wake = OpenWakeWordDetector(wake_word=wake_word)
        _layer = VoiceLayer(transcriber=stt, synthesizer=tts, wake_detector=wake)
        log.info(f"VoiceLayer ready: stt={stt.model_name}, tts={tts.voice_name}, wake={wake_word}")
    return _layer


def reset_voice_layer() -> None:
    """Reset singleton (tests + config change)."""
    global _layer
    if _layer is not None:
        try:
            _layer.stop()
        except Exception:
            pass
    _layer = None


def make_test_voice_layer() -> VoiceLayer:
    """
    Factory for tests: all mocks, no model load, no microphone, no network.
    """
    return VoiceLayer(
        transcriber=MockTranscriber(),
        synthesizer=MockSynthesizer(),
        wake_detector=MockWakeWordDetector(),
    )


__all__ = [
    "VoiceLayer",
    "VoiceStatus",
    "get_voice_layer",
    "make_test_voice_layer",
    "reset_voice_layer",
]
