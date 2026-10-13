"""
Guardian Voice -- Audio Capture
=================================
Microphone input using sounddevice (MIT).

AudioCapture wraps sounddevice's InputStream for push-based audio:
  - Captures 16kHz mono 16-bit PCM (Whisper's native format)
  - Delivers fixed-size chunks via a queue for wake-word detection
  - Delivers variable-length recordings for STT after wake detected

Designed for:
  - Wake word loop: small 80ms chunks → WakeWordDetector
  - Speech recording: larger frames until silence → Transcriber

Apache-2.0. sounddevice is MIT.
"""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from guardian.logging.logger import get_logger

log = get_logger(__name__)

_SAMPLE_RATE   = 16000          # Hz — Whisper native
_CHANNELS      = 1              # mono
_DTYPE         = "int16"
_CHUNK_MS      = 80             # ms per wake-word chunk (1280 samples)
_CHUNK_SAMPLES = int(_SAMPLE_RATE * _CHUNK_MS / 1000)
_SILENCE_THRESHOLD = 300        # RMS below this = silence (int16 scale)
_SILENCE_CHUNKS    = 25         # ~2s of silence to end recording


@dataclass
class AudioChunk:
    pcm: np.ndarray             # int16 shape (N,)
    timestamp: float = field(default_factory=time.monotonic)


class AudioCapture:
    """
    Microphone capture using sounddevice (MIT).

    Usage:
        cap = AudioCapture()
        cap.start()
        while True:
            chunk = cap.get_chunk(timeout=0.1)
            if chunk:
                # process chunk for wake word
        cap.stop()

    Or use record_utterance() for a one-shot blocking recording.
    """

    def __init__(
        self,
        sample_rate: int = _SAMPLE_RATE,
        chunk_samples: int = _CHUNK_SAMPLES,
    ) -> None:
        self._sr      = sample_rate
        self._chunk   = chunk_samples
        self._q: queue.Queue[AudioChunk] = queue.Queue(maxsize=50)
        self._stream: Any | None = None
        self._running = False

    def start(self) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            raise ImportError("sounddevice required: pip install sounddevice")

        self._running = True

        def _callback(indata: np.ndarray, frames: int, t: Any, status: Any) -> None:
            if status:
                log.debug(f"AudioCapture status: {status}")
            arr = indata[:, 0].copy()   # mono channel as 1D
            chunk = AudioChunk(pcm=arr)
            try:
                self._q.put_nowait(chunk)
            except queue.Full:
                pass  # drop oldest if queue full

        import sounddevice as sd
        self._stream = sd.InputStream(
            samplerate=self._sr,
            channels=_CHANNELS,
            dtype=_DTYPE,
            blocksize=self._chunk,
            callback=_callback,
        )
        self._stream.start()
        log.info(f"AudioCapture started ({self._sr}Hz, {self._chunk} samples/chunk)")

    def stop(self) -> None:
        self._running = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        log.info("AudioCapture stopped")

    def get_chunk(self, timeout: float = 0.1) -> AudioChunk | None:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def flush(self) -> None:
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    def record_utterance(
        self,
        max_seconds: float = 10.0,
        silence_chunks: int = _SILENCE_CHUNKS,
        silence_threshold: int = _SILENCE_THRESHOLD,
    ) -> np.ndarray:
        """
        Record until silence detected or max_seconds reached.
        Returns concatenated int16 PCM array.
        """
        self.flush()
        frames: list[np.ndarray] = []
        silent = 0
        deadline = time.monotonic() + max_seconds

        while time.monotonic() < deadline:
            chunk = self.get_chunk(timeout=0.1)
            if chunk is None:
                continue
            frames.append(chunk.pcm)
            rms = int(np.sqrt(np.mean(chunk.pcm.astype(np.float32) ** 2)))
            if rms < silence_threshold:
                silent += 1
                if silent >= silence_chunks:
                    break
            else:
                silent = 0

        return np.concatenate(frames) if frames else np.zeros(self._chunk, dtype=np.int16)


def play_audio(wav_bytes: bytes, blocking: bool = True) -> None:
    """
    Play WAV audio bytes through the default speaker.
    Uses sounddevice + soundfile (both MIT/BSD-3).
    """
    try:
        import io

        import sounddevice as sd
        import soundfile as sf

        buf = io.BytesIO(wav_bytes)
        data, sr = sf.read(buf, dtype="float32")
        if data.ndim == 1:
            data = data[:, np.newaxis]
        sd.play(data, samplerate=sr)
        if blocking:
            sd.wait()
    except Exception as exc:
        log.warning(f"play_audio failed: {exc}")
