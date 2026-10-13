"""
guardian/core/agents.py
========================
Sub-agent infrastructure. Each agent has a named scope (allowed tool set)
and routes through the standard policy/executor pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from guardian.tools.executor import ToolRequest, ToolResult
from guardian.tools import get_tool_executor
from guardian.policy.engine import get_policy_engine, Effect


@dataclass
class AgentScope:
    allowed_tools: set[str]


class SubAgent:
    def __init__(self, name: str, scope: AgentScope):
        self.name = name
        self.scope = scope
        self.executor = get_tool_executor()
        self.engine = get_policy_engine()

    def execute_step(self, tool_name: str, params: dict[str, Any], session_id: str = "") -> ToolResult:
        """
        Execute a tool on behalf of this sub-agent.
        Enforces the sub-agent's specific scope before falling back to the standard policy engine.
        """
        # 1. Enforce agent-specific scope
        if tool_name not in self.scope.allowed_tools:
            from guardian.audit import get_audit_log
            audit = get_audit_log()
            audit.append("agent.scope_denied", actor=self.name, payload={"tool": tool_name})
            return ToolResult(
                success=False, output="",
                error=f"Tool {tool_name} is outside the scope of agent {self.name}",
                tool_name=tool_name,
            )

        # 2. Proceed with standard execution (policy engine, sandbox, etc.)
        req = ToolRequest(
            name=tool_name,
            params=params,
            context={"actor": self.name},
        )
        result = self.executor.run(req)
        return result


# ---------------------------------------------------------------------------
# Lazy agent registry – populated once on first access
# ---------------------------------------------------------------------------

_AGENTS: dict | None = None


def _ensure_agents() -> dict:
    global _AGENTS
    if _AGENTS is None:
        from guardian.core.agents_ext import ReconAgentImpl, AnalysisAgentImpl, ResponseAgentImpl
        from guardian.core.coding_agent import CodingAgent
        from guardian.core.security_agents import (
            BlueTeamAgent,
            RedTeamAgent,
            ComplianceAgent,
            SocialEngineeringAgent,
        )

        _AGENTS = {
            "recon": ReconAgentImpl("recon_agent", AgentScope(allowed_tools={"network_recon", "file_read", "search"})),
            "analysis": AnalysisAgentImpl("analysis_agent", AgentScope(allowed_tools={"db_query", "vision_analyze", "file_read"})),
            "response": ResponseAgentImpl("response_agent", AgentScope(allowed_tools={"shell", "file_write", "git_write", "code_exec"})),
            "coding": CodingAgent,
            "blue_team": BlueTeamAgent,
            "red_team": RedTeamAgent,
            "compliance": ComplianceAgent,
            "social_engineering": SocialEngineeringAgent,
        }
    return _AGENTS


# Module-level __getattr__ so callers can do:
#   from guardian.core.agents import ReconAgent, AnalysisAgent, ResponseAgent, AGENTS
def __getattr__(name: str):
    if name == "AGENTS":
        return _ensure_agents()
    if name == "SocialEngineeringAgent":
        return _ensure_agents()["social_engineering"]
    if name == "ReconAgent":
        return _ensure_agents()["recon"]
    if name == "AnalysisAgent":
        return _ensure_agents()["analysis"]
    if name == "ResponseAgent":
        return _ensure_agents()["response"]
    raise AttributeError(f"module 'guardian.core.agents' has no attribute {name!r}")


def get_agent_for_tool(tool_name: str) -> SubAgent | None:
    """Return the first agent whose scope includes tool_name, or None."""
    agents = _ensure_agents()
    for agent in agents.values():
        if hasattr(agent, "scope") and tool_name in agent.scope.allowed_tools:
            return agent
    return None
