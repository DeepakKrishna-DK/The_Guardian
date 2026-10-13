"""
Guardian Voice -- Wake Word Detection
=======================================
WakeWordDetector ABC with two implementations:

  OpenWakeWordDetector -- openwakeword (Apache 2.0), lazy-loaded.
                          Uses TFLite models. Pre-trained models:
                            'alexa'          (permissive)
                            'hey_jarvis'     (permissive)
                            'hey_mycroft'    (permissive)
                          NOTE: Check each model's license individually.
                          TFLite runtime is Apache 2.0.

  MockWakeWordDetector -- Always or never detects (configurable). Tests only.

Usage in voice session:
    detector = OpenWakeWordDetector(wake_word='hey_mycroft')
    # Feed 80ms chunks of 16kHz int16 PCM
    if detector.process_chunk(pcm_chunk):
        # Wake word detected -- start recording
        ...

Apache-2.0. openwakeword is Apache 2.0.
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
class WakeResult:
    detected: bool
    wake_word: str
    score: float            # 0.0–1.0 confidence
    timestamp: float        # monotonic time of detection


class WakeWordDetector(ABC):
    """Abstract base for wake-word detection."""

    @abstractmethod
    def process_chunk(self, pcm_chunk: bytes | np.ndarray) -> WakeResult:
        """
        Process a 80ms chunk of 16kHz mono 16-bit PCM audio.
        Returns WakeResult with detected=True if wake word fired.
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset internal state (call after each detected event)."""
        ...

    @property
    @abstractmethod
    def wake_word(self) -> str:
        ...

    @property
    def is_available(self) -> bool:
        return True


class OpenWakeWordDetector(WakeWordDetector):
    """
    openwakeword (Apache 2.0) based detector.
    Lazy-loads TFLite model on first process_chunk call.

    Supported pre-trained words (check individual model licenses):
      'alexa', 'hey_jarvis', 'hey_mycroft', 'ok_nabu'

    threshold: float 0.0-1.0, sensitivity (default 0.5)
               Lower = more sensitive (more false positives)
               Higher = less sensitive (fewer false positives)
    """

    _CHUNK_SAMPLES = 1280   # 80ms at 16kHz

    def __init__(
        self,
        wake_word: str = "hey_mycroft",
        threshold: float = 0.5,
    ) -> None:
        self._wake_word = wake_word
        self._threshold = threshold
        self._model: Any | None = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from openwakeword.model import Model
            log.info(f"Loading openWakeWord model for '{self._wake_word}'")
            self._model = Model(
                wakeword_models=[self._wake_word],
                inference_framework="onnx",
            )
            log.info("Wake word model loaded")
        except ImportError:
            raise ImportError("openwakeword required: pip install openwakeword")
        except Exception as e:
            raise RuntimeError(f"Failed to load wake word '{self._wake_word}': {e}")

    @property
    def wake_word(self) -> str:
        return self._wake_word

    def process_chunk(self, pcm_chunk: bytes | np.ndarray) -> WakeResult:
        self._load()
        if isinstance(pcm_chunk, (bytes, bytearray)):
            arr = np.frombuffer(pcm_chunk, dtype=np.int16)
        else:
            arr = pcm_chunk.astype(np.int16)

        # openwakeword expects (N,) int16 array
        prediction = self._model.predict(arr)
        scores = prediction.get(self._wake_word, {})
        score = float(scores) if isinstance(scores, (int, float)) else 0.0
        # Handle dict/array return from openwakeword
        if hasattr(scores, '__iter__') and not isinstance(scores, (str, float)):
            try:
                score = float(list(scores)[-1])
            except Exception:
                score = 0.0

        detected = score >= self._threshold
        if detected:
            log.info(f"Wake word '{self._wake_word}' detected (score={score:.3f})")
        return WakeResult(
            detected=detected,
            wake_word=self._wake_word,
            score=score,
            timestamp=time.monotonic(),
        )

    def reset(self) -> None:
        if self._model is not None:
            try:
                self._model.reset()
            except AttributeError:
                pass  # some versions don't have reset()


class MockWakeWordDetector(WakeWordDetector):
    """
    Configurable mock for tests.
    always_detect=True: every chunk triggers wake.
    always_detect=False: never triggers.
    trigger_on_nth: trigger only on Nth process_chunk call.
    """

    def __init__(
        self,
        always_detect: bool = False,
        trigger_on_nth: int | None = None,
        wake_word: str = "mock_wake",
    ) -> None:
        self._always   = always_detect
        self._nth      = trigger_on_nth
        self._ww       = wake_word
        self._call_count = 0

    @property
    def wake_word(self) -> str:
        return self._ww

    def process_chunk(self, pcm_chunk: bytes | np.ndarray) -> WakeResult:
        self._call_count += 1
        detected = self._always or (
            self._nth is not None and self._call_count == self._nth
        )
        return WakeResult(
            detected=detected,
            wake_word=self._ww,
            score=1.0 if detected else 0.0,
            timestamp=time.monotonic(),
        )

    def reset(self) -> None:
        self._call_count = 0
