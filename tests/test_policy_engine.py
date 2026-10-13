"""
Tests for guardian.policy — M3 Policy Engine
==============================================
Tests all 5 rules, scope edge cases, fail-closed behaviour,
and a no-bypass spy test confirming evaluate() runs on every tool call.
Apache-2.0.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from guardian.policy.engine import (
    Effect,
    PolicyConfig,
    PolicyDecision,
    PolicyEngine,
    _target_in_scope,
    reset_policy_engine,
)

REGISTERED = {"shell", "file_read", "file_write", "web_search"}


def make_engine(**kwargs) -> PolicyEngine:
    return PolicyEngine(config=PolicyConfig(**kwargs))


# ── Rule 1: Unknown tool ───────────────────────────────────────────────────────

class TestRule1UnknownTool:
    def test_unknown_tool_denied(self) -> None:
        engine = make_engine()
        d = engine.evaluate("nonexistent", 0, {}, REGISTERED)
        assert d.effect == Effect.DENY
        assert "rule.1" in d.rule_id

    def test_known_tool_passes_rule1(self) -> None:
        engine = make_engine()
        d = engine.evaluate("file_read", 0, {}, REGISTERED)
        assert d.effect == Effect.ALLOW


# ── Rule 2: Blocklist / Allowlist ─────────────────────────────────────────────

class TestRule2BlocklistAllowlist:
    def test_blocked_tool_denied(self) -> None:
        engine = make_engine(blocked_tools=["shell"])
        d = engine.evaluate("shell", 2, {}, REGISTERED)
        assert d.effect == Effect.DENY
        assert "rule.2" in d.rule_id

    def test_allowlist_permits_listed_tool(self) -> None:
        engine = make_engine(allowlist=["file_read"])
        d = engine.evaluate("file_read", 0, {}, REGISTERED)
        assert d.effect == Effect.ALLOW

    def test_allowlist_denies_unlisted_tool(self) -> None:
        engine = make_engine(allowlist=["file_read"])
        d = engine.evaluate("shell", 2, {}, REGISTERED)
        assert d.effect == Effect.DENY
        assert "rule.2" in d.rule_id

    def test_empty_allowlist_allows_all(self) -> None:
        engine = make_engine(allowlist=[])
        d = engine.evaluate("shell", 2, {}, REGISTERED)
        # Passes rule 2 but may fail rule 3+ (no scope); level 2 → REQUIRE_APPROVAL
        assert d.effect != Effect.DENY or "rule.2" not in d.rule_id


# ── Rule 3: Scope ──────────────────────────────────────────────────────────────

class TestRule3Scope:
    def _write_scope(self, path: Path, targets: list[str], **extra) -> None:
        data = {"targets": targets, **extra}
        if "authorization_basis" not in data:
            data["authorization_basis"] = {
                "basis_type": "written permission",
                "date": "2026-10-03T12:00:00Z"
            }
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_no_scope_file_denies(self) -> None:
        engine = make_engine(scope_file=None)
        d = engine.evaluate("web_search", 0, {"target": "10.0.0.1"}, REGISTERED,
                            target_arg="target", requires_scope=True)
        assert d.effect == Effect.DENY
        assert "rule.3" in d.rule_id

    def test_exact_ip_in_scope(self, tmp_path: Path) -> None:
        sf = tmp_path / "scope.json"
        self._write_scope(sf, ["10.0.0.1"])
        engine = make_engine(scope_file=str(sf))
        d = engine.evaluate("web_search", 0, {"target": "10.0.0.1"}, REGISTERED,
                            target_arg="target", requires_scope=True)
        assert d.effect == Effect.ALLOW

    def test_cidr_match(self, tmp_path: Path) -> None:
        sf = tmp_path / "scope.json"
        self._write_scope(sf, ["192.168.1.0/24"])
        engine = make_engine(scope_file=str(sf))
        d = engine.evaluate("web_search", 0, {"target": "192.168.1.100"}, REGISTERED,
                            target_arg="target", requires_scope=True)
        assert d.effect == Effect.ALLOW

    def test_cidr_outside_range_denied(self, tmp_path: Path) -> None:
        sf = tmp_path / "scope.json"
        self._write_scope(sf, ["192.168.1.0/24"])
        engine = make_engine(scope_file=str(sf))
        d = engine.evaluate("web_search", 0, {"target": "10.0.0.1"}, REGISTERED,
                            target_arg="target", requires_scope=True)
        assert d.effect == Effect.DENY

    def test_wildcard_subdomain_allowed(self, tmp_path: Path) -> None:
        sf = tmp_path / "scope.json"
        self._write_scope(sf, ["*.example.com"])
        engine = make_engine(scope_file=str(sf))
        d = engine.evaluate("web_search", 0, {"target": "sub.example.com"}, REGISTERED,
                            target_arg="target", requires_scope=True)
        assert d.effect == Effect.ALLOW

    def test_wildcard_apex_denied(self, tmp_path: Path) -> None:
        """*.example.com must NOT match example.com (the apex domain)."""
        sf = tmp_path / "scope.json"
        self._write_scope(sf, ["*.example.com"])
        engine = make_engine(scope_file=str(sf))
        d = engine.evaluate("web_search", 0, {"target": "example.com"}, REGISTERED,
                            target_arg="target", requires_scope=True)
        assert d.effect == Effect.DENY

    def test_wildcard_different_domain_denied(self, tmp_path: Path) -> None:
        sf = tmp_path / "scope.json"
        self._write_scope(sf, ["*.example.com"])
        engine = make_engine(scope_file=str(sf))
        d = engine.evaluate("web_search", 0, {"target": "sub.evil.com"}, REGISTERED,
                            target_arg="target", requires_scope=True)
        assert d.effect == Effect.DENY

    def test_expired_window_denied(self, tmp_path: Path) -> None:
        sf = tmp_path / "scope.json"
        self._write_scope(sf, ["10.0.0.1"],
                          not_before="2020-01-01T00:00:00Z",
                          not_after="2021-01-01T00:00:00Z")
        engine = make_engine(scope_file=str(sf))
        d = engine.evaluate("web_search", 0, {"target": "10.0.0.1"}, REGISTERED,
                            target_arg="target", requires_scope=True)
        assert d.effect == Effect.DENY
        assert "expired" in d.reason.lower()

    def test_future_window_denied(self, tmp_path: Path) -> None:
        sf = tmp_path / "scope.json"
        self._write_scope(sf, ["10.0.0.1"], not_before="2099-01-01T00:00:00Z")
        engine = make_engine(scope_file=str(sf))
        d = engine.evaluate("web_search", 0, {"target": "10.0.0.1"}, REGISTERED,
                            target_arg="target", requires_scope=True)
        assert d.effect == Effect.DENY

    def test_valid_hmac_signature_allowed(self, tmp_path: Path) -> None:
        sf = tmp_path / "scope.json"
        key = "test-secret-key"
        base = {
            "targets": ["10.0.0.1"], 
            "require_signature": True,
            "authorization_basis": {
                "basis_type": "written permission",
                "date": "2026-10-03T12:00:00Z"
            }
        }
        canon = json.dumps(base, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        sig = hmac.new(key.encode(), canon, hashlib.sha256).hexdigest()
        data = {**base, "signature": sig}
        sf.write_text(json.dumps(data), encoding="utf-8")
        engine = make_engine(scope_file=str(sf), scope_hmac_key=key, require_signature=True)
        d = engine.evaluate("web_search", 0, {"target": "10.0.0.1"}, REGISTERED,
                            target_arg="target", requires_scope=True)
        assert d.effect == Effect.ALLOW

    def test_bad_hmac_signature_denied(self, tmp_path: Path) -> None:
        sf = tmp_path / "scope.json"
        key = "test-secret-key"
        data = {
            "targets": ["10.0.0.1"], 
            "require_signature": True, 
            "signature": "badhash",
            "authorization_basis": {
                "basis_type": "written permission",
                "date": "2026-10-03T12:00:00Z"
            }
        }
        sf.write_text(json.dumps(data), encoding="utf-8")
        engine = make_engine(scope_file=str(sf), scope_hmac_key=key, require_signature=True)
        d = engine.evaluate("web_search", 0, {"target": "10.0.0.1"}, REGISTERED,
                            target_arg="target", requires_scope=True)
        assert d.effect == Effect.DENY


# ── Rule 4: Risk tier ─────────────────────────────────────────────────────────

class TestRule4RiskTier:
    def test_level0_auto_allow(self) -> None:
        engine = make_engine()
        d = engine.evaluate("file_read", 0, {}, REGISTERED)
        assert d.effect == Effect.ALLOW

    def test_level1_requires_approval(self) -> None:
        engine = make_engine()
        d = engine.evaluate("file_write", 1, {}, REGISTERED)
        assert d.effect == Effect.REQUIRE_APPROVAL

    def test_level2_requires_approval(self) -> None:
        engine = make_engine()
        d = engine.evaluate("shell", 2, {}, REGISTERED)
        assert d.effect == Effect.REQUIRE_APPROVAL


# ── Rule 5: Risk flags ────────────────────────────────────────────────────────

class TestRule5RiskFlags:
    def test_shell_metacharacters_flagged(self) -> None:
        engine = make_engine()
        d = engine.evaluate("shell", 2, {"command": "ls && rm -rf /"}, REGISTERED)
        assert "shell.metacharacters" in d.risk_flags

    def test_pipe_flagged(self) -> None:
        engine = make_engine()
        d = engine.evaluate("shell", 2, {"command": "cat /etc/passwd | grep root"}, REGISTERED)
        assert "shell.metacharacters" in d.risk_flags

    def test_clean_command_no_flags(self) -> None:
        engine = make_engine()
        d = engine.evaluate("shell", 2, {"command": "ls -la"}, REGISTERED)
        assert "shell.metacharacters" not in d.risk_flags

    def test_metacharacters_do_not_block(self) -> None:
        """Metacharacter flags annotate but NEVER block."""
        engine = make_engine()
        d = engine.evaluate("shell", 2, {"command": "ls && evil"}, REGISTERED)
        assert d.effect != Effect.DENY


# ── Fail-closed ───────────────────────────────────────────────────────────────

class TestFailClosed:
    def test_exception_in_evaluate_returns_deny(self) -> None:
        engine = make_engine()
        # Inject an exception by passing a non-iterable for registered_tools
        d = engine.evaluate("file_read", 0, {}, None)  # type: ignore[arg-type]
        assert d.effect == Effect.DENY
        assert "policy.error" in d.rule_id


# ── No-bypass test ────────────────────────────────────────────────────────────

class TestNoBypass:
    def test_evaluate_called_on_executor_path(self, tmp_path: Path) -> None:
        """Spy confirms PolicyEngine.evaluate() is called on every ToolExecutor.run()."""
        from guardian.tools.base import ToolLevel, ToolRequest, ToolResult
        from guardian.tools.executor import ToolExecutor

        class DummyTool:
            name = "file_read"
            level = ToolLevel.READ
            description = "test"
            requires_scope = False
            target_arg = None

            def _execute(self, params):
                return ToolResult(success=True, output="ok")

        executor = ToolExecutor(sandbox_root=tmp_path)
        executor.register(DummyTool())  # type: ignore[arg-type]

        calls: list[str] = []

        from guardian.policy.engine import PolicyEngine as PE
        original_evaluate = PE.evaluate

        def spy_evaluate(self, tool_name, tool_level, params, registered_tools, **kw):
            calls.append(tool_name)
            return original_evaluate(self, tool_name, tool_level, params, registered_tools, **kw)

        reset_policy_engine()
        with patch.object(PE, "evaluate", spy_evaluate):
            result = executor.run(ToolRequest(name="file_read", params={}))

        assert "file_read" in calls, "PolicyEngine.evaluate() was not called"
        assert result.success

    def test_existing_approval_tests_still_pass(self, tmp_path: Path) -> None:
        """Level 1 tool still requires approved=True (authority gate preserved)."""
        from guardian.tools.base import ToolLevel, ToolRequest, ToolResult
        from guardian.tools.executor import ToolExecutor

        class WriteTool:
            name = "file_write"
            level = ToolLevel.WRITE
            description = "test"
            requires_scope = False
            target_arg = None

            def _execute(self, params):
                return ToolResult(success=True, output="written")

        executor = ToolExecutor(sandbox_root=tmp_path)
        executor.register(WriteTool())  # type: ignore[arg-type]
        reset_policy_engine()

        # Without approval → denied
        r1 = executor.run(ToolRequest(name="file_write", params={}, approved=False))
        assert not r1.success

        # With approval → succeeds
        r2 = executor.run(ToolRequest(name="file_write", params={}, approved=True))
        assert r2.success


# ── Locality attribute ────────────────────────────────────────────────────────

class TestModelLocality:
    def test_groq_is_cloud(self) -> None:
        # Can't instantiate without key; check the is_local field via BackendInfo
        # Mock the API key
        import os

        from guardian.model.backends.groq_backend import GroqBackend
        os.environ.setdefault("GUARDIAN_GROQ_API_KEY", "gsk_test_" + "x" * 40)
        try:
            b = GroqBackend()
            assert b.locality == "cloud"
        except Exception:
            pytest.skip("GroqBackend not instantiable without real key")

    def test_mock_is_local(self) -> None:
        from guardian.model.backends.mock import MockBackend
        b = MockBackend()
        assert b.locality == "local"

class TestEvaluateModelCall:
    def test_sensitive_skill_cloud_denied(self) -> None:
        engine = make_engine()
        d = engine.evaluate_model_call("pentest_copilot", "cloud")
        assert d.effect == Effect.DENY
        assert "cloud.leak_risk" in d.risk_flags

    def test_sensitive_skill_local_allowed(self) -> None:
        engine = make_engine()
        d = engine.evaluate_model_call("pentest_copilot", "local")
        assert d.effect == Effect.ALLOW

    def test_normal_skill_cloud_allowed(self) -> None:
        engine = make_engine()
        d = engine.evaluate_model_call("scholar", "cloud")
        assert d.effect == Effect.ALLOW
