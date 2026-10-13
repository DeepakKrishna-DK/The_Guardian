import pytest
import os
from guardian.core.orchestrator import GuardianCore, Session
from guardian.prompts import GUARDIAN_SYSTEM_PROMPT
from guardian.model.registry import get_registry

# Skip if no real models are available
def pytest_collection_modifyitems(config, items):
    # This just ensures we can mark tests
    pass

@pytest.mark.agent_eval
def test_agent_eval_synthesis_capabilities():
    # Only run if a real model backend is configured in env
    if not os.environ.get("GUARDIAN_MODEL_BACKEND") and not os.environ.get("GUARDIAN_GROQ_API_KEY") and not os.environ.get("GUARDIAN_GOOGLE_API_KEY"):
        pytest.skip("No real model configured for agent eval")
        
    registry = get_registry()
    try:
        model = registry.get_available()
    except Exception:
        pytest.skip("No model available for agent eval")
        
    # If it's mock, we shouldn't really run an "actual outcome" test unless we just assert it doesn't crash
    if model.get_info().provider == "mock":
        pytest.skip("Mock model not suitable for real agent eval")

    core = GuardianCore(model=model, enable_self_critique=False)
    session = Session()

    response = core.process("What is 2 + 2? Answer in one word.", session)
    
    assert response.success
    assert "4" in response.content or "four" in response.content.lower()

@pytest.mark.agent_eval
def test_agent_eval_tool_call_routing():
    # Ensure a real model can plan a tool call
    if not os.environ.get("GUARDIAN_MODEL_BACKEND") and not os.environ.get("GUARDIAN_GROQ_API_KEY") and not os.environ.get("GUARDIAN_GOOGLE_API_KEY"):
        pytest.skip("No real model configured for agent eval")
        
    registry = get_registry()
    try:
        model = registry.get_available()
    except Exception:
        pytest.skip("No model available for agent eval")
        
    if model.get_info().provider == "mock":
        pytest.skip("Mock model not suitable for real agent eval")

    from guardian.tools.tool_call import TOOL_USE_SYSTEM_ADDITION
    core = GuardianCore(
        model=model, 
        enable_self_critique=False,
        system_prompt=GUARDIAN_SYSTEM_PROMPT + "\n\n" + TOOL_USE_SYSTEM_ADDITION
    )
    session = Session()
    from guardian.tools.loop import ToolLoop
    from guardian.tools import get_tool_executor
    loop = ToolLoop(executor=get_tool_executor())
    
    # We ask it to run a tool
    result = loop.run(core, "Output EXACTLY ONE ```tool_call block to use file_read to read pytest.ini. DO NOT output anything else.", session)
    
    assert result.final_response.success
    # The real model should output a tool call block
    assert any(round.success for round in result.rounds)
