import pytest
import time
from guardian.laptop.session import start_session, get_active_session
from guardian.laptop.safety import reset_kill_switch, trigger_kill_switch

def test_session_requires_confirmation():
    session = start_session("test_123", budget=5)
    # Not valid until confirmed
    assert not session.is_valid()
    
    session.confirm_presence()
    assert session.is_valid()
    assert get_active_session() == session

def test_session_budget_exhaustion():
    session = start_session("test_456", budget=3)
    session.confirm_presence()
    
    assert session.record_action() is True
    assert session.record_action() is True
    assert session.record_action() is True
    
    # 4th action should fail due to budget exhaustion
    assert session.record_action() is False
    assert not session.is_valid()

def test_session_timeout():
    session = start_session("test_789", budget=10)
    session.timeout_seconds = 1  # 1 second timeout
    session.confirm_presence()
    
    assert session.is_valid()
    time.sleep(1.1)
    
    assert not session.is_valid()

def test_session_kill_switch():
    reset_kill_switch()
    session = start_session("test_000", budget=10)
    session.confirm_presence()
    
    assert session.is_valid()
    
    trigger_kill_switch()
    assert not session.is_valid()
    reset_kill_switch()
