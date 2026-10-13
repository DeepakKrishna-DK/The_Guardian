"""
Guardian Voice -- Speech-to-Text (STT)
=======================================
Transcriber ABC with two implementations:

  WhisperTranscriber  -- faster-whisper (MIT), lazy-loaded.
                         Runs locally on CPU or CUDA GPU.
                         Default model: 'base' (fast, offline).
                         Better quality: 'medium' or 'large-v3'.
                         On RTX 3050 4GB, 'medium' fits comfortably.

  MockTranscriber     -- deterministic, no model download. For tests.

Usage:
    t = WhisperTranscriber(model='medium', device='cuda', compute_type='int8')
    result = t.transcribe(audio_data, sample_rate=16000)
    print(result.text)

Audio input: 16-bit PCM bytes OR numpy float32 array, 16 kHz mono.
Apache-2.0. faster-whisper is MIT.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np

from guardian.logging.logger import get_logger

log = get_logger(__name__)


@dataclass
class TranscriptResult:
    text: str
    language: str
    duration_s: float
    model: str
    segments: list[dict]   # raw segment dicts for downstream use


class Transcriber(ABC):
    """Abstract base for all STT backends."""

    @abstractmethod
    def transcribe(
        self,
        audio: bytes | np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> TranscriptResult:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @property
    def is_available(self) -> bool:
        return True


class WhisperTranscriber(Transcriber):
    """
    faster-whisper (MIT) based transcriber.
    Lazy-loads the model on first call.

    model:        'tiny' | 'base' | 'small' | 'medium' | 'large-v3'
    device:       'cpu' | 'cuda' | 'auto'
    compute_type: 'int8' | 'float16' | 'float32'
                  int8 is fastest; float16 on GPU; float32 on CPU fallback.
    """

    def __init__(
        self,
        model: str = "base",
        device: str = "auto",
        compute_type: str = "int8",
        download_root: str | None = None,
    ) -> None:
        self._model_size   = model
        self._device       = device
        self._compute_type = compute_type
        self._download_root = download_root
        self._model: Any | None = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
            device = self._device
            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"
            log.info(f"Loading Whisper '{self._model_size}' on {device} ({self._compute_type})")
            kw: dict[str, Any] = {"device": device, "compute_type": self._compute_type}
            if self._download_root:
                kw["download_root"] = self._download_root
            self._model = WhisperModel(self._model_size, **kw)
            log.info("Whisper model loaded")
        except ImportError:
            raise ImportError("faster-whisper is required: pip install faster-whisper")

    @property
    def model_name(self) -> str:
        return f"whisper/{self._model_size}"

    def transcribe(
        self,
        audio: bytes | np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> TranscriptResult:
        self._load()
        t0 = time.monotonic()

        # Convert bytes to float32 numpy array
        if isinstance(audio, (bytes, bytearray)):
            arr = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            arr = audio.astype(np.float32)
            if arr.max() > 1.0:
                arr = arr / 32768.0

        kw: dict[str, Any] = {"beam_size": 5, "vad_filter": True}
        if language:
            kw["language"] = language
        if initial_prompt:
            kw["initial_prompt"] = initial_prompt

        segments_iter, info = self._model.transcribe(arr, **kw)
        segments = list(segments_iter)
        text = " ".join(s.text.strip() for s in segments).strip()
        elapsed = time.monotonic() - t0

        log.debug(f"Whisper transcribed {len(arr)/sample_rate:.1f}s audio in {elapsed:.2f}s")
        return TranscriptResult(
            text=text,
            language=info.language,
            duration_s=elapsed,
            model=self.model_name,
            segments=[{"start": s.start, "end": s.end, "text": s.text} for s in segments],
        )


class MockTranscriber(Transcriber):
    """
    Deterministic transcriber for tests.
    Returns a preset text without loading any model.
    """

    def __init__(self, preset_text: str = "Hello, this is a test transcription.") -> None:
        self._preset = preset_text

    @property
    def model_name(self) -> str:
        return "mock/whisper"

    def transcribe(
        self,
        audio: bytes | np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> TranscriptResult:
        return TranscriptResult(
            text=self._preset,
            language="en",
            duration_s=0.001,
            model=self.model_name,
            segments=[{"start": 0.0, "end": 1.0, "text": self._preset}],
        )
