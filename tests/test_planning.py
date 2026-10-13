import pytest
from guardian.core.orchestrator import GuardianCore, Session
from guardian.core.planning import Planner, Plan, PlanStep
from guardian.model.backends.mock import MockBackend

def test_create_plan():
    class PlanMockBackend(MockBackend):
        def complete(self, request):
            import json
            from guardian.model.interface import ModelResponse
            data = {
                "confidence": 0.85,
                "steps": [
                    {"tool_or_skill": "file_read", "rationale": "read scope", "target": "scope.json"}
                ]
            }
            return ModelResponse(content=f"```json\n{json.dumps(data)}\n```", provider="mock", model="plan-mock")

    core = GuardianCore(model=PlanMockBackend())
    planner = Planner(core)
    plan = planner.create_plan("do something", Session())
    
    assert plan.confidence == 0.85
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_or_skill == "file_read"

def test_verify_plan_flags_bad_step(monkeypatch):
    core = GuardianCore(model=MockBackend())
    planner = Planner(core)
    
    plan = Plan(
        confidence=0.9,
        steps=[
            PlanStep(tool_or_skill="network_recon", rationale="scan", target="8.8.8.8")
        ]
    )
    
    # Mock PolicyEngine to always DENY this for the test
    from guardian.policy.engine import get_policy_engine, PolicyDecision, Effect
    engine = get_policy_engine()
    
    def mock_evaluate(tool_name, tool_level, params, registered_tools, **kwargs):
        return PolicyDecision(effect=Effect.DENY, rule_id="test_rule", reason="Out of scope target")
        
    monkeypatch.setattr(engine, "evaluate", mock_evaluate)
    
    warnings = planner.verify_plan(plan)
    
    # Verification flags it without blocking it
    assert len(warnings) == 1
    assert "Out of scope target" in warnings[0]
