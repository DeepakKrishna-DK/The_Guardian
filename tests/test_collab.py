"""
tests/test_collab.py
=====================
M3: Agent/Human Collaboration Protocol tests
"""
from __future__ import annotations

import pytest
from guardian.core.collab import CollaborationSummary, record_agent_handoff, EscalationReason
from guardian.core.orchestrator import GuardianCore, Session
from guardian.model.backends.mock import MockBackend
from guardian.core.planning import Planner, Plan, PlanStep

def test_seeded_ambiguous_scenario_escalates():
    # If a plan step targets an ambiguous scope (e.g. wildcard or out of scope),
    # verifying it should produce a warning that triggers an Escalation.
    
    class MockPlannerBackend(MockBackend):
        def complete(self, request):
            import json
            from guardian.model.interface import ModelResponse
            data = {
                "confidence": 0.5,
                "steps": [
                    {"tool_or_skill": "network_recon", "rationale": "scan everything", "target": "*"}
                ]
            }
            return ModelResponse(content=f"```json\n{json.dumps(data)}\n```", provider="mock", model="mock")

    core = GuardianCore(model=MockPlannerBackend())
    
    # We patch process to use Planner before responding, or we just test the Collab logic directly
    # The requirement: "the orchestrator should surface a clarifying question... rather than silently proceeding"
    # Let's call core.process() and see if the response contains an escalation.
    
    session = Session()
    response = core.process("scan the network", session, active_skill="security_guardian")
    
    assert response.success
    assert len(response.escalations) >= 1
    assert response.escalations[0].reason == EscalationReason.AMBIGUOUS_SCOPE


def test_subagent_handoff_audit_log(tmp_path):
    from guardian.audit.log import AuditLog, reset_audit_log
    from unittest.mock import patch
    
    reset_audit_log()
    test_log = AuditLog(path=tmp_path / "audit_handoff.db")
    
    with patch("guardian.core.collab.get_audit_log", return_value=test_log):
        
        record_agent_handoff(
            from_agent="recon_agent",
            to_agent="analysis_agent",
            asked="scan 10.0.0.1",
            found="ports 80, 443 open",
            passing_on="analyze web vulnerabilities"
        )
        
        cur = test_log._conn.cursor()
        cur.execute("SELECT event_type, actor, payload_json FROM audit_events WHERE event_type='agent.handoff'")
        rows = cur.fetchall()
        
    test_log.close()
    reset_audit_log()
    
    assert len(rows) == 1
    assert rows[0][1] == "recon_agent"
    assert "analyze web vulnerabilities" in rows[0][2]


def test_collaboration_summary_rendering():
    from guardian.core.collab import CollaborationSummary, Escalation, EscalationReason
    summary = CollaborationSummary(
        tasks_done=["Recon target A", "Analyze target A"],
        handoffs=[{"from": "recon", "to": "analysis"}],
        escalations=[
            Escalation(
                reason=EscalationReason.POLICY_APPROVAL_REQUIRED,
                message="Level-2 tool execution blocked.",
                pending_action="Approve or Deny"
            )
        ]
    )
    
    text = summary.render()
    assert "Completed: 2 steps" in text
    assert "Handoffs: 1" in text
    assert "ESCALATION REQUIRED" in text
    assert "Level-2 tool execution blocked." in text
