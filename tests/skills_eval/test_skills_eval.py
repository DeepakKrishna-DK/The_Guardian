import pytest
from unittest.mock import patch, MagicMock
from guardian.core.orchestrator import GuardianCore, Session
from guardian.model.backends.mock import MockBackend
from guardian.tools import get_tool_executor
from guardian.tools.base import ToolRequest
from guardian.skills.base import Skill
from guardian.tools.skill_tool import skill_recursion_depth, SkillTool

@pytest.fixture
def mock_core():
    return GuardianCore(model=MockBackend())

@pytest.mark.skills_eval
def test_recursion_limit_enforced_and_audited(mock_core):
    # Set recursion depth directly to simulate deep call stack
    token = skill_recursion_depth.set(5)
    
    skill = Skill(name="dummy", title="Dummy", description="", prompt_addition="", keywords=[])
    tool = SkillTool(skill)
    
    # Needs a mock audit log to verify the event
    with patch("guardian.audit.get_audit_log") as mock_audit:
        result = tool._execute({"goal": "test"})
        
        # Verify it denied execution
        assert not result.success
        assert "Recursion depth limit (5) exceeded" in result.error
        
        # Verify it was audited
        mock_audit.return_value.append.assert_called_with(
            "skill.recursion_limit_exceeded",
            payload={"skill": "skill:dummy", "depth": 5}
        )
    
    skill_recursion_depth.reset(token)

@pytest.mark.skills_eval
def test_composed_skill_eval_scenario(mock_core):
    # Create a recon skill that calls 2 smaller skills
    recon_skill = Skill(name="recon", title="Recon", description="", prompt_addition="", keywords=[])
    small_skill_1 = Skill(name="small1", title="Small1", description="", prompt_addition="", keywords=[])
    small_skill_2 = Skill(name="small2", title="Small2", description="", prompt_addition="", keywords=[])
    
    # We will simulate the LLM choosing to call skill:small1 and then skill:small2
    # The MockBackend just returns whatever we want. But the ToolLoop uses MockBackend which by default returns 
    # fixed responses. To make it output tool calls, we can patch `ToolLoop._call_model_and_parse` or mock the ModelInterface.
    
    executor = get_tool_executor()
    executor.register(SkillTool(recon_skill))
    executor.register(SkillTool(small_skill_1))
    executor.register(SkillTool(small_skill_2))
    
    with patch("guardian.tools.loop.ToolLoop.run") as mock_loop_run:
        from guardian.tools.loop import ToolLoopResult
        from guardian.core.response import GuardianResponse
        
        mock_loop_run.return_value = ToolLoopResult(
            final_response=GuardianResponse(content="Done", model_provider="mock", model_name="mock", session_turn=1, duration_ms=10),
            rounds=1
        )
        
        tool = SkillTool(recon_skill)
        result = tool._execute({"goal": "do recon"})
        assert result.success
        assert result.output == "Done"
        assert mock_loop_run.call_count == 1
