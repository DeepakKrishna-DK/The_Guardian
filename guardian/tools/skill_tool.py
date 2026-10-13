import contextvars
from typing import Any
from guardian.tools.base import Tool, ToolLevel, ToolResult

skill_recursion_depth = contextvars.ContextVar("skill_recursion_depth", default=0)

class SkillTool(Tool):
    def __init__(self, skill):
        self.skill = skill
        self.name = f"skill:{skill.name}"
        self.level = ToolLevel(min(skill.risk_tier, 2))
        self.description = f"Invoke the {skill.title} skill. {skill.description}"
        self.requires_scope = skill.requires_scope
        self.target_arg = skill.target_arg

    def schema(self):
        return {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": f"The specific task or prompt to execute using the {self.skill.name} skill."
                }
            },
            "required": ["goal"]
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        goal = params.get("goal")
        if not goal:
            return ToolResult(success=False, output="", error="Missing 'goal' parameter.")
            
        depth = skill_recursion_depth.get()
        if depth >= 5:
            try:
                from guardian.audit import get_audit_log
                get_audit_log().append(
                    "skill.recursion_limit_exceeded",
                    payload={"skill": self.name, "depth": depth}
                )
            except Exception:
                pass
            return ToolResult(success=False, output="", error=f"Recursion depth limit (5) exceeded invoking {self.name}.")

        token = skill_recursion_depth.set(depth + 1)
        try:
            from guardian.core.session import Session
            from guardian.core.orchestrator import GuardianCore
            from guardian.model.registry import get_model
            from guardian.tools.loop import ToolLoop
            from guardian.tools import get_tool_executor
            
            core = GuardianCore(model=get_model())
            session = Session()
            loop = ToolLoop(executor=get_tool_executor())
            
            result = loop.run(
                core=core,
                user_input=goal,
                session=session,
                active_skill=self.skill.name,
                skill_prompt_addition=self.skill.prompt_addition
            )
            
            success = result.final_response.error is None
            return ToolResult(
                success=success,
                output=result.final_response.content or "",
                error=result.final_response.error,
                metadata={"rounds": result.rounds}
            )
        finally:
            skill_recursion_depth.reset(token)
