import pytest
from guardian.core.agents import ReconAgent, AnalysisAgent, ResponseAgent, AGENTS, get_agent_for_tool
from guardian.tools.executor import ToolRequest
from guardian.tools import get_tool_executor
from guardian.policy.engine import get_policy_engine, Effect

def test_supervisor_routes_to_correct_agent():
    assert get_agent_for_tool("network_recon") == ReconAgent
    assert get_agent_for_tool("vision_analyze") == AnalysisAgent
    assert get_agent_for_tool("shell") == ResponseAgent
    assert get_agent_for_tool("unknown_tool") is None

def test_subagent_scope_denial():
    # Attempting to use a tool outside the agent's scope
    # E.g. ReconAgent using 'shell'
    result = ReconAgent.execute_step("shell", {"cmd": "ls"})
    assert result.success is False
    assert "outside the scope of agent recon_agent" in result.error
    
    # Check that AnalysisAgent is denied network_recon
    result = AnalysisAgent.execute_step("network_recon", {"target": "127.0.0.1"})
    assert result.success is False
    assert "outside the scope of agent analysis_agent" in result.error

def test_subagent_no_bypass(monkeypatch):
    """
    Spy test to prove no call bypasses the existing choke point via the new delegation path.
    We mock the ToolExecutor's run method to ensure it is actually called by the agent.
    """
    executor = get_tool_executor()
    
    spy_called = False
    original_run = executor.run
    
    def mock_run(request, session_id=""):
        nonlocal spy_called
        spy_called = True
        # Check that the actor is correctly passed
        assert request.context.get("actor") == "recon_agent"
        # We can just return a dummy result instead of fully executing to avoid side effects
        from guardian.tools.executor import ToolResult
        return ToolResult(success=True, output="Mocked", error="", tool_name=request.name)
        
    monkeypatch.setattr(executor, "run", mock_run)
    
    result = ReconAgent.execute_step("network_recon", {"target": "127.0.0.1"})
    
    assert spy_called is True
    assert result.success is True
    assert result.output == "Mocked"
