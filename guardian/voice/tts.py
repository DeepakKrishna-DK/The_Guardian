"""
Guardian Voice -- Text-to-Speech (TTS)
========================================
Synthesizer ABC with three implementations:

  PiperSynthesizer   -- Piper TTS via subprocess (GPL-3.0 isolation).
                        Finds 'piper' binary in PATH or GUARDIAN_PIPER_PATH.
                        Accepts raw text, produces WAV audio bytes.
                        No Piper code is imported -- pure subprocess.

  EdgeTTSSynthesizer -- Microsoft Edge TTS (edge-tts, MIT).
                        Cloud-based, no API key, near-human quality.
                        Requires internet. ~150ms latency.
                        Best for 'feels like it has life' requirement.

  MockSynthesizer    -- Returns silent WAV bytes. For tests and offline.

Selection logic (auto):
  1. If GUARDIAN_PIPER_PATH set → PiperSynthesizer
  2. If 'piper' in PATH → PiperSynthesizer
  3. If internet available → EdgeTTSSynthesizer (cloud, high quality)
  4. → MockSynthesizer (silent, graceful degradation)

Apache-2.0. edge-tts is MIT. Piper is GPL-3.0, run as subprocess only.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import struct
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from guardian.logging.logger import get_logger

log = get_logger(__name__)

_SILENT_WAV = (
    # Minimal valid WAV header: 44 bytes, 0 data samples, 16kHz mono 16-bit
    b'RIFF' + struct.pack('<I', 36) +
    b'WAVE' +
    b'fmt ' + struct.pack('<IHHIIHH', 16, 1, 1, 16000, 32000, 2, 16) +
    b'data' + struct.pack('<I', 0)
)


@dataclass
class SynthesisResult:
    audio_bytes: bytes        # WAV-encoded audio
    text: str
    voice: str
    duration_s: float
    backend: str


class Synthesizer(ABC):
    """Abstract base for all TTS backends."""

    @abstractmethod
    def synthesize(self, text: str) -> SynthesisResult:
        ...

    @property
    @abstractmethod
    def voice_name(self) -> str:
        ...

    @property
    def is_available(self) -> bool:
        return True


# ── Piper TTS (subprocess, GPL-3.0 isolation) ─────────────────────────────────

class PiperSynthesizer(Synthesizer):
    """
    Piper TTS invoked as an external subprocess.

    Piper (OHF-Voice/piper1-gpl) is GPL-3.0. By running it as a subprocess
    rather than importing its Python package, our Apache-2.0 code remains
    unaffected. This is the standard approach for invoking GPL tools.

    Binary discovery order:
      1. GUARDIAN_PIPER_PATH env var (full path to piper executable)
      2. 'piper' in PATH
      3. Common install locations

    Voice model: path to .onnx file. Download from:
      https://huggingface.co/rhasspy/piper-voices
      Check each model's license before use.
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        piper_binary: str | Path | None = None,
        speaker_id: int | None = None,
    ) -> None:
        self._binary = self._find_binary(piper_binary)
        self._model  = Path(model_path) if model_path else None
        self._speaker = speaker_id

    @staticmethod
    def _find_binary(override: str | Path | None) -> str | None:
        if override:
            return str(override)
        env_path = os.environ.get("GUARDIAN_PIPER_PATH")
        if env_path:
            return env_path
        found = shutil.which("piper")
        if found:
            return found
        # Common Windows locations
        for candidate in [
            r"C:\Program Files\piper\piper.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\piper\piper.exe"),
        ]:
            if Path(candidate).exists():
                return candidate
        return None

    @property
    def is_available(self) -> bool:
        return self._binary is not None and (
            self._model is None or self._model.exists()
        )

    @property
    def voice_name(self) -> str:
        if self._model:
            return f"piper/{self._model.stem}"
        return "piper/default"

    def synthesize(self, text: str) -> SynthesisResult:
        if not self.is_available:
            raise RuntimeError(
                "Piper binary not found. Set GUARDIAN_PIPER_PATH or install piper. "
                "Download from: https://github.com/rhasspy/piper/releases"
            )
        t0 = time.monotonic()
        cmd = [self._binary]
        if self._model:
            cmd += ["--model", str(self._model)]
        if self._speaker is not None:
            cmd += ["--speaker", str(self._speaker)]
        cmd += ["--output_raw"]   # output raw PCM to stdout

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_f:
            wav_path = wav_f.name

        try:
            cmd = [self._binary]
            if self._model:
                cmd += ["--model", str(self._model)]
            if self._speaker is not None:
                cmd += ["--speaker", str(self._speaker)]
            cmd += ["--output_file", wav_path]

            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"Piper failed (rc={proc.returncode}): {proc.stderr.decode()[:200]}")

            with open(wav_path, "rb") as f:
                audio = f.read()
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

        elapsed = time.monotonic() - t0
        log.debug(f"Piper synthesized {len(text)} chars in {elapsed:.2f}s")
        return SynthesisResult(
            audio_bytes=audio,
            text=text,
            voice=self.voice_name,
            duration_s=elapsed,
            backend="piper",
        )


# ── Edge TTS (MIT, cloud, near-human quality) ─────────────────────────────────

class EdgeTTSSynthesizer(Synthesizer):
    """
    Microsoft Edge TTS via edge-tts (MIT).
    Requires internet. No API key.

    Quality: near-human, expressive, natural cadence.
    Latency: ~150-500ms depending on network.

    Default voice: en-US-AriaNeural (female, natural, expressive).
    Other good choices:
      en-US-GuyNeural        (male, warm)
      en-GB-SoniaNeural      (British female)
      en-US-JennyNeural      (female, conversational)
      en-IN-NeerjaNeural     (Indian English female)

    Find all voices: edge-tts --list-voices
    """

    # Default: Aria — expressive, conversational, natural
    _DEFAULT_VOICE = "en-US-AriaNeural"

    def __init__(
        self,
        voice: str = _DEFAULT_VOICE,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
    ) -> None:
        self._voice   = voice
        self._rate    = rate
        self._volume  = volume
        self._pitch   = pitch

    @property
    def voice_name(self) -> str:
        return f"edge/{self._voice}"

    @property
    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def synthesize(self, text: str) -> SynthesisResult:
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            raise ImportError("edge-tts required: pip install edge-tts")

        t0 = time.monotonic()
        audio = asyncio.run(self._async_synth(text))
        elapsed = time.monotonic() - t0
        log.debug(f"EdgeTTS synthesized {len(text)} chars in {elapsed:.2f}s")
        return SynthesisResult(
            audio_bytes=audio,
            text=text,
            voice=self.voice_name,
            duration_s=elapsed,
            backend="edge-tts",
        )

    async def _async_synth(self, text: str) -> bytes:
        import edge_tts
        communicate = edge_tts.Communicate(
            text,
            voice=self._voice,
            rate=self._rate,
            volume=self._volume,
            pitch=self._pitch,
        )
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)


# ── Mock Synthesizer (tests) ──────────────────────────────────────────────────

class MockSynthesizer(Synthesizer):
    """Returns silent WAV bytes. No model load, no network. For tests."""

    def __init__(self, voice: str = "mock/silent") -> None:
        self._voice = voice

    @property
    def voice_name(self) -> str:
        return self._voice

    def synthesize(self, text: str) -> SynthesisResult:
        return SynthesisResult(
            audio_bytes=_SILENT_WAV,
            text=text,
            voice=self._voice,
            duration_s=0.0,
            backend="mock",
        )


# ── Factory ───────────────────────────────────────────────────────────────────

def auto_synthesizer(
    piper_model: str | Path | None = None,
    voice: str = EdgeTTSSynthesizer._DEFAULT_VOICE,
    prefer_local: bool = True,
) -> Synthesizer:
    """
    Auto-select best available TTS backend:
    1. PiperSynthesizer if piper binary found and model set (local, offline)
    2. EdgeTTSSynthesizer if internet available (cloud, near-human)
    3. MockSynthesizer (silent fallback)
    """
    piper = PiperSynthesizer(model_path=piper_model)
    if prefer_local and piper.is_available and piper_model:
        log.info("TTS backend: Piper (local)")
        return piper

    edge = EdgeTTSSynthesizer(voice=voice)
    if edge.is_available:
        log.info(f"TTS backend: Edge TTS ({voice})")
        return edge

    log.warning("TTS: No backend available, using silent mock")
    return MockSynthesizer()
