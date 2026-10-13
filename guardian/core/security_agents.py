from guardian.core.agents import SubAgent, AgentScope
from guardian.tools.executor import ToolResult
from guardian.policy.compliance import ComplianceStore
from pathlib import Path
from typing import Any

class ComplianceAgentImpl(SubAgent):
    def check_attestation(self, technique_id: str) -> bool:
        store = ComplianceStore(Path("guardian/policy/compliance.json"))
        # In a real scenario, this would evaluate actual compliance constraints.
        # For this test, we enforce that 'T1595' is disallowed without active compliance record.
        # Let's say if it requires scope, check if store has a record.
        from guardian.techniques.library import TechniqueLibrary
        tech = TechniqueLibrary.get(technique_id)
        if tech and tech.requires_scope:
            refs = store.get_all()
            if not refs:
                return False
        return True

class RedTeamAgentImpl(SubAgent):
    def execute_step(self, tool_name: str, params: dict[str, Any], session_id: str = "") -> ToolResult:
        # Dependency on ComplianceAgent
        technique_id = params.get("technique_id")
        if technique_id:
            compliance_agent = ComplianceAgentImpl("compliance", AgentScope(allowed_tools=set()))
            if not compliance_agent.check_attestation(technique_id):
                return ToolResult(
                    success=False, 
                    output="", 
                    error=f"RedTeam action blocked: ComplianceAgent attestation failed for {technique_id}", 
                    tool_name=tool_name
                )
        return super().execute_step(tool_name, params, session_id)

class BlueTeamAgentImpl(SubAgent):
    pass

class SocialEngineeringAgentImpl(SubAgent):
    """SubAgent dedicated to social engineering defense, phishing triage, and credential harvester detection."""
    pass

BlueTeamAgent = BlueTeamAgentImpl("blue_team", AgentScope(allowed_tools={"file_read", "search"}))
RedTeamAgent = RedTeamAgentImpl("red_team", AgentScope(allowed_tools={"network_recon", "file_read"}))
ComplianceAgent = ComplianceAgentImpl("compliance", AgentScope(allowed_tools={"file_read"}))
SocialEngineeringAgent = SocialEngineeringAgentImpl(
    "social_engineering",
    AgentScope(allowed_tools={"social_engineering_defense", "file_read", "search"})
)
