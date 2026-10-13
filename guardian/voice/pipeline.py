import re
import threading
import time
from enum import Enum
from typing import Callable, Any

from guardian.logging.logger import get_logger
from guardian.core.orchestrator import GuardianCore
from guardian.core.session import Session
from guardian.voice import get_voice_layer

log = get_logger(__name__)


class VoiceState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"


class VoicePipeline:
    """
    Consolidated Voice Pipeline (M3).
    State machine: idle -> listening -> transcribing -> thinking -> speaking -> idle
    """

    def __init__(self, core: GuardianCore, session: Session) -> None:
        self.core = core
        self.session = session
        self.state = VoiceState.IDLE
        self._layer = get_voice_layer()
        self._on_state_change: list[Callable[[VoiceState, dict[str, Any]], None]] = []
        self._listening = False

    def on_state_change(self, callback: Callable[[VoiceState, dict[str, Any]], None]) -> None:
        self._on_state_change.append(callback)

    def _set_state(self, state: VoiceState, **kwargs) -> None:
        self.state = state
        event = {
            "schema": "guardian.voice.v1",
            "event": state.value,
            "timestamp": time.time(),
            **kwargs,
        }
        log.debug(f"Voice state transition: {state.value}")
        for cb in self._on_state_change:
            try:
                cb(state, event)
            except Exception as e:
                log.error(f"Error in state change callback: {e}")

    def process_audio(self, audio_bytes: bytes) -> None:
        """
        Manually trigger the pipeline with an audio utterance.
        Transitions: transcribing -> thinking -> speaking -> idle
        """
        self._set_state(VoiceState.TRANSCRIBING)
        
        # 1. STT
        t0 = time.monotonic()
        transcript_result = self._layer._stt.transcribe(audio_bytes)
        stt_time = time.monotonic() - t0
        text = transcript_result.text.strip()
        
        if not text:
            self._set_state(VoiceState.IDLE)
            return

        log.info(f"[Voice] Transcribed: '{text}' (in {stt_time:.2f}s)")

        # 2. Think
        self._set_state(VoiceState.THINKING)
        t1 = time.monotonic()
        resp = self.core.process(text, self.session)
        think_time = time.monotonic() - t1

        if resp.error:
            reply = f"Error: {resp.error}"
        else:
            reply = resp.content

        log.info(f"[Voice] Thinking complete in {think_time:.2f}s")

        # 3. Speak
        # Chunk sentence-by-sentence to improve time-to-first-audio (TTFA)
        sentences = re.split(r'(?<=[.!?]) +', reply)
        
        import base64
        
        t2 = time.monotonic()
        first_audio = True
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence: continue
            
            # Synthesize
            synth_res = self._layer._tts.synthesize(sentence)
            
            if first_audio:
                ttfa = time.monotonic() - t2
                log.info(f"[Voice] Time-to-first-audio: {ttfa:.2f}s")
                first_audio = False
            
            # For 'speaking' state, we send the audio directly over the event for the Presence UI
            audio_b64 = base64.b64encode(synth_res.audio_bytes).decode('utf-8')
            
            self._set_state(
                VoiceState.SPEAKING, 
                audio_b64=audio_b64, 
                sentence=sentence,
                duration_s=synth_res.duration_s
            )
            
            # Wait roughly the duration of the audio to simulate speaking time 
            # if we are doing this strictly sequentially.
            # In a real integration, the UI might queue these up.
            time.sleep(synth_res.duration_s * 0.9)

        self._set_state(VoiceState.IDLE)

    def listen_loop(self) -> None:
        """
        Starts the wake-word detector, transitions to listening, then captures utterance.
        (This simulates the full idle -> listening flow).
        """
        # deferred: actual microphone handling
        pass
