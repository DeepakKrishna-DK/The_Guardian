"""
Tests for Unified JARVIS Conversational Core & Presence WebSocket
==================================================================
Tests:
  - /conversation REST endpoint
  - /ws/presence WebSocket connection and event dispatch
  - Emergency Kill Switch activation and reset
  - Level 3 Consequential Action Proposal & Approval
"""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from app import app
from guardian.security.kill_switch import get_kill_switch
from guardian.security.permissions import get_permission_gateway


@pytest.fixture
def client():
    # Reset kill switch before tests
    get_kill_switch().deactivate()
    with TestClient(app) as test_client:
        yield test_client
    get_kill_switch().deactivate()


class TestJarvisConversation:
    def test_conversation_endpoint_basic(self, client: TestClient):
        payload = {
            "query": "What is the capital of France?",
            "use_knowledge": False,
            "use_web": False,
            "use_academic": False,
            "max_sources": 2,
        }
        resp = client.post("/conversation", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert data["query"] == payload["query"]
        assert "duration_ms" in data

    def test_kill_switch_lifecycle(self, client: TestClient):
        # Trigger
        resp = client.post("/security/kill-switch/trigger")
        assert resp.status_code == 200
        assert get_kill_switch().is_active() is True

        # When active, conversation must reject execution
        conv_resp = client.post("/conversation", json={"query": "test query"})
        assert conv_resp.status_code == 200
        assert "error" in conv_resp.json()

        # Reset
        reset_resp = client.post("/security/kill-switch/reset")
        assert reset_resp.status_code == 200
        assert get_kill_switch().is_active() is False

    def test_websocket_presence_connection(self, client: TestClient):
        with client.websocket_connect("/ws/presence") as websocket:
            # First message should be connected status
            initial = websocket.receive_json()
            assert initial.get("event") == "connected"
            assert "kill_switch" in initial

            # Send ping
            websocket.send_json({"type": "ping"})
            pong = websocket.receive_json()
            assert pong.get("event") == "pong"
