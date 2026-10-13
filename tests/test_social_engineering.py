"""
Tests for Guardian Social Engineering Defense (SET-Inspired)
=============================================================
"""

import json
import pytest
from guardian.security.social_engineering import (
    SocialEngineeringDetector,
    RiskTier,
    get_social_engineering_detector,
)
from guardian.tools.social_engineering_tool import SocialEngineeringDefenseTool
from guardian.tools.base import ToolRequest, ToolLevel
from guardian.tools import get_tool_executor
from guardian.core.agents import get_agent_for_tool


def test_benign_text_safe():
    detector = SocialEngineeringDetector()
    report = detector.analyze(
        "Hi team, let's schedule our quarterly planning session next Tuesday at 2 PM. "
        "The project notes are in the shared workspace."
    )
    assert report.risk_tier == RiskTier.SAFE
    assert report.risk_score < 0.20
    assert not report.is_malicious
    assert len(report.indicators) == 0


def test_urgency_and_authority_phishing():
    detector = SocialEngineeringDetector()
    attack_text = (
        "URGENT: This is IT Support. Your account has been suspended due to an unauthorized access attempt. "
        "Immediate action is required within 2 hours or your access will be permanently terminated."
    )
    report = detector.analyze(attack_text)
    assert report.is_malicious
    assert report.risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL)
    assert "URGENCY" in report.psychological_triggers
    assert "AUTHORITY_IMPERSONATION" in report.psychological_triggers
    assert "SET_SPEAR_PHISHING" in report.detected_vectors


def test_credential_harvester_typosquatting():
    detector = SocialEngineeringDetector()
    attack_text = (
        "Please confirm your password to update credentials immediately: "
        "http://login-micros0ft.account-security.net/auth/login"
    )
    report = detector.analyze(attack_text)
    assert report.is_malicious
    assert "SET_CREDENTIAL_HARVESTER" in report.detected_vectors
    assert any(u["is_suspicious"] for u in report.urls_analyzed)
    typo_match = any("micros0ft" in ind.description.lower() for ind in report.indicators)
    assert typo_match


def test_weaponized_attachment():
    detector = SocialEngineeringDetector()
    attack_text = "Attached is the urgent invoice. Please inspect Invoice_Final_2026.pdf.exe immediately."
    report = detector.analyze(attack_text)
    assert "SET_INFECTIOUS_MEDIA" in report.detected_vectors
    attachment_indicator = any(ind.category == "WEAPONIZED_ATTACHMENT" for ind in report.indicators)
    assert attachment_indicator


def test_powershell_payload_cradle():
    detector = SocialEngineeringDetector()
    attack_text = "powershell.exe -w hidden -nop -enc JABzAD0ATgBlAHcALQBPAGIAagBlAGMAdAAgAE4AZQB0AC4AVwBlAGIAQwBsAGkAZQBuAHQA"
    report = detector.analyze(attack_text)
    assert report.risk_tier == RiskTier.CRITICAL
    assert "SET_POWERSHELL_PAYLOAD" in report.detected_vectors


def test_tool_execution():
    tool = SocialEngineeringDefenseTool()
    assert tool.name == "social_engineering_defense"
    assert tool.level == ToolLevel.READ

    result = tool._execute({"text": "URGENT: CEO wire transfer payment required right now."})
    assert result.success
    parsed = json.loads(result.output)
    assert parsed["risk_tier"] in ("HIGH", "CRITICAL")
    assert "SET_SPEAR_PHISHING" in parsed["detected_vectors"]


def test_executor_integration():
    executor = get_tool_executor()
    req = ToolRequest(
        name="social_engineering_defense",
        params={"text": "Routine security check completed with zero findings."},
    )
    result = executor.run(req)
    assert result.success
    # Unwrap [UNTRUSTED TOOL OUTPUT] if wrapped by executor
    raw_output = result.output
    if "[UNTRUSTED TOOL OUTPUT]" in raw_output:
        raw_output = raw_output.replace("[UNTRUSTED TOOL OUTPUT]", "").replace("[/UNTRUSTED TOOL OUTPUT]", "").strip()
    parsed = json.loads(raw_output)
    assert parsed["risk_tier"] == "SAFE"


def test_social_engineering_agent_scoped():
    agent = get_agent_for_tool("social_engineering_defense")
    assert agent is not None
    assert agent.name == "social_engineering"
    assert "social_engineering_defense" in agent.scope.allowed_tools
