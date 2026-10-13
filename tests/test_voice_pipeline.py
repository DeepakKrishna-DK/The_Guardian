import pytest
import time
from guardian.core.orchestrator import GuardianCore
from guardian.core.session import Session
from guardian.model.backends.mock import MockBackend
from guardian.voice.pipeline import VoicePipeline, VoiceState
from guardian.voice import make_test_voice_layer, reset_voice_layer

@pytest.fixture(autouse=True)
def _reset_voice():
    import guardian.voice as gv
    gv.reset_voice_layer()
    gv._layer = gv.make_test_voice_layer()
    yield
    gv.reset_voice_layer()

def test_pipeline_state_transitions():
    core = GuardianCore(model=MockBackend())
    session = Session()
    
    pipeline = VoicePipeline(core=core, session=session)
    
    events = []
    def callback(state, event):
        events.append(event)
    
    pipeline.on_state_change(callback)
    
    # Send dummy audio to trigger the pipeline
    pipeline.process_audio(b"\x00\x00" * 1600)
    
    # Expected transitions: TRANSCRIBING -> THINKING -> SPEAKING -> IDLE
    assert len(events) >= 4
    
    assert events[0]["event"] == "transcribing"
    assert events[1]["event"] == "thinking"
    assert events[2]["event"] == "speaking"
    
    # speaking event should have audio_b64
    assert "audio_b64" in events[2]
    
    assert events[-1]["event"] == "idle"

def test_pipeline_no_bypass():
    """
    Test that Voice-triggered requests go through the SAME choke point as text.
    (guardrails -> PolicyEngine -> audit log)
    We can verify this by injecting a prompt that violates the mock policy or checking the core processing.
    """
    from guardian.policy.engine import get_policy_engine
    core = GuardianCore(model=MockBackend())
    session = Session()
    
    pipeline = VoicePipeline(core=core, session=session)
    
    # Spy on PolicyEngine.evaluate_model_call
    engine = get_policy_engine()
    original_eval = engine.evaluate_model_call
    called = False
    
    def spy_eval(*args, **kwargs):
        nonlocal called
        called = True
        return original_eval(*args, **kwargs)
        
    engine.evaluate_model_call = spy_eval
    
    pipeline.process_audio(b"\x00\x00" * 1600)
    
    assert called, "VoicePipeline bypassed the policy engine!"
    
    # restore
    engine.evaluate_model_call = original_eval
