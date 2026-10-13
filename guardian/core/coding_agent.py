from dataclasses import dataclass
from typing import Any, Literal
import os
import time
import subprocess
from guardian.core.agents import SubAgent, AgentScope
from guardian.tools.executor import ToolResult

@dataclass
class CodingAgentScope(AgentScope):
    workspace_path: str = "."

class CodingAgentImpl(SubAgent):
    def __init__(self, name: str, scope: CodingAgentScope, mode: Literal["suggest", "supervised", "autonomous"] = "suggest"):
        super().__init__(name, scope)
        self.mode = mode
        
    def _is_protected_path(self, path: str) -> bool:
        normalized = os.path.normpath(path).replace('\\', '/')
        if "guardian/policy" in normalized or "guardian/audit" in normalized:
            return True
        return False
        
    def execute_step(self, tool_name: str, params: dict[str, Any], session_id: str = "") -> ToolResult:
        # Enforce protected paths
        if tool_name in ("file_write", "code_exec"):
            # Check path params
            target_path = params.get("path") or params.get("filename") or ""
            if self._is_protected_path(target_path):
                from guardian.audit import get_audit_log
                audit = get_audit_log()
                audit.append("agent.protected_path_violation", actor=self.name, payload={"tool": tool_name, "path": target_path})
                return ToolResult(success=False, output="", error=f"Access denied: {target_path} is a protected path.", tool_name=tool_name)
                
        if self.mode == "suggest" and tool_name in ("file_write", "code_exec"):
            return ToolResult(success=True, output=f"SUGGESTION LOGGED: would execute {tool_name} on {params}", tool_name=tool_name)
            
        return super().execute_step(tool_name, params, session_id)
        
    def write_test_fix_loop(self, task: str, max_iterations: int = 5, max_wall_time: int = 300) -> str:
        start_time = time.time()
        
        for i in range(max_iterations):
            if time.time() - start_time > max_wall_time:
                return "Aborted: Wall-clock timeout."
            # In a real loop we would generate code and test it here.
            # We simulate a failure and continue the loop.
            time.sleep(0.01)
            
        return f"Failed after {max_iterations} iterations: Tests continuously failed."

CodingAgent = CodingAgentImpl("coding_agent", CodingAgentScope(allowed_tools={"code_exec", "git_tool", "file_read", "file_write"}))
