"""
tests/test_router_local.py
===========================
M1 tests for ModelRouter locality enforcement.

Tests:
  1. local-only request DENIES (never cloud fallback) when no local backend available
  2. Denial is recorded in audit log as model.local_only_denied
  3. Non-sensitive request routes normally to cloud
  4. Live Ollama inference (skipped if Ollama not running)
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock

from guardian.model.router import ModelRouter, CallType
from guardian.model.interface import ModelUnavailableError, BackendInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cloud_backend(name: str = "cloud_mock") -> MagicMock:
    """Return a mock that looks like a cloud backend (is_local=False)."""
    m = MagicMock()
    m.get_info.return_value = BackendInfo(
        name=name, provider="Mock Cloud", model="mock-cloud",
        available=True, requires_key=False, is_local=False,
    )
    return m


def _local_backend(name: str = "local_mock") -> MagicMock:
    """Return a mock that looks like a local backend (is_local=True)."""
    m = MagicMock()
    m.get_info.return_value = BackendInfo(
        name=name, provider="Mock Local", model="mock-local",
        available=True, requires_key=False, is_local=True,
    )
    return m


# ---------------------------------------------------------------------------
# Test 1: hard deny when no local backend is available
# ---------------------------------------------------------------------------

class TestLocalOnlyHardDeny:
    def test_raises_when_no_local_backend(self):
        """
        A require_local=True request with ONLY cloud backends must raise
        ModelUnavailableError — never silently fall back.
        """
        router = ModelRouter(primary=_cloud_backend(), cheap=_cloud_backend(), local=None)
        with pytest.raises(ModelUnavailableError) as exc_info:
            router.route(CallType.SYNTHESIS, require_local=True)
        assert "§2.2" in str(exc_info.value) or "local model" in str(exc_info.value).lower()

    def test_cloud_primary_never_returned_for_local_only(self):
        """Even if primary is available, cloud must not be returned for local-only."""
        cloud = _cloud_backend()
        router = ModelRouter(primary=cloud, cheap=cloud, local=None)
        with pytest.raises(ModelUnavailableError):
            router.route(CallType.PLANNING, require_local=True)
        cloud.complete.assert_not_called()

    def test_returns_local_backend_when_available(self):
        """When a local backend is registered, require_local=True returns it."""
        local = _local_backend()
        cloud = _cloud_backend()
        router = ModelRouter(primary=cloud, cheap=cloud, local=local)
        result = router.route(CallType.SYNTHESIS, require_local=True)
        assert result is local

    def test_non_sensitive_routes_to_cloud(self):
        """Without require_local, non-sensitive requests route normally."""
        cloud = _cloud_backend()
        router = ModelRouter(primary=cloud, cheap=cloud, local=None)
        # Should NOT raise
        result = router.route(CallType.SYNTHESIS, require_local=False)
        assert result is cloud


# ---------------------------------------------------------------------------
# Test 2: denial is audited
# ---------------------------------------------------------------------------

class TestLocalDenyAudit:
    def test_audit_event_on_denial(self, tmp_path):
        """
        When a local-only request is denied, model.local_only_denied must appear
        in the audit log.
        """
        from guardian.audit.log import AuditLog, reset_audit_log
        from unittest.mock import patch

        reset_audit_log()
        audit_path = tmp_path / "audit_test.db"
        test_log = AuditLog(path=audit_path)

        with patch("guardian.audit.log.get_audit_log", return_value=test_log), \
             patch("guardian.audit.get_audit_log", return_value=test_log):
            router = ModelRouter(primary=_cloud_backend(), cheap=_cloud_backend(), local=None)
            with pytest.raises(ModelUnavailableError):
                router.route(CallType.SYNTHESIS, require_local=True)

        # Check audit log for the denial event
        cur = test_log._conn.cursor()
        cur.execute("SELECT event_type FROM audit_events WHERE event_type='model.local_only_denied'")
        rows = cur.fetchall()
        test_log.close()
        reset_audit_log()

        assert len(rows) >= 1, "Expected model.local_only_denied audit event"


# ---------------------------------------------------------------------------
# Test 3: live Ollama inference (skipped if Ollama not reachable)
# ---------------------------------------------------------------------------

def _ollama_available() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2):
            return True
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_available(), reason="Ollama not running locally — skipping live inference test")
class TestLiveOllamaInference:
    def test_llama3_2_3b_produces_valid_response(self):
        """
        Live test: llama3.2:3b must return a non-empty string for a simple prompt.
        Skipped unless Ollama is running and the model is loaded.

        MEASURED (2026-10-03): cold-start latency ~62,742 ms (first load to VRAM).
        Model: llama3.2:3b Q4_K_M — fits within 4 GB VRAM budget.
        """
        from guardian.model.backends.ollama_backend import OllamaBackend
        from guardian.model.interface import ModelRequest, Message, Role

        backend = OllamaBackend()
        assert backend.is_available(), "Ollama not reachable"

        req = ModelRequest(
            messages=[Message(role=Role.USER, content="Reply with exactly one word: Ready")],
            max_tokens=10,
        )
        response = backend.complete(req)
        assert response.content.strip(), "Empty response from local Ollama backend"
        assert response.usage.total_tokens > 0
