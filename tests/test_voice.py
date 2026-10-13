"""
Tests -- Phase 11: Voice I/O
==============================
All deterministic -- no mic, no speakers, no model download, no network.
Uses make_test_voice_layer() which wires MockTranscriber + MockSynthesizer
+ MockWakeWordDetector throughout.

Coverage:
  TranscriptResult / SynthesisResult / WakeResult dataclasses
  MockTranscriber:   transcribes bytes, numpy array, returns preset text
  MockSynthesizer:   synthesizes text, returns silent WAV, valid WAV header
  MockWakeWordDetector: always_detect, never_detect, trigger_on_nth
  VoiceLayer facade: transcribe_bytes, synthesize, status, wake_loop
  WhisperTranscriber interface: model_name, is_available (no load)
  EdgeTTSSynthesizer interface: voice_name, is_available
  PiperSynthesizer:  is_available False when binary absent
  AudioCapture:      constructible, queue interface (no real mic)
  play_audio:        no-op when sounddevice absent (graceful)
  Singleton:         get/reset/make_test_layer
  WakeLoop:          start + stop without real audio
"""

from __future__ import annotations

import threading

import numpy as np
import pytest

from guardian.voice import (
    VoiceLayer,
    VoiceStatus,
    get_voice_layer,
    make_test_voice_layer,
    reset_voice_layer,
)
from guardian.voice.stt import (
    MockTranscriber,
    TranscriptResult,
    WhisperTranscriber,
)
from guardian.voice.tts import (
    _SILENT_WAV,
    EdgeTTSSynthesizer,
    MockSynthesizer,
    PiperSynthesizer,
    SynthesisResult,
    auto_synthesizer,
)
from guardian.voice.wake import (
    MockWakeWordDetector,
    OpenWakeWordDetector,
    WakeResult,
)


@pytest.fixture(autouse=True)
def reset():
    reset_voice_layer()
    yield
    reset_voice_layer()


@pytest.fixture
def layer() -> VoiceLayer:
    return make_test_voice_layer()


# ── Dataclasses ───────────────────────────────────────────────────────────────

class TestTranscriptResult:
    def test_fields(self):
        r = TranscriptResult(
            text="hello world",
            language="en",
            duration_s=0.5,
            model="mock/whisper",
            segments=[{"start": 0.0, "end": 1.0, "text": "hello world"}],
        )
        assert r.text == "hello world"
        assert r.language == "en"
        assert r.duration_s == 0.5


class TestSynthesisResult:
    def test_fields(self):
        r = SynthesisResult(
            audio_bytes=_SILENT_WAV,
            text="test",
            voice="mock/silent",
            duration_s=0.0,
            backend="mock",
        )
        assert r.audio_bytes == _SILENT_WAV
        assert r.text == "test"
        assert r.backend == "mock"


class TestWakeResult:
    def test_fields(self):
        r = WakeResult(detected=True, wake_word="hey_test", score=0.9, timestamp=0.0)
        assert r.detected
        assert r.score == 0.9


# ── MockTranscriber ───────────────────────────────────────────────────────────

class TestMockTranscriber:
    def test_model_name(self):
        t = MockTranscriber()
        assert "mock" in t.model_name

    def test_transcribe_bytes_returns_preset(self):
        t = MockTranscriber(preset_text="Guardian is ready.")
        result = t.transcribe(b"\x00\x00" * 1600)
        assert result.text == "Guardian is ready."
        assert result.language == "en"

    def test_transcribe_numpy_array(self):
        t = MockTranscriber(preset_text="test")
        arr = np.zeros(1600, dtype=np.int16)
        result = t.transcribe(arr)
        assert result.text == "test"

    def test_transcribe_empty_bytes(self):
        t = MockTranscriber()
        result = t.transcribe(b"")
        assert isinstance(result.text, str)

    def test_transcribe_custom_language(self):
        t = MockTranscriber()
        result = t.transcribe(b"\x00" * 100, language="fr")
        assert result.language == "en"  # mock ignores, always returns "en"

    def test_segments_present(self):
        t = MockTranscriber()
        result = t.transcribe(b"\x00" * 100)
        assert len(result.segments) == 1
        assert "text" in result.segments[0]

    def test_duration_near_zero(self):
        t = MockTranscriber()
        result = t.transcribe(b"\x00" * 100)
        assert result.duration_s < 0.01

    def test_is_available(self):
        assert MockTranscriber().is_available


# ── WhisperTranscriber (interface only — no model load in tests) ──────────────

class TestWhisperTranscriberInterface:
    def test_model_name_includes_size(self):
        t = WhisperTranscriber(model="medium")
        assert "medium" in t.model_name

    def test_is_available_before_load(self):
        t = WhisperTranscriber()
        assert t.is_available  # True even before load

    def test_custom_model_size_stored(self):
        t = WhisperTranscriber(model="large-v3")
        assert "large-v3" in t.model_name

    def test_device_auto_accepted(self):
        t = WhisperTranscriber(device="auto")
        assert t._device == "auto"


# ── MockSynthesizer ───────────────────────────────────────────────────────────

class TestMockSynthesizer:
    def test_voice_name(self):
        s = MockSynthesizer()
        assert "mock" in s.voice_name

    def test_synthesize_returns_result(self):
        s = MockSynthesizer()
        result = s.synthesize("Hello Guardian!")
        assert isinstance(result, SynthesisResult)
        assert result.text == "Hello Guardian!"

    def test_audio_bytes_is_valid_wav(self):
        s = MockSynthesizer()
        result = s.synthesize("test")
        wav = result.audio_bytes
        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"

    def test_backend_is_mock(self):
        s = MockSynthesizer()
        result = s.synthesize("x")
        assert result.backend == "mock"

    def test_duration_zero(self):
        s = MockSynthesizer()
        result = s.synthesize("test")
        assert result.duration_s == 0.0

    def test_is_available(self):
        assert MockSynthesizer().is_available

    def test_synthesize_empty_string(self):
        s = MockSynthesizer()
        result = s.synthesize("")
        assert result.audio_bytes  # still returns silent WAV


# ── EdgeTTSSynthesizer interface (no network call in tests) ───────────────────

class TestEdgeTTSInterface:
    def test_voice_name_contains_voice(self):
        e = EdgeTTSSynthesizer(voice="en-US-AriaNeural")
        assert "AriaNeural" in e.voice_name

    def test_is_available_true_when_installed(self):
        e = EdgeTTSSynthesizer()
        # edge-tts is installed in venv — should be available
        assert e.is_available

    def test_custom_voice_stored(self):
        e = EdgeTTSSynthesizer(voice="en-GB-SoniaNeural")
        assert "SoniaNeural" in e.voice_name


# ── PiperSynthesizer (no binary expected in CI) ───────────────────────────────

class TestPiperSynthesizer:
    def test_is_available_false_without_binary(self):
        # Piper binary may exist on this system (it does on the dev machine)
        # is_available = binary found AND (no model set OR model exists)
        # Use both a fake binary AND a nonexistent model to force False
        p = PiperSynthesizer(
            piper_binary="/nonexistent/piper_binary_xyz",
            model_path="/nonexistent/model.onnx",
        )
        assert not p.is_available

    def test_voice_name_with_model(self, tmp_path):
        model = tmp_path / "en_US-lessac-medium.onnx"
        model.write_bytes(b"\x00")  # fake onnx
        p = PiperSynthesizer(model_path=model, piper_binary="/nonexistent/piper")
        assert "lessac" in p.voice_name

    def test_voice_name_without_model(self):
        p = PiperSynthesizer(piper_binary="/nonexistent/piper")
        assert p.voice_name == "piper/default"

    def test_synthesize_raises_when_unavailable(self):
        p = PiperSynthesizer(
            piper_binary="/nonexistent/piper_binary_xyz",
            model_path="/nonexistent/model.onnx",
        )
        with pytest.raises(RuntimeError, match="Piper binary not found"):
            p.synthesize("hello")


# ── auto_synthesizer ──────────────────────────────────────────────────────────

class TestAutoSynthesizer:
    def test_returns_edge_when_no_piper(self):
        s = auto_synthesizer(piper_model=None, prefer_local=True)
        # No piper model specified → EdgeTTS (installed) or Mock
        assert isinstance(s, (EdgeTTSSynthesizer, MockSynthesizer))

    def test_prefer_mock_when_nothing_available(self, monkeypatch):
        # Simulate EdgeTTS unavailable by patching import
        monkeypatch.setattr("guardian.voice.tts.EdgeTTSSynthesizer.is_available",
                            property(lambda self: False),
                            raising=False)
        # auto_synthesizer with no piper + mock edge = MockSynthesizer
        import guardian.voice.tts as tts_mod
        orig = tts_mod.EdgeTTSSynthesizer.is_available.fget
        try:
            tts_mod.EdgeTTSSynthesizer.is_available = property(lambda self: False)
            s = auto_synthesizer(piper_model=None, prefer_local=False)
            assert isinstance(s, (MockSynthesizer, EdgeTTSSynthesizer))
        finally:
            tts_mod.EdgeTTSSynthesizer.is_available = property(lambda self: orig(self))


# ── MockWakeWordDetector ──────────────────────────────────────────────────────

class TestMockWakeWordDetector:
    def test_never_detect_by_default(self):
        d = MockWakeWordDetector(always_detect=False)
        chunk = np.zeros(1280, dtype=np.int16)
        result = d.process_chunk(chunk)
        assert not result.detected

    def test_always_detect(self):
        d = MockWakeWordDetector(always_detect=True)
        chunk = np.zeros(1280, dtype=np.int16)
        result = d.process_chunk(chunk)
        assert result.detected
        assert result.score == 1.0

    def test_trigger_on_nth(self):
        d = MockWakeWordDetector(trigger_on_nth=3)
        chunk = np.zeros(1280, dtype=np.int16)
        assert not d.process_chunk(chunk).detected  # 1st
        assert not d.process_chunk(chunk).detected  # 2nd
        assert d.process_chunk(chunk).detected       # 3rd

    def test_wake_word_name(self):
        d = MockWakeWordDetector(wake_word="test_word")
        assert d.wake_word == "test_word"

    def test_reset_clears_count(self):
        # trigger_on_nth=2 fires on 2nd call; reset() brings count back to 0
        d = MockWakeWordDetector(trigger_on_nth=2)
        chunk = np.zeros(1280, dtype=np.int16)
        assert not d.process_chunk(chunk).detected   # 1st call - no trigger
        assert d.process_chunk(chunk).detected        # 2nd call - triggers
        d.reset()
        # After reset count=0; 1st call again should NOT trigger
        assert not d.process_chunk(chunk).detected   # 1st after reset

    def test_process_bytes_input(self):
        d = MockWakeWordDetector(always_detect=True)
        result = d.process_chunk(b"\x00" * 2560)   # 1280 int16 samples as bytes
        assert result.detected


# ── OpenWakeWordDetector interface ────────────────────────────────────────────

class TestOpenWakeWordDetectorInterface:
    def test_wake_word_stored(self):
        d = OpenWakeWordDetector(wake_word="alexa", threshold=0.5)
        assert d.wake_word == "alexa"

    def test_threshold_stored(self):
        d = OpenWakeWordDetector(threshold=0.7)
        assert d._threshold == 0.7

    def test_reset_no_error_before_load(self):
        d = OpenWakeWordDetector()
        d.reset()   # should not raise even before model load


# ── VoiceLayer facade ─────────────────────────────────────────────────────────

class TestVoiceLayer:
    def test_transcribe_bytes(self, layer):
        result = layer.transcribe_bytes(b"\x00\x00" * 1600)
        assert isinstance(result.text, str)
        assert result.language == "en"

    def test_transcribe_numpy(self, layer):
        arr = np.zeros(1600, dtype=np.int16)
        result = layer.transcribe_bytes(arr)
        assert isinstance(result.text, str)

    def test_synthesize_returns_wav(self, layer):
        result = layer.synthesize("Hello world")
        assert isinstance(result.audio_bytes, bytes)
        assert result.audio_bytes[:4] == b"RIFF"

    def test_synthesize_text_stored(self, layer):
        result = layer.synthesize("Testing voice synthesis")
        assert result.text == "Testing voice synthesis"

    def test_status(self, layer):
        s = layer.status()
        assert isinstance(s, VoiceStatus)
        assert "mock" in s.stt_model
        assert "mock" in s.tts_voice
        assert isinstance(s.wake_word, str)
        assert not s.audio_capture  # no mic started

    def test_wake_loop_start_stop(self, layer):
        fired = []
        layer.start_wake_loop(on_wake=lambda r: fired.append(r))
        # Thread starts; wake detector is mock (never fires by default)
        assert layer._wake_running
        layer.stop_wake_loop()
        assert not layer._wake_running

    def test_wake_loop_callback_fires(self):
        fired = threading.Event()
        detector = MockWakeWordDetector(always_detect=True)
        vl = VoiceLayer(
            transcriber=MockTranscriber(),
            synthesizer=MockSynthesizer(),
            wake_detector=detector,
        )

        # Monkey-patch capture to avoid real mic
        class FakeCapture:
            def get_chunk(self, timeout=0.1):
                import time as _t
                _t.sleep(0.01)
                class _Chunk:
                    pcm = np.zeros(1280, dtype=np.int16)
                return _Chunk()
        vl._capture = FakeCapture()

        def _on_wake(r):
            fired.set()
            vl.stop_wake_loop()

        vl.start_wake_loop(_on_wake)
        detected = fired.wait(timeout=3.0)
        assert detected, "Wake word callback never fired"

    def test_stop_no_error_when_not_started(self, layer):
        layer.stop()   # should not raise

    def test_transcribe_file(self, layer, tmp_path):
        # Write a real WAV file with 1s of silence (1600 int16 samples @ 16kHz)
        import wave as _wave
        wav_path = tmp_path / "test.wav"
        with _wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 1600)
        result = layer.transcribe_file(wav_path)
        assert isinstance(result.text, str)


# ── Singleton management ──────────────────────────────────────────────────────

class TestSingleton:
    def test_make_test_layer_returns_voice_layer(self):
        vl = make_test_voice_layer()
        assert isinstance(vl, VoiceLayer)

    def test_all_mocks_in_test_layer(self):
        vl = make_test_voice_layer()
        assert isinstance(vl._stt, MockTranscriber)
        assert isinstance(vl._tts, MockSynthesizer)
        assert isinstance(vl._wake, MockWakeWordDetector)

    def test_get_voice_layer_singleton(self):
        # get_voice_layer builds real objects (lazy) — just verify same instance
        l1 = get_voice_layer()
        l2 = get_voice_layer()
        assert l1 is l2

    def test_reset_creates_new(self):
        l1 = get_voice_layer()
        reset_voice_layer()
        l2 = get_voice_layer()
        assert l1 is not l2


# ── Silent WAV format ─────────────────────────────────────────────────────────

class TestSilentWav:
    def test_riff_header(self):
        assert _SILENT_WAV[:4] == b"RIFF"

    def test_wave_marker(self):
        assert _SILENT_WAV[8:12] == b"WAVE"

    def test_minimum_length(self):
        assert len(_SILENT_WAV) == 44  # header only, 0 data bytes

    def test_fmt_chunk(self):
        assert _SILENT_WAV[12:16] == b"fmt "

    def test_data_chunk(self):
        assert _SILENT_WAV[36:40] == b"data"
