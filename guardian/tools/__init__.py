"""
Guardian Tool System — Public API
===================================
Usage:
    from guardian.tools import get_tool_registry, get_tool_executor
    executor = get_tool_executor()
    result = executor.run(ToolRequest(name="file_read", params={"path": "README.md"}))
"""

from __future__ import annotations

from pathlib import Path

from guardian.tools.base import (
    SandboxViolation,
    Tool,
    ToolError,
    ToolLevel,
    ToolRequest,
    ToolResult,
)
from guardian.tools.directory import DirectoryTool
from guardian.tools.executor import ToolExecutor
from guardian.tools.file_read import FileReadTool
from guardian.tools.file_write import FileWriteTool
from guardian.tools.loop import ToolLoop, ToolLoopResult, ToolRound
from guardian.tools.search import SearchTool
from guardian.tools.shell import ShellTool
from guardian.tools.tool_call import (
    TOOL_USE_SYSTEM_ADDITION,
    ParseResult,
    ToolCall,
    build_tool_result_message,
    parse_tool_calls,
)


def _build_default_executor(sandbox: Path | None = None) -> ToolExecutor:
    exe = ToolExecutor(sandbox_root=sandbox)
    exe.register(FileReadTool())
    exe.register(FileWriteTool())
    exe.register(DirectoryTool())
    exe.register(SearchTool())
    exe.register(ShellTool())
    
    # M3: New tools
    from guardian.tools.code_exec import CodeExecTool
    from guardian.tools.git_tool import GitReadTool, GitWriteTool
    from guardian.tools.network_recon import NetworkReconTool
    from guardian.tools.db_query import DbQueryTool
    from guardian.tools.vision_analyze import VisionAnalyzeTool
    from guardian.tools.social_engineering_tool import SocialEngineeringDefenseTool
    from guardian.tools.web_research_tool import WebResearchTool
    
    exe.register(CodeExecTool())
    exe.register(GitReadTool())
    exe.register(GitWriteTool())
    exe.register(NetworkReconTool())
    exe.register(DbQueryTool())
    exe.register(VisionAnalyzeTool())
    exe.register(SocialEngineeringDefenseTool())
    exe.register(WebResearchTool())
    
    # M2: Register skills as tools
    from guardian.skills import get_skill_registry
    from guardian.tools.skill_tool import SkillTool
    for skill in get_skill_registry().list_all():
        exe.register(SkillTool(skill))
        
    return exe


_executor: ToolExecutor | None = None


def get_tool_executor(sandbox: Path | None = None) -> ToolExecutor:
    """Return the shared ToolExecutor singleton (lazy init)."""
    global _executor
    if _executor is None:
        _executor = _build_default_executor(sandbox)
    return _executor


def reset_tool_executor() -> None:
    """Reset the singleton (for testing with custom sandbox)."""
    global _executor
    _executor = None


__all__ = [
    "DirectoryTool",
    "FileReadTool",
    "FileWriteTool",
    "SandboxViolation",
    "SearchTool",
    "ShellTool",
    "Tool",
    "ToolError",
    "ToolExecutor",
    "ToolLevel",
    "ToolRequest",
    "ToolResult",
    "WebResearchTool",
    "get_tool_executor",
    "reset_tool_executor",
]
