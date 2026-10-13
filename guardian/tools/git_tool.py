import subprocess
from typing import Any
from guardian.tools.base import Tool, ToolLevel, ToolResult

class GitReadTool(Tool):
    name = "git_read"
    level = ToolLevel.WRITE  # risk_tier 1
    description = "Read-only Git operations (status, diff, log)."
    
    def schema(self):
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["status", "diff", "log"]},
                "args": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["action"]
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        action = params.get("action")
        if action not in ["status", "diff", "log"]:
            return ToolResult(success=False, output="", error="Invalid action.")
            
        sandbox = params["_sandbox"]
        args = params.get("args", [])
        
        cmd = ["git", action] + args
        try:
            proc = subprocess.run(cmd, cwd=str(sandbox), capture_output=True, text=True, check=True)
            return ToolResult(success=True, output=proc.stdout)
        except subprocess.CalledProcessError as e:
            return ToolResult(success=False, output=e.stdout, error=e.stderr or str(e))
            
class GitWriteTool(Tool):
    name = "git_write"
    level = ToolLevel.DANGEROUS  # risk_tier 2
    description = "Write Git operations (add, commit)."
    
    def schema(self):
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "commit"]},
                "args": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["action"]
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        action = params.get("action")
        if action not in ["add", "commit"]:
            return ToolResult(success=False, output="", error="Invalid action.")
            
        sandbox = params["_sandbox"]
        args = params.get("args", [])
        
        cmd = ["git", action] + args
        try:
            proc = subprocess.run(cmd, cwd=str(sandbox), capture_output=True, text=True, check=True)
            return ToolResult(success=True, output=proc.stdout)
        except subprocess.CalledProcessError as e:
            return ToolResult(success=False, output=e.stdout, error=e.stderr or str(e))
