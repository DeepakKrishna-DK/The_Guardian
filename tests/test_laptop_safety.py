import os
import pytest
import time
from guardian.laptop.safety import (
    is_blocklisted,
    trigger_kill_switch,
    reset_kill_switch,
    is_kill_triggered,
    show_indicator,
    hide_indicator,
    register_kill_switch
)
from guardian.config.settings import settings

def test_feature_flag_default_off():
    # Setting should be OFF by default
    assert settings.enable_laptop_control is False

def test_blocklist_matching():
    # True positives
    assert is_blocklisted("1Password")
    assert is_blocklisted("Windows Defender Security Center")
    assert is_blocklisted("Administrator: Command Prompt")
    assert is_blocklisted("paypal login")
    
    # True negatives
    assert not is_blocklisted("Notepad")
    assert not is_blocklisted("Calculator")
    assert not is_blocklisted("Visual Studio Code")

def test_kill_switch_halts_simulated_loop():
    reset_kill_switch()
    assert not is_kill_triggered()
    
    # Simulate hotkey trigger
    trigger_kill_switch()
    assert is_kill_triggered()
    
    # Simulated loop
    loop_ran = False
    for i in range(10):
        if is_kill_triggered():
            break
        loop_ran = True
        
    assert loop_ran is False, "Loop should not have run after kill switch was triggered"
    reset_kill_switch()

@pytest.mark.skipif("CI" in os.environ and os.name != "nt", reason="Headless Linux CI has no graphical display for Tkinter")
def test_indicator_state_transitions():
    show_indicator()
    time.sleep(0.5) # Give tk time to start
    from guardian.laptop.safety import _INDICATOR_THREAD
    assert _INDICATOR_THREAD is not None
    assert _INDICATOR_THREAD.is_alive()
    
    hide_indicator()
    time.sleep(0.5)
    from guardian.laptop.safety import _INDICATOR_ROOT
    assert _INDICATOR_ROOT is None
