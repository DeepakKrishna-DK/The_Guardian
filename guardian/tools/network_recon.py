import subprocess
from typing import Any
from guardian.tools.base import Tool, ToolLevel, ToolResult

class NetworkReconTool(Tool):
    name = "network_recon"
    level = ToolLevel.DANGEROUS  # risk_tier 2
    description = "Run nmap against a target. Enforces scope strictly."
    requires_scope = True
    target_arg = "target"
    cache_ttl = 300.0  # 5 minutes
    
    def schema(self):
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "The target IP or hostname"},
                "args": {"type": "array", "items": {"type": "string"}, "description": "Additional nmap arguments"}
            },
            "required": ["target"]
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        target = params.get("target")
        if not target:
            return ToolResult(success=False, output="", error="Missing 'target'.")
            
        args = params.get("args", [])
        cmd = ["nmap", target] + args
        
        try:
            # Sandbox is ignored for network operations but cwd is safe
            sandbox = params["_sandbox"]
            proc = subprocess.run(cmd, cwd=str(sandbox), capture_output=True, text=True, check=True)
            return ToolResult(success=True, output=proc.stdout)
        except subprocess.CalledProcessError as e:
            return ToolResult(success=False, output=e.stdout, error=e.stderr or str(e))
        except FileNotFoundError:
            return ToolResult(success=False, output="", error="nmap not found on system.")
