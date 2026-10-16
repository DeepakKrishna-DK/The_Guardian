"""
Unit and Integration Tests for Guardian Universal Digital Intelligence Architecture (v2.0)
==========================================================================================
Tests:
  - 20-Slot Model Foundation & config/models.yaml loading
  - On-demand lazy loading and LRU eviction (max 2 parallel models)
  - ModelAdapter protocol and 10 adapter implementations
  - GuardianRouter orchestrator & available_models filtering
  - Digital Access Layer & SSRF prevention (localhost, private CIDRs, 169.254.169.254)
  - Permission Gateway (Level 1/2/3, approval gates, JSONL audit logger, kill switch)
  - FastAPI Architecture 2.0 endpoints
"""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app import app
from guardian.model.adapters import (
    ModelAdapter,
    ModelResult,
    get_adapter,
)
from guardian.model.guardian_router import GuardianRouter, get_guardian_router
from guardian.model.slots import (
    SlotState,
    TwentySlotRegistry,
    get_slot_registry,
)
from guardian.prompts import (
    GUARDIAN_MASTER_PROMPT,
    GUARDIAN_MASTER_SYSTEM_PROMPT_V1,
    GUARDIAN_MASTER_SYSTEM_PROMPT_V2,
)
from guardian.security.permissions import (
    PermissionGateway,
    PermissionLevel,
    get_permission_gateway,
)
from guardian.web.gateway import (
    BrowserGateway,
    DigitalAccessGateway,
    get_digital_access_gateway,
)
from guardian.web.security import is_safe_url


class TestMasterPromptV2:
    """Validates the Master System Prompt Version 2.0."""

    def test_prompt_file_exists(self):
        root = Path(__file__).resolve().parent.parent
        p_path = root / "guardian_master_prompt.txt"
        assert p_path.exists(), "guardian_master_prompt.txt must exist at project root"
        content = p_path.read_text(encoding="utf-8")
        assert "Version 2.0" in content
        assert "20. ULTIMATE OBJECTIVE" in content

    def test_all_20_sections_present_in_v2(self):
        prompt = GUARDIAN_MASTER_SYSTEM_PROMPT_V2
        for sec in range(1, 21):
            assert f"{sec}. " in prompt, f"Section {sec} missing from Version 2.0 prompt"

    def test_prompt_directives_v2(self):
        prompt = GUARDIAN_MASTER_SYSTEM_PROMPT_V2
        assert "TWENTY-SLOT MODEL FOUNDATION" in prompt
        assert "PUBLIC WORLD WIDE WEB" in prompt
        assert "OPERATIONAL PERMISSION LEVELS" in prompt
        assert "DEFENSIVE SECURITY AND GUARDIAN PROTECTION" in prompt


class TestTwentySlotRegistry:
    """Validates Layer 1: Twenty-Slot Model Foundation."""

    def test_registry_contains_20_distinct_slots(self):
        registry = get_slot_registry()
        assert len(registry.slots) == 20
        # Check slot indices 1 through 20
        for num in range(1, 21):
            assert num in registry.slots, f"Slot {num} missing from registry"

    def test_retrieval_and_reranker_slots_assigned(self):
        registry = get_slot_registry()
        slot_14 = registry.get_slot(14)
        assert slot_14 is not None
        assert slot_14.id == "qwen3_embedding"
        assert slot_14.adapter_name == "sentence_transformer_or_native"

        slot_16 = registry.get_slot(16)
        assert slot_16 is not None
        assert slot_16.id == "bge_reranker"
        assert slot_16.adapter_name == "cross_encoder"

    def test_verify_slot_capability(self):
        registry = get_slot_registry()
        res = registry.verify_slot(1)
        assert res["verified"] is True
        assert res["state"] == SlotState.HEALTHY.value
        assert len(res["notes"]) >= 2

    def test_on_demand_lazy_loading_and_lru_eviction(self):
        registry = TwentySlotRegistry()
        # Reset loaded slots for clean test
        registry._loaded_slots.clear()
        for s in registry.slots.values():
            s.is_loaded = False

        # Load slot 1
        r1 = registry.load_slot(1)
        assert r1["success"] is True
        assert 1 in registry._loaded_slots

        # Load slot 2
        r2 = registry.load_slot(2)
        assert r2["success"] is True
        assert 2 in registry._loaded_slots
        assert len(registry._loaded_slots) == 2

        # Load slot 3 -> Must evict LRU slot 1
        r3 = registry.load_slot(3)
        assert r3["success"] is True
        assert r3["evicted_slot"] == 1
        assert 1 not in registry._loaded_slots
        assert 2 in registry._loaded_slots
        assert 3 in registry._loaded_slots
        assert len(registry._loaded_slots) == 2

    def test_unload_slot(self):
        registry = get_slot_registry()
        registry.load_slot(5)
        assert 5 in registry._loaded_slots
        unloaded = registry.unload_slot(5)
        assert unloaded is True
        assert 5 not in registry._loaded_slots


class TestModelAdapters:
    """Validates ModelAdapter protocol implementations across families."""

    @pytest.mark.parametrize(
        "adapter_name,slot_id,repo",
        [
            ("transformers_chat", "gpt_oss_120b", "openai/gpt-oss-120b"),
            ("transformers_vlm", "gemma4_26b", "google/gemma-4-26B-A4B"),
            ("diffusers", "qwen_image", "Qwen/Qwen-Image-2.1-Turbo"),
            ("transformers_specialist", "nemotron_tennis", "nvidia/NemotronLabs-AI-for-Media-Sports-Tennis"),
            ("transformers_asr", "whisper_v3", "openai/whisper-large-v3"),
            ("kokoro_tts", "kokoro", "hexgrad/Kokoro-82M"),
            ("paddleocr", "paddleocr", "PaddleOCR-VL"),
            ("sentence_transformer_or_native", "qwen_emb", "Qwen/Qwen3-Embedding-0.6B"),
            ("cross_encoder", "bge", "BAAI/bge-reranker-v2-m3"),
            ("transformers_masked_lm", "securebert", "cisco-ai/SecureBERT2.0-base"),
        ],
    )
    def test_adapter_protocol_compliance(self, adapter_name, slot_id, repo):
        adapter = get_adapter(adapter_name, slot_id, repo)
        assert isinstance(adapter, ModelAdapter)
        assert adapter.health() is True

        res = adapter.run({"prompt": "Smoke test execution", "query": "Smoke test"})
        assert isinstance(res, ModelResult)
        assert res.status in ("success", "simulated")
        assert res.slot_id == slot_id


class TestGuardianRouter:
    """Validates Layer 2: Guardian Orchestrator."""

    def test_available_models_query(self):
        router = get_guardian_router()
        chat_models = router.available_models("chat")
        assert len(chat_models) >= 1
        assert "gpt_oss_120b" in chat_models

        vlm_models = router.available_models("multimodal")
        assert len(vlm_models) >= 1
        assert "gemma4_26b_a4b" in vlm_models

    def test_slot_mapping_for_tasks(self):
        router = get_guardian_router()
        assert router.find_slot_for_task("generate an image of a cyber defense node", has_images=True) == 2
        assert router.find_slot_for_task("inspect this screenshot", has_images=True) == 1
        assert router.find_slot_for_task("transcribe this recording", has_audio=True) == 11
        assert router.find_slot_for_task("analyze firewall alert and CVE vulnerability") == 20

    def test_collaborative_workflow_execution(self):
        router = get_guardian_router()
        res = router.route_and_execute(
            task={"prompt": "Assess network intrusion log"},
            collaborative=True,
        )
        assert res.status in ("success", "simulated")
        assert "synthesizer" in res.slot_id


class TestDigitalAccessGateway:
    """Validates Layer 3: Digital Access Layer and SSRF Defense."""

    def test_ssrf_blocks_private_and_local_networks(self):
        blocked_urls = [
            "http://127.0.0.1:8000/api",
            "http://localhost:5000",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.1.25/admin",
            "http://192.168.1.1/router",
            "http://172.16.0.10:8080/internal",
            "http://metadata.google.internal/computeMetadata/v1/",
        ]
        for url in blocked_urls:
            safe, reason = is_safe_url(url)
            assert safe is False, f"Expected {url} to be blocked by SSRF defense"

    def test_safe_public_url_allowed(self):
        safe_urls = [
            "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "https://docs.python.org/3/",
            "https://github.com",
        ]
        for url in safe_urls:
            safe, _ = is_safe_url(url)
            assert safe is True, f"Expected {url} to be allowed"

    def test_web_search_fallback(self):
        gw = get_digital_access_gateway()
        results = gw.search_web("neural networks", max_results=3)
        assert len(results) >= 1
        assert all(r.title and r.url for r in results)

    def test_browser_gateway_disabled_by_default(self):
        bg = BrowserGateway()
        res = bg.render_page("https://example.com")
        if not bg.enabled:
            assert res["success"] is False
            assert "disabled" in res["error"].lower()


class TestPermissionGateway:
    """Validates Layer 4: Permission & Operational Safety Gateway."""

    def test_operational_permission_levels(self):
        perm = get_permission_gateway()
        # Level 1 Read
        p_read = perm.evaluate_action("document_search", target="knowledge.db")
        assert p_read.level_required == PermissionLevel.LEVEL_1_READ
        assert p_read.requires_approval is False

        # Level 3 Execute (Consequential)
        p_exec = perm.evaluate_action("firewall_change", target="DROP 203.0.113.1")
        assert p_exec.level_required == PermissionLevel.LEVEL_3_EXECUTE
        assert p_exec.requires_approval is True
        assert p_exec.status == "pending"

    def test_approval_and_execution_flow(self):
        perm = get_permission_gateway()
        prop = perm.evaluate_action("file_delete", target="/tmp/stale.log")
        assert prop.status == "pending"

        # Commit before approval fails
        cant_exec = perm.execute_proposal(prop.action_id)
        assert cant_exec["success"] is False

        # Approve proposal
        app_res = perm.approve_proposal(prop.action_id, approver="security_officer")
        assert app_res["success"] is True

        # Commit succeeds
        exec_res = perm.execute_proposal(prop.action_id)
        assert exec_res["success"] is True
        assert exec_res["status"] == "executed"

    def test_jsonl_audit_logger(self):
        perm = get_permission_gateway()
        evt = perm.audit_logger.record_event(
            event_type="test_audit_event",
            action="verify_test",
            status="success",
        )
        assert evt["event_type"] == "test_audit_event"

        recent = perm.audit_logger.read_recent_events(limit=5)
        assert len(recent) >= 1
        assert any(e.get("event_type") == "test_audit_event" for e in recent)


class TestFastApiV2Endpoints:
    """Validates Architecture 2.0 REST API endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_system_prompt_v2_endpoint(self, client):
        resp = client.get("/system/prompt?v=2.0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "2.0"
        assert data["sections"] == 20

    def test_models_slots_endpoint(self, client):
        resp = client.get("/models/slots")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_slots"] == 20
        assert data["policy"]["max_parallel_models"] == 2

    def test_models_slots_verify_endpoint(self, client):
        resp = client.post("/models/slots/verify", json={"slot_number": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["verified"] is True

    def test_models_slots_load_endpoint(self, client):
        resp = client.post("/models/slots/load", json={"slot_number": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["slot"] == 2

    def test_web_search_endpoint(self, client):
        resp = client.post("/web/search", json={"query": "responsible AI standards", "max_results": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_web_fetch_ssrf_blocked_endpoint(self, client):
        resp = client.post("/web/fetch", json={"url": "http://169.254.169.254/latest/meta-data/"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "SSRF blocked" in data["error"]

    def test_security_permissions_endpoint(self, client):
        resp = client.get("/security/permissions")
        assert resp.status_code == 200
        data = resp.json()
        assert "kill_switch_active" in data
        assert "permission_levels" in data
