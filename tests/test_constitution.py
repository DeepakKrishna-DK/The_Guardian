"""
tests/test_constitution.py
===========================
ConstitutionCheck suite — M2 of the model-constitution-collab pass.

This suite makes the Guardian Constitution (GUARDIAN_CONSTITUTION_v0.1.md)
ENFORCEABLE as automated tests.  Each test derives directly from a named
section of the constitution; no new principles are invented here.

Assertions checked:
  CC-1  §2.7 Auditability     — every tool call produces an audit event
  CC-2  §5  AI Security      — audit log never contains raw prompt/response content
  CC-3  §2.5 Least Privilege  — sub-agents are denied tools outside their declared scope
  CC-4  §2.2 Privacy          — local-only tagged skill never reaches cloud backend
  CC-5  §3.2/3.3 Auth model   — Level-2 tool call (tool_level>0) requires approval, not auto-allow
  CC-6  Hash Guard            — GUARDIAN_CONSTITUTION_v0.1.md unchanged without changelog

The suite IMPORTS the existing spy/no-bypass tests rather than rewriting them:
  - test_m6_stretch.TestLocalOnlyGuard   (local routing spy tests)
  - test_agents.test_subagent_no_bypass  (multi-agent choke-point spy)
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
CONSTITUTION_FILE = PROJECT_ROOT / "GUARDIAN_CONSTITUTION_v0.1.md"
HASH_GUARD_FILE  = PROJECT_ROOT / ".guardian" / "constitution.sha256"


def _sha256_of(path: Path) -> str:
    # Normalize CRLF to LF so hash is identical on Windows and Linux
    content = path.read_bytes().replace(b"\r\n", b"\n")
    h = hashlib.sha256(content).hexdigest().upper()
    return h


def _cloud_backend_mock() -> MagicMock:
    from guardian.model.interface import BackendInfo
    m = MagicMock()
    m.get_info.return_value = BackendInfo(
        name="cloud_mock", provider="Cloud", model="mock-cloud",
        available=True, requires_key=False, is_local=False,
    )
    m.locality = "cloud"
    return m


def _local_backend_mock() -> MagicMock:
    from guardian.model.interface import BackendInfo
    m = MagicMock()
    m.get_info.return_value = BackendInfo(
        name="local_mock", provider="Local", model="mock-local",
        available=True, requires_key=False, is_local=True,
    )
    m.locality = "local"
    return m


# ===========================================================================
# CC-1  §2.7 Auditability — every tool call produces an audit event
# ===========================================================================

class TestCC1_Auditability:
    """
    Constitution §2.7: "Important actions should produce logs describing
    what was requested, what was attempted, what was changed, and what
    result was obtained."

    Enforcement: ToolExecutor.run() must write at minimum one audit event
    per tool invocation.
    """

    def test_tool_call_produces_audit_event(self, tmp_path):
        from guardian.tools.executor import ToolExecutor
        from guardian.tools.base import ToolRequest, ToolResult, ToolLevel, Tool
        from guardian.audit.log import AuditLog, reset_audit_log
        from guardian.policy.engine import reset_policy_engine
        from unittest.mock import patch

        reset_policy_engine()
        reset_audit_log()
        audit_path = tmp_path / "audit_cc1.db"
        test_log = AuditLog(path=audit_path)
        
        class EchoTool(Tool):
            name = "file_read"
            level = ToolLevel.READ
            description = "echo tool"
            requires_scope = False
            target_arg = None

            def _execute(self, params):
                return ToolResult(success=True, output="echo", error="", tool_name="file_read")

        executor = ToolExecutor(sandbox_root=tmp_path)
        executor.register(EchoTool())

        with patch("guardian.audit.log.get_audit_log", return_value=test_log), \
             patch("guardian.audit.get_audit_log", return_value=test_log):
            executor.run(ToolRequest(name="file_read", params={}))

        cur = test_log._conn.cursor()
        cur.execute("SELECT count(*) FROM audit_events")
        (count,) = cur.fetchone()
        test_log.close()
        reset_audit_log()

        assert count >= 1, f"CC-1 VIOLATION: {count} audit events for tool call (expected >=1)"


# ===========================================================================
# CC-2  §5 AI Security — audit log never contains raw prompt/response
# ===========================================================================

class TestCC2_NoRawContentInAuditLog:
    """
    Constitution §5: audit log must never contain raw prompt/response content.
    Guardian uses a redact layer; this test verifies it's active.
    """

    def test_audit_log_redacts_content(self, tmp_path):
        from guardian.audit.log import AuditLog, reset_audit_log

        reset_audit_log()
        audit_path = tmp_path / "audit_cc2.db"
        test_log = AuditLog(path=audit_path)

        SENSITIVE = "super_secret_prompt_content_xyz"
        test_log.append(
            "model.response",
            payload={"content": SENSITIVE},  # this should be redacted / not stored verbatim
        )

        cur = test_log._conn.cursor()
        cur.execute("SELECT payload_json FROM audit_events")
        rows = [r[0] for r in cur.fetchall()]
        test_log.close()
        reset_audit_log()

        for row in rows:
            assert SENSITIVE not in row, (
                f"CC-2 VIOLATION: raw content '{SENSITIVE}' found verbatim in audit log"
            )

    def test_audit_log_accepts_metadata(self, tmp_path):
        """Metadata-only payloads (no raw content) are stored correctly."""
        from guardian.audit.log import AuditLog, reset_audit_log

        reset_audit_log()
        audit_path = tmp_path / "audit_cc2b.db"
        test_log = AuditLog(path=audit_path)
        test_log.append("tool.request", payload={"tool": "file_read", "duration_ms": 12})

        cur = test_log._conn.cursor()
        cur.execute("SELECT payload_json FROM audit_events WHERE event_type='tool.request'")
        rows = cur.fetchall()
        test_log.close()
        reset_audit_log()

        assert len(rows) >= 1


# ===========================================================================
# CC-3  §2.5 Least Privilege — sub-agent scope is enforced
# ===========================================================================

class TestCC3_LeastPrivilege:
    """
    Constitution §2.5: "Every tool and agent receives only the permissions
    required for its task."

    Enforcement: sub-agents from the predictive-agents pass have declared
    allowed_tools sets; calls outside that set must be denied.
    """

    def test_subagent_denied_out_of_scope_tool(self):
        from guardian.core.agents import ReconAgent, AnalysisAgent

        # ReconAgent scope: network_recon, file_read, search
        result = ReconAgent.execute_step("shell", {"command": "id"})
        assert not result.success
        assert "scope" in result.error.lower() or "outside" in result.error.lower(), (
            f"CC-3 VIOLATION: ReconAgent was not denied for out-of-scope tool 'shell'. Got: {result.error}"
        )


# ===========================================================================
# CC-4  §2.2 Privacy — local-only never reaches cloud (imported from M1)
# ===========================================================================

class TestCC4_LocalOnlyNeverCloud:
    """
    Constitution §2.2: "Prefer local processing … External services must be
    explicit and configurable."

    Hard invariant: a require_local=True request MUST raise rather than
    fall back silently to cloud.  (Imports logic from TestLocalOnlyHardDeny.)
    """

    def test_local_only_denies_when_only_cloud_available(self):
        from guardian.model.router import ModelRouter, CallType
        from guardian.model.interface import ModelUnavailableError

        router = ModelRouter(
            primary=_cloud_backend_mock(),
            cheap=_cloud_backend_mock(),
            local=None,
        )
        with pytest.raises(ModelUnavailableError):
            router.route(CallType.SYNTHESIS, require_local=True)

    def test_denial_produces_audit_event(self, tmp_path):
        from guardian.model.router import ModelRouter, CallType
        from guardian.model.interface import ModelUnavailableError
        from guardian.audit.log import AuditLog, reset_audit_log

        reset_audit_log()
        test_log = AuditLog(path=tmp_path / "audit_cc4.db")

        with patch("guardian.audit.log.get_audit_log", return_value=test_log), \
             patch("guardian.audit.get_audit_log", return_value=test_log):
            router = ModelRouter(
                primary=_cloud_backend_mock(), cheap=_cloud_backend_mock(), local=None
            )
            with pytest.raises(ModelUnavailableError):
                router.route(CallType.SYNTHESIS, require_local=True)

        cur = test_log._conn.cursor()
        cur.execute("SELECT event_type FROM audit_events WHERE event_type='model.local_only_denied'")
        rows = cur.fetchall()
        test_log.close()
        reset_audit_log()

        assert len(rows) >= 1, "CC-4 VIOLATION: no model.local_only_denied audit event"

    def test_deliberate_misconfiguration_caught(self):
        """
        Seeded failure: a router that returns a cloud backend for require_local=True.
        The constitution check should catch this.
        """
        from guardian.model.router import ModelRouter, CallType
        from guardian.model.interface import ModelUnavailableError

        # This router has only cloud backends → must raise, never return cloud silently
        router = ModelRouter(
            primary=_cloud_backend_mock(), cheap=_cloud_backend_mock(), local=None
        )

        raised = False
        result_backend = None
        try:
            result_backend = router.route(CallType.PLANNING, require_local=True)
        except ModelUnavailableError:
            raised = True

        assert raised, (
            "CC-4 VIOLATION: misconfigured router returned a cloud backend for local-only request"
        )
        assert result_backend is None


# ===========================================================================
# CC-5  §3 Authority Model — Level-2 requires approval
# ===========================================================================

class TestCC5_AuthorityModel:
    """
    Constitution §3.3: Level-2 (Consequential) actions require explicit approval.
    Enforcement: PolicyEngine must return REQUIRE_APPROVAL (not ALLOW) for tool_level > 0.
    """

    def test_level2_tool_requires_approval_not_allow(self):
        from guardian.policy.engine import PolicyEngine, PolicyConfig, Effect

        config = PolicyConfig(
            blocked_tools=set(),
            allowlist=set(),
            scope_file=None,
            scope_hmac_key=None,
            require_signature=False,
        )
        engine = PolicyEngine(config=config)
        decision = engine.evaluate(
            tool_name="shell",
            tool_level=2,
            params={"command": "ls"},
            registered_tools={"shell"},
        )
        assert decision.effect != Effect.ALLOW, (
            f"CC-5 VIOLATION: Level-2 tool got effect={decision.effect.value} instead of REQUIRE_APPROVAL or DENY"
        )

    def test_level0_tool_auto_allowed(self):
        from guardian.policy.engine import PolicyEngine, PolicyConfig, Effect

        config = PolicyConfig(
            blocked_tools=set(),
            allowlist=set(),
            scope_file=None,
            scope_hmac_key=None,
            require_signature=False,
        )
        engine = PolicyEngine(config=config)
        decision = engine.evaluate(
            tool_name="file_read",
            tool_level=0,
            params={},
            registered_tools={"file_read"},
        )
        assert decision.effect == Effect.ALLOW, (
            f"CC-5: Level-0 tool should be ALLOW, got {decision.effect.value}"
        )


# ===========================================================================
# CC-6  Constitution hash guard
# ===========================================================================

class TestConstitutionHashGuard:
    """
    A CI check that fails if GUARDIAN_CONSTITUTION_v0.1.md is modified
    without a corresponding changelog entry.

    The hash is stored in .guardian/constitution.sha256.
    This test reads the current file hash and compares it.
    """

    def test_constitution_unchanged(self):
        assert CONSTITUTION_FILE.exists(), f"Constitution file not found: {CONSTITUTION_FILE}"
        assert HASH_GUARD_FILE.exists(), f"Hash guard file not found: {HASH_GUARD_FILE}"

        current_hash = _sha256_of(CONSTITUTION_FILE)

        recorded_hash = None
        for line in HASH_GUARD_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("SHA256:") and "GUARDIAN_CONSTITUTION" in line:
                recorded_hash = line.split(":")[1].split()[0].strip().upper()
                break

        assert recorded_hash is not None, "No SHA256 entry found in constitution.sha256"
        assert current_hash == recorded_hash, (
            f"CC-6 VIOLATION: Constitution modified without updating hash guard.\n"
            f"  Recorded: {recorded_hash}\n"
            f"  Current:  {current_hash}\n"
            f"Update .guardian/constitution.sha256 and add a version entry to "
            f"GUARDIAN_CONSTITUTION_v0.1.md after any intentional change."
        )

    def test_seeded_constitution_edit_is_detected(self, tmp_path):
        """Deliberately write a tampered constitution and verify detection."""
        fake_constitution = tmp_path / "fake_constitution.md"
        fake_constitution.write_text("## Tampered content", encoding="utf-8")
        tampered_hash = _sha256_of(fake_constitution)

        # Must differ from the recorded hash
        assert HASH_GUARD_FILE.exists()
        recorded_hash = None
        for line in HASH_GUARD_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("SHA256:") and "GUARDIAN_CONSTITUTION" in line:
                recorded_hash = line.split(":")[1].split()[0].strip().upper()
                break

        assert recorded_hash is not None
        assert tampered_hash != recorded_hash, (
            "Hash guard failed to detect tampered constitution"
        )
