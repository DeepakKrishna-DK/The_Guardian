import pytest
from guardian.core.orchestrator import GuardianCore, Session
from guardian.core.procedure import Procedure, ProcedureStep, ProcedureRunner
from guardian.model.backends.mock import MockBackend
from guardian.tools import get_tool_executor
from guardian.tools.base import Tool, ToolResult, ToolLevel

class DummyTool(Tool):
    name = "dummy_tool"
    level = ToolLevel.READ
    
    def _execute(self, params):
        return ToolResult(success=True, output=f"dummy {params.get('id')}")

def test_procedure_execution_and_approval(monkeypatch):
    core = GuardianCore(model=MockBackend())
    executor = get_tool_executor()
    executor.register(DummyTool())
    
    proc = Procedure(
        name="test_proc",
        description="A test",
        steps=[
            ProcedureStep(tool_name="dummy_tool", params={"id": 1}),
            ProcedureStep(tool_name="dummy_tool", params={"id": 2}),
        ]
    )
    
    from guardian.policy.engine import get_policy_engine, PolicyDecision, Effect
    engine = get_policy_engine()
    
    # Mock PolicyEngine to require approval on step 2
    original_evaluate = engine.evaluate
    def mock_evaluate(tool_name, tool_level, params, registered_tools, **kwargs):
        if params.get("id") == 2:
            return PolicyDecision(effect=Effect.REQUIRE_APPROVAL, rule_id="req_app", reason="Step 2 needs approval")
        return original_evaluate(tool_name, tool_level, params, registered_tools, **kwargs)
    
    monkeypatch.setattr(engine, "evaluate", mock_evaluate)
    
    runner = ProcedureRunner(core, executor)
    
    # 1. Run without callback -> step 2 fails
    results = runner.run(proc, Session())
    assert len(results) == 2
    assert getattr(results[0], "success", False) == True
    assert "requires approval" in results[1]
    
    # 2. Run with callback that approves
    approved = False
    def approve_cb(call, reason):
        nonlocal approved
        approved = True
        return True
        
    results_approved = runner.run(proc, Session(), approval_callback=approve_cb)
    assert len(results_approved) == 2
    assert getattr(results_approved[0], "success", False) == True
    assert getattr(results_approved[1], "success", False) == True
    assert approved
