from typing import Any
from guardian.tools.base import Tool, ToolLevel, ToolResult
from guardian.mcp.adapter import MCPAdapter

class McpTool(Tool):
    """Wraps a discovered MCP tool to be used within the ToolExecutor."""
    
    def __init__(self, adapter: MCPAdapter, name: str, description: str, input_schema: dict):
        self.adapter = adapter
        self.name = f"mcp:{name}"
        self.level = ToolLevel.DANGEROUS  # default risk_tier 2 for external tools
        self.description = description
        self.requires_scope = False
        self._schema = input_schema
        self._original_name = name

    def schema(self) -> dict[str, Any]:
        return self._schema

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        # Strip injected params
        args = {k: v for k, v in params.items() if not k.startswith("_")}
        
        try:
            res = self.adapter.call_tool(self._original_name, args)
            # res is dict with 'content' and 'isError'
            is_error = res.get("isError", False)
            content_list = res.get("content", [])
            output = "\n".join([c.get("text", str(c)) for c in content_list])
            
            if is_error:
                return ToolResult(success=False, output="", error=output)
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
