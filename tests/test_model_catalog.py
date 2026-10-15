"""
Unit Tests for Guardian Model Catalog, Task Router & Master Prompt v1.0
========================================================================
Verifies:
  - Guardian Master System Prompt v1.0 with all 18 sections
  - 20 Candidate model implementations and alias mapping (#3 and #14)
  - Modality, runtime, and hardware requirement validation
  - Section 5 Intelligent Task Routing across all tasks
  - Section 6 Multi-Model Collaboration planning
  - Section 8 & 17 Defensive Firewall Advisory generation
"""

from __future__ import annotations

import pytest

from guardian.model.catalog import (
    CandidateModelCatalog,
    HardwareRequirement,
    ModelDeployment,
    ModelHealthStatus,
    TrustLevel,
    get_candidate_catalog,
)
from guardian.model.task_router import (
    CollaborationRole,
    IntelligentTaskRouter,
    RoutingDecision,
    TaskType,
    get_task_router,
)
from guardian.prompts import (
    GUARDIAN_MASTER_PROMPT,
    GUARDIAN_MASTER_SYSTEM_PROMPT_V1,
    UIRA_MASTER_SYSTEM_PROMPT_V1,
)
from guardian.security.advisory import (
    DefensiveFirewallRecommendation,
    RuleAction,
    SecurityFindingReport,
    SeverityLevel,
    generate_firewall_advisory,
)


class TestGuardianMasterPromptV1:
    """Tests the 18 sections of Guardian Master System Prompt Version 1.0."""

    def test_all_18_sections_present(self):
        prompt = GUARDIAN_MASTER_SYSTEM_PROMPT_V1
        sections = [
            "## 1. IDENTITY",
            "## 2. CORE PRINCIPLES",
            "## 3. MODEL REGISTRY AND CAPABILITY DISCOVERY",
            "## 4. INITIAL MODEL CATALOG",
            "## 5. INTELLIGENT TASK ROUTING",
            "## 6. MULTI-MODEL COLLABORATION",
            "## 7. GUARDIAN DEFENSIVE SECURITY MISSION",
            "## 8. FIREWALL AND NETWORK CONTROL",
            "## 9. RESEARCH AND KNOWLEDGE MANAGEMENT",
            "## 10. SEMANTIC MEMORY AND RETRIEVAL",
            "## 11. PROMPT INJECTION AND UNTRUSTED INPUTS",
            "## 12. OUTPUT VALIDATION",
            "## 13. PRIVACY AND SECRET MANAGEMENT",
            "## 14. PERFORMANCE AND RESOURCE MANAGEMENT",
            "## 15. SELF-EVALUATION AND IMPROVEMENT",
            "## 16. FAILURE AND FALLBACK POLICY",
            "## 17. STANDARD RESPONSE FORMAT",
            "## 18. FINAL DIRECTIVE",
        ]
        for sec in sections:
            assert sec in prompt, f"Missing section {sec} in Master System Prompt"

    def test_master_prompt_core_directives(self):
        prompt = GUARDIAN_MASTER_SYSTEM_PROMPT_V1
        assert "Accuracy before confidence" in prompt
        assert "Evidence before assertion" in prompt
        assert "Treat every model ID in the initial user-supplied catalog as a CANDIDATE" in prompt
        assert "Never execute unreviewed remote model code with unrestricted system privileges" in prompt
        assert "Guardian's success is measured by verified outcomes, reduced risk" in prompt
        assert GUARDIAN_MASTER_PROMPT == GUARDIAN_MASTER_SYSTEM_PROMPT_V1


class TestCandidateModelCatalog:
    """Tests the Candidate Model Registry per Sections 3 & 4."""

    @pytest.fixture
    def catalog(self):
        return get_candidate_catalog()

    def test_catalog_entries_count(self, catalog: CandidateModelCatalog):
        all_models = catalog.list_all()
        # Catalog has 18 unique candidate model entries (#1-#20, with #14 as alias to #3)
        assert len(all_models) == 18

    def test_alias_resolution(self, catalog: CandidateModelCatalog):
        # Snippet #3 and Snippet #14 both refer to openai/gpt-oss-120b
        m3 = catalog.get("openai/gpt-oss-120b")
        assert m3 is not None
        assert m3.candidate_number == 3

        # Lookup by alias '#14'
        m14 = catalog.get("#14")
        assert m14 is not None
        assert m14.model_id == "openai/gpt-oss-120b"

    def test_multimodal_models(self, catalog: CandidateModelCatalog):
        image_models = catalog.filter(modality="image")
        model_ids = [m.model_id for m in image_models]
        assert "google/gemma-4-26B-A4B" in model_ids
        assert "google/gemma-4-31B-it" in model_ids
        assert "Qwen/Qwen3.8-27B" in model_ids
        assert "microsoft/Fara1.5-27B" in model_ids
        assert "Qwen/Qwen-Image-2.1-Turbo" in model_ids

    def test_audio_and_ocr_models(self, catalog: CandidateModelCatalog):
        whisper = catalog.get("openai/whisper-large-v3")
        assert whisper is not None
        assert "audio" in whisper.input_modalities

        kokoro = catalog.get("hexgrad/Kokoro-82M")
        assert kokoro is not None
        assert "audio" in kokoro.output_modalities

        ocr = catalog.get("PaddleOCR-VL")
        assert ocr is not None
        assert "pdf" in ocr.input_modalities
        assert "ocr" in ocr.capability_tags

    def test_security_model(self, catalog: CandidateModelCatalog):
        sec = catalog.get("cisco-ai/SecureBERT2.0-base")
        assert sec is not None
        assert "security" in sec.capability_tags
        assert "masked_text" in sec.output_modalities

    def test_custom_code_flagged_models(self, catalog: CandidateModelCatalog):
        custom_code_models = catalog.filter(requires_custom_code=True)
        ids = [m.model_id for m in custom_code_models]
        assert "deepseek-ai/DeepSeek-R1" in ids
        assert "nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4" in ids

    def test_hardware_verification(self, catalog: CandidateModelCatalog):
        # Host with 16GB RAM and 4GB VRAM
        report = catalog.verify_candidate_eligibility("deepseek-ai/DeepSeek-R1", available_ram_gb=16.0, available_vram_gb=4.0)
        assert report["security_sandbox_required"] is True
        assert len(report["warnings"]) > 0
        assert report["recommended_deployment"] == "hosted"


class TestIntelligentTaskRouter:
    """Tests Section 5 task classification and routing logic."""

    @pytest.fixture
    def router(self):
        return get_task_router()

    def test_route_image_creation(self, router: IntelligentTaskRouter):
        decision = router.route_request("Please generate a detailed 8k image of an astronaut in a jungle")
        assert decision.task_type == TaskType.IMAGE_CREATION
        assert decision.selected_model_or_tool == "Qwen/Qwen-Image-2.1-Turbo"
        assert "image" in decision.output_modalities

    def test_route_image_understanding(self, router: IntelligentTaskRouter):
        decision = router.route_request("What animal is on the candy?", has_images=True)
        assert decision.task_type == TaskType.IMAGE_UNDERSTANDING
        assert decision.selected_model_or_tool == "google/gemma-4-26B-A4B"

    def test_route_speech_transcription(self, router: IntelligentTaskRouter):
        decision = router.route_request("Transcribe this speech recording", has_audio=True)
        assert decision.task_type == TaskType.SPEECH_TRANSCRIPTION
        assert decision.selected_model_or_tool == "openai/whisper-large-v3"

    def test_route_speech_synthesis(self, router: IntelligentTaskRouter):
        decision = router.route_request("Read aloud the following text with voice synthesis")
        assert decision.task_type == TaskType.SPEECH_SYNTHESIS
        assert decision.selected_model_or_tool == "hexgrad/Kokoro-82M"

    def test_route_ocr(self, router: IntelligentTaskRouter):
        decision = router.route_request("Extract text and tables from this scanned document", has_pdf=True)
        assert decision.task_type == TaskType.OCR_DOCUMENT_EXTRACTION
        assert decision.selected_model_or_tool == "PaddleOCR-VL"

    def test_route_biomedical(self, router: IntelligentTaskRouter):
        decision = router.route_request("Summarize the clinical pathology and genetics of leukemia")
        assert decision.task_type == TaskType.SCIENTIFIC_BIOMEDICAL
        assert decision.selected_model_or_tool == "BioMistral/BioMistral-7B"
        assert decision.requires_external_evidence is True

    def test_route_security(self, router: IntelligentTaskRouter):
        decision = router.route_request("Analyze this firewall log and detect potential malware exploit attempts")
        assert decision.task_type == TaskType.SECURITY_ALERT_ANALYSIS
        assert "SecureBERT" in decision.selected_model_or_tool

    def test_route_complex_reasoning(self, router: IntelligentTaskRouter):
        decision = router.route_request("Prove that the square root of 2 is irrational using formal deduction")
        assert decision.task_type == TaskType.COMPLEX_REASONING
        assert decision.selected_model_or_tool == "deepseek-ai/DeepSeek-R1"

    def test_standard_response_formatting(self, router: IntelligentTaskRouter):
        decision = router.route_request("What is quantum entanglement?")
        report = decision.format_routing_report()
        assert "**Selected Model / Tool**:" in report
        assert "**Why Selected**:" in report
        assert "**Execution Status**:" in report


class TestDefensiveSecurityAdvisory:
    """Tests Section 8 and Section 17 security advisory and firewall rules."""

    def test_firewall_advisory_contains_8_required_fields(self):
        advisory = generate_firewall_advisory(
            evidence="Port scan detected on ports 22, 80, 443 from 203.0.113.19",
            src_dest="SRC 203.0.113.19 -> DST 10.0.0.1",
            ports="TCP / 22, 80, 443",
            outcome="Block malicious scanning IP",
            impact="None on production users",
            false_positives="Shared NAT gateway",
            rollback="iptables -D INPUT -s 203.0.113.19 -j DROP",
            verification="Confirm drop counters increment",
            action=RuleAction.DROP,
        )
        assert advisory.mode == "ADVISORY_READ_ONLY"
        assert advisory.requires_human_confirmation is True
        md = advisory.format_markdown()
        assert "Observed Evidence" in md
        assert "Source & Destination Scope" in md
        assert "Protocol & Ports" in md
        assert "Intended Security Outcome" in md
        assert "Expected Operational Impact" in md
        assert "Potential False Positives" in md
        assert "Rollback Plan" in md
        assert "Verification Procedure" in md
        assert "Human Authorization Required" in md

    def test_security_finding_report(self):
        finding = SecurityFindingReport(
            severity=SeverityLevel.HIGH,
            confidence=0.92,
            affected_asset_and_scope="Gateway SSH Service",
            evidence="Auth failures exceeded threshold",
            potential_impact="Unauthorized access / brute force compromise",
            recommended_remediation="Enforce key-based auth and rate limiting",
            verification_steps="Attempt connection without private key",
            rollback_considerations="Restore previous sshd_config from backup",
            requires_human_decision=True,
        )
        assert finding.requires_human_decision is True
        md = finding.format_markdown()
        assert "HIGH" in md
        assert "92%" in md
        assert "Gateway SSH Service" in md


class TestAppCatalogEndpoints:
    """Tests the new FastAPI endpoints in app.py."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app import app
        return TestClient(app)

    def test_get_models_catalog_endpoint(self, client):
        resp = client.get("/models/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["catalog_version"] == "1.0"
        assert data["total_candidate_models"] == 18
        assert len(data["models"]) == 18

    def test_models_route_endpoint(self, client):
        payload = {"query": "Please draw an astronaut riding a horse", "has_images": True}
        resp = client.post("/models/route", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "decision" in data
        assert "routing_report" in data
        assert data["decision"]["task_type"] == "image_creation"

    def test_security_advisory_endpoint(self, client):
        payload = {
            "evidence": "SQL injection attempts in user-agent header",
            "source_dest": "SRC 198.51.100.9 -> DST 10.0.0.8:80",
            "protocol_ports": "TCP / 80, 443",
            "intended_outcome": "Block malicious web application attack source",
            "expected_impact": "Malicious requests dropped",
            "potential_false_positives": "None identified",
            "rollback_plan": "iptables -D INPUT -s 198.51.100.9 -j DROP",
            "verification_procedure": "curl test from probe host",
            "action": "DROP",
        }
        resp = client.post("/security/advisory", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "advisory" in data
        assert "markdown" in data
        assert data["advisory"]["mode"] == "ADVISORY_READ_ONLY"

    def test_system_prompt_endpoint(self, client):
        resp = client.get("/system/prompt")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "1.0"
        assert data["sections"] == 18
        assert "GUARDIAN AI — MASTER SYSTEM PROMPT" in data["prompt"]

