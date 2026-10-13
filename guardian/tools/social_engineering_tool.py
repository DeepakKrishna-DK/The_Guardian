"""
Tool: social_engineering_defense
================================
Provides on-demand analysis of suspicious emails, messages, URLs, and scripts
against TrustedSec Social-Engineer Toolkit (SET) vectors.
"""

from __future__ import annotations

import json
import time
from typing import Any

from guardian.security.social_engineering import get_social_engineering_detector
from guardian.tools.base import Tool, ToolLevel, ToolResult


class SocialEngineeringDefenseTool(Tool):
    """
    Guardian tool for analyzing social engineering tactics and phishing lures.
    """

    name = "social_engineering_defense"
    level = ToolLevel.READ
    description = (
        "Analyze text, emails, messages, or URLs for social engineering, "
        "spear-phishing, pretexting, and SET credential harvester tactics."
    )

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        t0 = time.monotonic()
        text = params.get("text", "")
        if not text:
            return ToolResult(
                success=False,
                output="",
                error="Parameter 'text' is required.",
                tool_name=self.name,
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        detector = get_social_engineering_detector()
        report = detector.analyze(text)

        output_data = {
            "risk_tier": report.risk_tier.value,
            "risk_score": report.risk_score,
            "is_malicious": report.is_malicious,
            "detected_vectors": report.detected_vectors,
            "psychological_triggers": report.psychological_triggers,
            "indicators": [
                {
                    "category": ind.category,
                    "vector": ind.vector,
                    "description": ind.description,
                    "severity": ind.severity,
                    "evidence": ind.evidence,
                }
                for ind in report.indicators
            ],
            "urls_analyzed": report.urls_analyzed,
            "recommendations": report.recommendations,
        }

        duration_ms = (time.monotonic() - t0) * 1000
        formatted_output = json.dumps(output_data, indent=2)

        return ToolResult(
            success=True,
            output=formatted_output,
            tool_name=self.name,
            duration_ms=duration_ms,
            metadata={"risk_tier": report.risk_tier.value, "risk_score": report.risk_score},
        )

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The message body, email contents, URL, or script to evaluate for social engineering indicators.",
                }
            },
            "required": ["text"],
        }
