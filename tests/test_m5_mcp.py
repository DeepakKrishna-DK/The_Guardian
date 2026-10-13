import pytest
import os
import subprocess
from unittest.mock import patch, MagicMock
from guardian.mcp.adapter import MCPAdapter
from guardian.tools.mcp_tool import McpTool
from guardian.tools.executor import ToolExecutor
from guardian.tools.base import ToolRequest

def test_mcp_tool_wrapping_and_execution(tmp_path):
    adapter = MCPAdapter()
    adapter.connect_stdio("dummy", ["args"])
    
    with patch.object(adapter, "call_tool") as mock_call_tool:
        mock_call_tool.return_value = {"content": [{"text": "Success"}], "isError": False}
        
        tool = McpTool(adapter, "test_tool", "A test tool", {"type": "object", "properties": {}})
        
        executor = ToolExecutor(sandbox_root=tmp_path)
        executor.register(tool)
        
        # Unapproved should fail (risk_tier 2)
        req_unapproved = ToolRequest(name="mcp:test_tool", params={}, approved=False)
        res1 = executor.run(req_unapproved)
        assert not res1.success
        assert "requires approval" in res1.error
        
        # Approved should succeed
        req_approved = ToolRequest(name="mcp:test_tool", params={}, approved=True)
        res2 = executor.run(req_approved)
        assert res2.success
        assert "Success" in res2.output

def test_no_mcp_imports_outside_adapter():
    # Run a recursive grep to ensure no file contains 'import mcp' or 'from mcp'
    # EXCEPT adapter.py or test files.
    import pathlib
    root = pathlib.Path(__file__).parent.parent / "guardian"
    
    violations = []
    for filepath in root.rglob("*.py"):
        if filepath.name in ("adapter.py", "server.py"):
            continue
            
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        for line_num, line in enumerate(content.splitlines(), 1):
            if "import mcp" in line or "from mcp " in line or "from mcp." in line:
                violations.append(f"{filepath.name}:{line_num}: {line.strip()}")
                
    assert not violations, f"Found prohibited mcp imports:\n" + "\n".join(violations)
