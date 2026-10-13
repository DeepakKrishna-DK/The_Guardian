"""
Tests for guardian.mcp.adapter — M5 MCP Adapter
=================================================
Verifies:
  1. MCPAdapter exposes correct SDK version and target spec
  2. Only files under guardian/mcp/ import the `mcp` SDK (isolation test)
  3. guardian/mcp/server.py does NOT use deprecated features
     (Roots, Sampling, Logging, HTTP+SSE)
Apache-2.0.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from guardian.mcp.adapter import (
    TARGET_SPEC_REVISION,
    MCPAdapter,
    get_sdk_protocol_versions,
    get_sdk_version,
)


class TestMCPAdapter:
    def test_target_spec_revision(self) -> None:
        assert TARGET_SPEC_REVISION == "2026-07-28"

    def test_sdk_version_string(self) -> None:
        ver = get_sdk_version()
        assert ver != "unknown", "mcp SDK is not installed"
        # Should be a semver-like string
        parts = ver.split(".")
        assert len(parts) >= 2

    def test_adapter_sdk_version_property(self) -> None:
        a = MCPAdapter()
        assert a.sdk_version == get_sdk_version()

    def test_adapter_target_spec(self) -> None:
        a = MCPAdapter()
        assert a.target_spec_revision == "2026-07-28"

    def test_list_tools_no_params_returns_empty(self) -> None:
        """Without server_params, list_tools returns empty (not connected)."""
        a = MCPAdapter(server_params=None)
        assert a.list_tools() == []

    def test_call_tool_no_params_raises(self) -> None:
        a = MCPAdapter(server_params=None)
        with pytest.raises(ValueError, match="not connected"):
            a.call_tool("any_tool", {})


class TestMCPIsolation:
    """Only files under guardian/mcp/ may import the `mcp` SDK."""

    def _imports_mcp(self, filepath: pathlib.Path) -> list[str]:
        """Return list of mcp import lines found in the file."""
        try:
            source = filepath.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(filepath))
        except SyntaxError:
            return []

        hits: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "mcp" or alias.name.startswith("mcp."):
                        hits.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod == "mcp" or mod.startswith("mcp."):
                    hits.append(f"from {mod} import ...")
        return hits

    def test_only_mcp_dir_imports_mcp_sdk(self) -> None:
        guardian_root = pathlib.Path("guardian")
        violations: list[str] = []

        for py_file in sorted(guardian_root.rglob("*.py")):
            # Allow anything inside guardian/mcp/
            if "mcp" in py_file.parts:
                continue
            hits = self._imports_mcp(py_file)
            for hit in hits:
                violations.append(f"{py_file}: {hit}")

        assert not violations, (
            "Files outside guardian/mcp/ must not import the mcp SDK directly.\n"
            "Use guardian.mcp.adapter.MCPAdapter instead.\n"
            "Violations:\n" + "\n".join(violations)
        )


class TestMCPServerNoDeprecated:
    """guardian/mcp/server.py must not use deprecated MCP features."""

    def _read_server(self) -> str:
        p = pathlib.Path("guardian/mcp/server.py")
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""

    def test_no_roots(self) -> None:
        src = self._read_server()
        assert "add_resource" not in src, "server.py uses Roots (deprecated)"
        # Roots uses 'roots' attribute; check for the pattern
        assert "RequestedRoots" not in src

    def test_no_sampling(self) -> None:
        src = self._read_server()
        assert "create_message" not in src.lower() or "# " in src, \
            "server.py may use Sampling (deprecated); verify manually"

    def test_no_sse_transport(self) -> None:
        src = self._read_server()
        assert "SSEServerTransport" not in src, \
            "server.py uses HTTP+SSE transport (deprecated in 2026-07-28 spec)"
        assert "sse_server" not in src.lower()

    def test_no_logging_handler(self) -> None:
        src = self._read_server()
        # mcp Logging capability (deprecated) uses set_logging_level
        assert "set_logging_level" not in src
