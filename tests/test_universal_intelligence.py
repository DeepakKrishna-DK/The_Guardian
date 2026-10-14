"""
Unit Tests for Universal Intelligence & Knowledge Framework
============================================================
Verifies:
  - 25 Master Knowledge Domains across 6 Ontological Layers
  - 15 Study Dimensions
  - Automatic Domain Classification & Context Tagging
  - Universal Intelligence Prompts and Principles
"""

from __future__ import annotations

import pytest

from guardian.knowledge.domains import (
    DOMAINS,
    STUDY_DIMENSIONS,
    KnowledgeDomain,
    KnowledgeLayerEnum,
    classify_domain_context,
    get_all_domains,
    get_domain,
)
from guardian.prompts import (
    GUARDIAN_SYSTEM_PROMPT,
    UIRA_MASTER_SYSTEM_PROMPT_V1,
    UNIVERSAL_INTELLIGENCE_MASTER_PROMPT,
)


class TestKnowledgeTaxonomy:
    """Tests the 25 domains and 6 ontological layers."""

    def test_domain_count_and_uniqueness(self):
        domains = get_all_domains()
        assert len(domains) == 25, f"Expected 25 domains, got {len(domains)}"
        codes = [d.code for d in domains]
        assert len(set(codes)) == 25, "All domain codes must be unique"

    def test_six_ontological_layers(self):
        layers = list(KnowledgeLayerEnum)
        assert len(layers) == 6, f"Expected 6 ontological layers, got {len(layers)}"
        
        # Verify layer coverage across domains
        represented_layers = {d.layer for d in get_all_domains()}
        assert represented_layers == set(layers), "All 6 layers must be represented in domains"

    def test_study_dimensions(self):
        assert len(STUDY_DIMENSIONS) == 15
        expected_dims = [
            "Fundamentals", "Concepts", "Principles", "Evidence", "Methods",
            "Mathematics", "Causality", "Applications", "Tools", "History",
            "Limitations", "Ethics", "Connections", "Evaluation", "Updates"
        ]
        assert STUDY_DIMENSIONS == expected_dims

    def test_get_domain_by_code(self):
        d_math = get_domain("math_formal")
        assert d_math is not None
        assert d_math.layer == KnowledgeLayerEnum.FOUNDATIONS
        assert "probability" in d_math.keywords

        d_cs = get_domain("cs_ai")
        assert d_cs is not None
        assert d_cs.layer == KnowledgeLayerEnum.BUILT_AND_DIGITAL
        assert "algorithm" in d_cs.keywords

        assert get_domain("nonexistent_domain") is None


class TestDomainClassifier:
    """Tests keyword and semantic domain classification."""

    def test_math_classification(self):
        query = "Calculate the matrix eigenvalues and probability distribution"
        results = classify_domain_context(query)
        assert len(results) >= 1
        assert any(d.code == "math_formal" for d in results)

    def test_biology_classification(self):
        query = "Analyze cellular genetics, DNA replication, and ecosystem biodiversity"
        results = classify_domain_context(query)
        assert any(d.code in ("biology_life", "earth_environmental") for d in results)

    def test_economics_classification(self):
        query = "Evaluate monetary policy, capital investment, and inflation in financial markets"
        results = classify_domain_context(query)
        assert any(d.code == "economics_finance" for d in results)

    def test_cybersecurity_and_ai_classification(self):
        query = "Develop a Python neural network algorithm with encryption and security auditing"
        results = classify_domain_context(query)
        assert any(d.code == "cs_ai" for d in results)

    def test_fallback_classification(self):
        query = "xyzzy foobar blort"
        results = classify_domain_context(query)
        assert len(results) >= 1
        assert results[0].code == "cs_ai"


class TestUniversalIntelligencePrompts:
    """Verifies that the system prompts embed the blueprint's principles."""

    def test_system_prompt_principles(self):
        prompt = GUARDIAN_SYSTEM_PROMPT
        assert "UNDERSTAND BEFORE SOLVING" in prompt
        assert "EVIDENCE BEFORE ASSUMPTIONS" in prompt
        assert "REASON SYSTEMATICALLY" in prompt
        assert "7-PHASE INTELLIGENCE CYCLE" in prompt
        assert "LEAST PRIVILEGE" in prompt
        assert "USER SOVEREIGNTY" in prompt

    def test_universal_master_prompt_structure(self):
        prompt = UNIVERSAL_INTELLIGENCE_MASTER_PROMPT
        assert "Perceive -> Understand -> Reason -> Plan -> Act -> Verify -> Improve" in prompt
        assert "Multidisciplinary synthesis" in prompt
        assert "Never manufacture citations or results" in prompt

    def test_uira_master_system_prompt_v1_coverage(self):
        prompt = UIRA_MASTER_SYSTEM_PROMPT_V1
        # Check core identity & directive
        assert "Universal Intelligence & Responsible AI (UIRA)" in prompt
        assert "1. IDENTITY AND MISSION" in prompt
        assert "2. CORE OPERATING PRINCIPLES" in prompt
        assert "3. KNOWLEDGE AND DISCIPLINARY COVERAGE" in prompt
        assert "4. STANDARD PROBLEM-SOLVING WORKFLOW" in prompt
        assert "5. RESEARCH AND WEB INTELLIGENCE" in prompt
        assert "6. ACADEMIC RESEARCH PROTOCOL" in prompt
        assert "7. LOCAL KNOWLEDGE AND MEMORY" in prompt
        assert "8. EVIDENCE AND CITATION REQUIREMENTS" in prompt
        assert "9. RESPONSIBLE AI AND SAFETY" in prompt
        assert "10. TOOL USE AND APPLICATION INTEGRATION" in prompt
        assert "11. ANSWER QUALITY STANDARD" in prompt
        assert "12. CODE AND ENGINEERING STANDARD" in prompt
        assert "13. LEARNING, FEEDBACK, AND IMPROVEMENT" in prompt
        assert "14. UNCERTAINTY AND CONFLICT HANDLING" in prompt
        assert "15. OPERATIONAL PRIORITIES" in prompt
        assert "16. FINAL DIRECTIVE" in prompt
        assert "The goal is not to appear universally intelligent. The goal is to be consistently useful" in prompt
