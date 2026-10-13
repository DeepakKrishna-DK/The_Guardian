import json
from dataclasses import dataclass, field
from typing import Any

from guardian.logging.logger import get_logger
from guardian.core.orchestrator import GuardianCore, Session, CallType

log = get_logger(__name__)


@dataclass
class PlanStep:
    tool_or_skill: str
    rationale: str
    target: str = ""

@dataclass
class Plan:
    steps: list[PlanStep] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 to 1.0


class Planner:
    """
    Produces and verifies multi-step execution plans (M1).
    """

    def __init__(self, core: GuardianCore):
        self.core = core

    def create_plan(self, task: str, session: Session) -> Plan:
        """
        Ask the model to produce a structured plan for the task.
        """
        from guardian.tools import get_tool_executor
        executor = get_tool_executor()
        tools_list = ", ".join(executor.get_all().keys()) if hasattr(executor, "get_all") else "file_read, shell, network_recon"
        
        prompt = (
            f"Produce an explicit plan to solve this task: '{task}'.\n"
            f"You MUST only use the following available tools/skills: {tools_list}\n"
            "Respond ONLY with a JSON object in this format:\n"
            "{\n"
            "  \"confidence\": 0.95,\n"
            "  \"steps\": [\n"
            "    {\"tool_or_skill\": \"name\", \"rationale\": \"why\", \"target\": \"target_arg_if_any\"}\n"
            "  ]\n"
            "}"
        )
        # Using PLANNING call type
        response = self.core.process(prompt, session, call_type=CallType.PLANNING)
        if not response.success:
            log.error(f"Plan creation failed: {response.error}")
            return Plan()

        try:
            # Extract JSON block
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)
            steps = [
                PlanStep(
                    tool_or_skill=s.get("tool_or_skill", ""),
                    rationale=s.get("rationale", ""),
                    target=s.get("target", "")
                )
                for s in data.get("steps", [])
            ]
            confidence = float(data.get("confidence", 0.0))
            log.info(f"Generated plan with {len(steps)} steps (confidence: {confidence:.2f})")
            return Plan(steps=steps, confidence=confidence)
        except Exception as e:
            log.warning(f"Failed to parse plan JSON: {e}\nContent was: {response.content}")
            return Plan()

    def verify_plan(self, plan: Plan) -> list[str]:
        """
        Advisory self-critique pass against scope/risk-tier/policy BEFORE the first step runs.
        Returns a list of warnings. Empty list means clean.
        """
        warnings = []
        if not plan.steps:
            return ["Empty plan"]

        from guardian.policy.engine import get_policy_engine, Effect
        engine = get_policy_engine()

        for i, step in enumerate(plan.steps):
            # Check via policy engine. evaluate expects params dict with standard keys if possible.
            # We map target to typical scoped arguments.
            params = {}
            if step.target:
                params["path"] = step.target
                params["target"] = step.target
                params["command"] = step.target

            # We don't have tool level or registered_tools easily available without executor,
            # but we can get them from executor.
            from guardian.tools import get_tool_executor
            executor = get_tool_executor()
            tool = executor.get(step.tool_or_skill)
            level = tool.level.value if tool else 0
            req_scope = getattr(tool, "requires_scope", False) if tool else False
            t_arg = getattr(tool, "target_arg", None) if tool else None
            registered = set(executor.list_tools()) if hasattr(executor, "list_tools") else {step.tool_or_skill}
            
            # Map target to params so policy engine can check it
            if step.target and t_arg:
                params[t_arg] = step.target
            elif step.target:
                params["target"] = step.target
                params["path"] = step.target
                
            registered_names = {t.name for t in registered} if isinstance(list(registered)[0], object) and hasattr(list(registered)[0], "name") else registered
            
            decision = engine.evaluate(step.tool_or_skill, level, params, registered_names, target_arg=t_arg, requires_scope=req_scope)
            if decision.effect == Effect.DENY:
                warning = f"Step {i+1} ({step.tool_or_skill}) flagged by PolicyEngine: {decision.reason}"
                warnings.append(warning)
                log.warning(warning)
                
            # M1 specific requirement: log this advisory pass to audit (metadata only)
            try:
                from guardian.audit import get_audit_log
                get_audit_log().append(
                    "plan.verify",
                    payload={
                        "step": i+1,
                        "tool": step.tool_or_skill,
                        "effect": decision.effect.value,
                        "confidence": plan.confidence
                    }
                )
            except Exception:
                pass

        if not warnings:
            log.info("Plan verification passed clean.")
        return warnings
