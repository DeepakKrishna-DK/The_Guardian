import pytest
from guardian.laptop.agent import LaptopAgent
from guardian.core.collab import EscalationReason

def test_laptop_agent_scope():
    agent = LaptopAgent()
    assert "laptop_click" in agent.scope.allowed_tools
    assert "laptop_screenshot" in agent.scope.allowed_tools
    # Not exposed to other agents implicitly, since scope is explicit

def test_laptop_escalation():
    agent = LaptopAgent()
    
    # Ambiguous instruction should return Escalation
    esc1 = agent.evaluate_instruction("Please click something on the screen.")
    assert esc1 is not None
    assert esc1.reason == EscalationReason.AMBIGUOUS_SCOPE
    
    esc2 = agent.evaluate_instruction("Can you type something for me?")
    assert esc2 is not None
    
    # Specific instruction should be fine
    esc3 = agent.evaluate_instruction("Click the 'Save' button in Notepad.")
    assert esc3 is None
