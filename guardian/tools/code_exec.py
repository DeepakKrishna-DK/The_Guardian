import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from guardian.tools.base import Tool, ToolLevel, ToolResult

class CodeExecTool(Tool):
    name = "code_exec"
    level = ToolLevel.DANGEROUS
    description = "Execute sandboxed Python code for data analysis or scripting."
    
    def __init__(self, enable_feature: bool = False, timeout: int = 10):
        self._enabled = enable_feature or os.environ.get("GUARDIAN_ENABLE_CODE_EXEC", "0") == "1"
        self._timeout = timeout
        
    def schema(self):
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute."
                }
            },
            "required": ["code"]
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        if not self._enabled:
            return ToolResult(success=False, output="", error="code_exec feature is disabled by default.")
            
        code = params.get("code")
        if not code:
            return ToolResult(success=False, output="", error="Missing 'code' parameter.")
            
        sandbox = params["_sandbox"]
        scratch_dir = sandbox / "scratch"
        scratch_dir.mkdir(exist_ok=True)
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=scratch_dir, delete=False, encoding="utf-8") as f:
            f.write(code)
            script_path = f.name
            
        try:
            # Documented best-effort on Windows, resource limits on POSIX
            preexec_fn = None
            if os.name == "posix":
                def limit_resources():
                    import resource
                    # 100MB memory limit
                    resource.setrlimit(resource.RLIMIT_AS, (100 * 1024 * 1024, 100 * 1024 * 1024))
                preexec_fn = limit_resources
                
            cmd = [sys.executable, script_path]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(scratch_dir),
                preexec_fn=preexec_fn
            )
            
            output = proc.stdout
            if proc.stderr:
                output += f"\n--- STDERR ---\n{proc.stderr}"
                
            if proc.returncode != 0:
                return ToolResult(success=False, output=output, error=f"Process exited with code {proc.returncode}")
                
            return ToolResult(success=True, output=output)
            
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error=f"Execution timed out after {self._timeout}s")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
        finally:
            try:
                os.remove(script_path)
            except OSError:
                pass
