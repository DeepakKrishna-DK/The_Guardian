"""
Guardian MCP Adapter — guardian/mcp/adapter.py
================================================
The ONLY module outside guardian/mcp/ that should import the `mcp` SDK.

This wrapper isolates the rest of the codebase from SDK internals so that
the SDK can be swapped or version-pinned without touching application logic.

Installed SDK: mcp==2.2.0
Target spec revision: 2026-07-28 (stateless, Streamable HTTP transport)

Known gaps vs 2026-07-28 spec:
  - SDK 2.2.0 may still support HTTP+SSE (deprecated in 2026-07-28 spec).
    guardian/mcp/server.py uses stdio only — this is compliant.
  - Roots, Sampling, Logging: deprecated in 2026-07-28. Not used in server.py.
  - "Streamable HTTP" transport: not yet implemented; server uses stdio only.
    This is acceptable for local-first operation (see ADR-0003).

Apache-2.0. The mcp SDK license is MIT.
"""

from __future__ import annotations

import importlib.metadata
from typing import Any

# ── SDK version constants ─────────────────────────────────────────────────────

TARGET_SPEC_REVISION = "2026-07-28"

def get_sdk_version() -> str:
    """Return the installed mcp SDK version string."""
    try:
        return importlib.metadata.version("mcp")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def get_sdk_protocol_versions() -> list[str]:
    """
    Return the protocol versions supported by the installed SDK, if exposed.
    Falls back to empty list if the SDK does not expose this information.
    """
    try:
        import mcp.types as _t
        ver = getattr(_t, "LATEST_PROTOCOL_VERSION", None)
        if ver:
            return [str(ver)]
    except Exception:
        pass
    return []


# ── Thin wrapper ──────────────────────────────────────────────────────────────

class MCPAdapter:
    """
    Thin wrapper over the mcp SDK.

    Exposes only the operations needed by the rest of Guardian:
        list_tools()    → list of tool descriptors
        call_tool()     → tool result dict

    All mcp SDK imports are confined to this class. Application code
    must import MCPAdapter, not mcp directly.
    """

    def __init__(self, server_params: Any | None = None) -> None:
        self._command: str | None = None
        self._args: list[str] | None = None
        if server_params is not None:
            self._command = getattr(server_params, "command", None)
            self._args = getattr(server_params, "args", None)
        self._sdk_version = get_sdk_version()
        self._protocol_versions = get_sdk_protocol_versions()

    def connect_stdio(self, command: str, args: list[str]) -> None:
        self._command = command
        self._args = args

    def list_tools(self) -> list[dict[str, Any]]:
        """Return tool descriptors from the connected MCP server."""
        if not self._command:
            return []
            
        import asyncio
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from mcp.client.session import ClientSession

        params = StdioServerParameters(command=self._command, args=self._args or [])
        
        async def _run():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    res = await session.list_tools()
                    return [{"name": t.name, "description": t.description, "inputSchema": t.inputSchema} for t in res.tools]
                    
        return asyncio.run(_run())

    def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool on the connected MCP server."""
        if not self._command:
            raise ValueError("MCPAdapter not connected")
            
        import asyncio
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from mcp.client.session import ClientSession

        params = StdioServerParameters(command=self._command, args=self._args or [])
        
        async def _run():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    res = await session.call_tool(name, arguments=args)
                    return {"content": [c.model_dump() for c in res.content], "isError": res.isError}
                    
        return asyncio.run(_run())

    @property
    def sdk_version(self) -> str:
        return self._sdk_version

    @property
    def protocol_versions(self) -> list[str]:
        return self._protocol_versions

    @property
    def target_spec_revision(self) -> str:
        return TARGET_SPEC_REVISION


def log_startup_info() -> None:
    """
    Log MCP SDK version and protocol info to the audit log at startup.
    Call once from the application entrypoint.
    """
    try:
        from guardian.audit import get_audit_log
        get_audit_log().append(
            "mcp.startup",
            actor="guardian.mcp.adapter",
            payload={
                "sdk_version": get_sdk_version(),
                "protocol_versions": get_sdk_protocol_versions(),
                "target_spec_revision": TARGET_SPEC_REVISION,
            },
        )
    except Exception:
        pass
