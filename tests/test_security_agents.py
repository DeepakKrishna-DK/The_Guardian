import pytest
import json
from pathlib import Path
from guardian.core.security_agents import RedTeamAgentImpl, ComplianceAgentImpl
from guardian.core.agents import AgentScope

def test_red_team_attestation_block(tmp_path):
    # Setup dummy compliance store missing T1595 record
    db_path = tmp_path / "compliance.json"
    db_path.write_text("{}")
    
    # Patch Path to use our temp path inside ComplianceAgentImpl
    import guardian.core.security_agents
    original_path = guardian.core.security_agents.Path
    guardian.core.security_agents.Path = lambda x: db_path if "compliance.json" in x else original_path(x)
    
    agent = RedTeamAgentImpl("red_team", AgentScope(allowed_tools={"network_recon"}))
    
    res = agent.execute_step("network_recon", {"technique_id": "T1595"})
    
    # Should be blocked
    assert res.success is False
    assert "ComplianceAgent attestation failed for T1595" in res.error

    # Restore
    guardian.core.security_agents.Path = original_path

def test_cross_agent_tool_access_denied():
    agent = RedTeamAgentImpl("red_team", AgentScope(allowed_tools={"network_recon"}))
    res = agent.execute_step("file_write", {"path": "test.txt"})
    assert res.success is False
    assert "outside the scope of agent" in res.error

@pytest.fixture
def mock_compliance():
    import guardian.core.security_agents
    original_check = guardian.core.security_agents.ComplianceAgentImpl.check_attestation
    guardian.core.security_agents.ComplianceAgentImpl.check_attestation = lambda self, tid: True
    yield
    guardian.core.security_agents.ComplianceAgentImpl.check_attestation = original_check

def test_red_team_policy_gate_still_enforced(mock_compliance):
    agent = RedTeamAgentImpl("red_team", AgentScope(allowed_tools={"network_recon"}))
    # Even if compliance passes (mocked to True), the policy engine should block an unauthorized tool call
    res = agent.execute_step("network_recon", {"target": "10.0.0.1", "technique_id": "T1595"})
    assert res.success is False
    assert "policy" in res.error.lower() or "not in scope" in res.error.lower() or "denied" in res.error.lower()
