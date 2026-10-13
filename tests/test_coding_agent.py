import pytest
from guardian.core.coding_agent import CodingAgentImpl, CodingAgentScope

def test_protected_paths_hard_denied():
    agent = CodingAgentImpl("coding", CodingAgentScope(allowed_tools={"file_write"}), mode="autonomous")
    
    # Try to write to policy engine
    res = agent.execute_step("file_write", {"path": "guardian/policy/engine.py"})
    assert res.success is False
    assert "Access denied: guardian/policy/engine.py is a protected path." in res.error
    
    # Mode shouldn't matter
    agent_suggest = CodingAgentImpl("coding", CodingAgentScope(allowed_tools={"file_write"}), mode="suggest")
    res = agent_suggest.execute_step("file_write", {"path": "guardian/policy/engine.py"})
    assert res.success is False

def test_suggest_mode_only_suggests():
    agent = CodingAgentImpl("coding", CodingAgentScope(allowed_tools={"file_write"}), mode="suggest")
    res = agent.execute_step("file_write", {"path": "src/main.py", "content": "print()"})
    assert res.success is True
    assert "SUGGESTION LOGGED" in res.output

def test_iteration_loop_stops_at_limit():
    agent = CodingAgentImpl("coding", CodingAgentScope(allowed_tools={"file_write"}), mode="autonomous")
    res = agent.write_test_fix_loop("fix bug", max_iterations=2)
    assert "Failed after 2 iterations" in res
