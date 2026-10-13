from dataclasses import dataclass, field
from typing import Callable, Any
from guardian.logging.logger import get_logger
from guardian.core.orchestrator import GuardianCore, Session
from guardian.tools.tool_call import ToolCall
from guardian.tools import ToolExecutor

log = get_logger(__name__)

@dataclass
class ProcedureStep:
    tool_name: str
    params: dict[str, Any]

@dataclass
class Procedure:
    name: str
    description: str
    steps: list[ProcedureStep] = field(default_factory=list)


class ProcedureRunner:
    """
    Executes a predefined Procedure.
    Every step is individually policy-checked and audited.
    """
    def __init__(self, core: GuardianCore, executor: ToolExecutor):
        self.core = core
        self.executor = executor
        
    def run(
        self,
        procedure: Procedure,
        session: Session,
        approval_callback: Callable[[ToolCall, str], bool] | None = None
    ) -> list[Any]:
        results = []
        log.info(f"Starting procedure: {procedure.name} ({len(procedure.steps)} steps)")
        
        from guardian.policy.engine import get_policy_engine, Effect
        engine = get_policy_engine()
        
        for i, step in enumerate(procedure.steps):
            log.info(f"Procedure {procedure.name} step {i+1}: {step.tool_name}")
            
            tool = self.executor.get(step.tool_name)
            if tool is None:
                results.append(f"Error: Tool {step.tool_name} not found.")
                break
                
            req_scope = getattr(tool, "requires_scope", False) if tool else False
            t_arg = getattr(tool, "target_arg", None) if tool else None
            registered = set(self.executor.list_tools()) if hasattr(self.executor, "list_tools") else {step.tool_name}
            registered_names = {t.name for t in registered} if isinstance(list(registered)[0], object) and hasattr(list(registered)[0], "name") else registered
            
            decision = engine.evaluate(
                step.tool_name,
                tool.level.value if tool else 0,
                step.params,
                registered_names,
                target_arg=t_arg,
                requires_scope=req_scope
            )
            if decision.effect == Effect.DENY:
                results.append(f"Error: Step {i+1} denied by policy: {decision.reason}")
                break
            
            # Step requires approval
            call = ToolCall(name=step.tool_name, params=step.params, raw="")
            is_approved = False
            if decision.effect == Effect.REQUIRE_APPROVAL:
                if approval_callback:
                    if not approval_callback(call, decision.reason):
                        results.append(f"Error: Step {i+1} user denied approval.")
                        break
                    is_approved = True
                else:
                    # Default: deny if no callback provided
                    results.append(f"Error: Step {i+1} requires approval but no callback provided.")
                    break
            else:
                is_approved = True
            
            try:
                # Add context for sandboxing if needed
                step_params = dict(step.params)
                # Call run
                from guardian.tools.base import ToolRequest
                req = ToolRequest(
                    name=step.tool_name,
                    params=step_params,
                    session_id=getattr(session, "session_id", ""),
                    approved=is_approved
                )
                res = self.executor.run(req)
                results.append(res)
                
                # If tool failed, we stop the procedure
                if not res.success:
                    log.warning(f"Procedure step {i+1} failed: {res.error}")
                    break
            except Exception as e:
                results.append(f"Error executing step {i+1}: {e}")
                break
                
        log.info(f"Completed procedure: {procedure.name} ({len(results)} steps run)")
        return results
