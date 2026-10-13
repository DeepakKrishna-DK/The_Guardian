import sqlite3
import re
from typing import Any
from guardian.tools.base import Tool, ToolLevel, ToolResult

class DbQueryTool(Tool):
    name = "db_query"
    level = ToolLevel.WRITE  # risk_tier 1
    description = "Read-only queries against the audit log / threat DB."
    cache_ttl = 60.0  # 60 seconds
    
    def schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The SQL query to run (SELECT only)."},
                "params": {"type": "array", "items": {"type": "string"}, "description": "Query parameters."}
            },
            "required": ["query"]
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        if not re.match(r"^\s*SELECT", query, re.IGNORECASE):
            return ToolResult(success=False, output="", error="Only SELECT queries are allowed.")
            
        sql_params = params.get("params", [])
        
        # In a real app we'd use the actual DB path, assuming audit DB is at .guardian/audit.db
        sandbox = params["_sandbox"]
        db_path = sandbox / ".guardian" / "audit.db"
        if not db_path.exists():
            return ToolResult(success=False, output="", error="Database not found.")
            
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, sql_params)
                rows = cursor.fetchall()
                # simple CSV output
                output = "\n".join([",".join(map(str, row)) for row in rows])
                return ToolResult(success=True, output=output or "No results.")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
