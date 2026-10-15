"""
Guardian Defensive Security Advisory Engine
============================================
Implements Section 8 (Firewall and Network Control) and
Section 17 (Standard Response Format for Security Findings)
of the Guardian Master System Prompt v1.0.

Defaults strictly to ADVISORY and READ-ONLY mode.
Requires human authorization before any consequential configuration actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleAction(str, Enum):
    DROP = "DROP"
    REJECT = "REJECT"
    RATE_LIMIT = "RATE_LIMIT"
    ISOLATE = "ISOLATE"
    LOG_ONLY = "LOG_ONLY"


@dataclass
class DefensiveFirewallRecommendation:
    """
    Firewall advisory rule containing all 8 fields required by Section 8.
    """
    observed_evidence: str
    source_and_destination_scope: str
    protocol_and_ports: str
    intended_security_outcome: str
    expected_operational_impact: str
    potential_false_positives: str
    rollback_plan: str
    verification_procedure: str
    action: RuleAction = RuleAction.DROP
    requires_human_confirmation: bool = True
    mode: str = "ADVISORY_READ_ONLY"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "action": self.action.value,
            "requires_human_confirmation": self.requires_human_confirmation,
            "observed_evidence": self.observed_evidence,
            "source_and_destination_scope": self.source_and_destination_scope,
            "protocol_and_ports": self.protocol_and_ports,
            "intended_security_outcome": self.intended_security_outcome,
            "expected_operational_impact": self.expected_operational_impact,
            "potential_false_positives": self.potential_false_positives,
            "rollback_plan": self.rollback_plan,
            "verification_procedure": self.verification_procedure,
        }

    def format_markdown(self) -> str:
        return f"""### 🛡️ Defensive Firewall Rule Recommendation (ADVISORY — READ ONLY)
> [!IMPORTANT]
> **Human Authorization Required**: Direct modification of firewall rules is restricted. This proposal requires explicit administrative confirmation before application.

- **Observed Evidence**: {self.observed_evidence}
- **Source & Destination Scope**: `{self.source_and_destination_scope}`
- **Protocol & Ports**: `{self.protocol_and_ports}`
- **Intended Security Outcome**: {self.intended_security_outcome}
- **Expected Operational Impact**: {self.expected_operational_impact}
- **Potential False Positives**: {self.potential_false_positives}
- **Rollback Plan**: `{self.rollback_plan}`
- **Verification Procedure**: {self.verification_procedure}
"""


@dataclass
class SecurityFindingReport:
    """
    Security Finding formatted strictly according to Section 17.
    """
    severity: SeverityLevel
    confidence: float  # 0.0 to 1.0
    affected_asset_and_scope: str
    evidence: str
    potential_impact: str
    recommended_remediation: str
    verification_steps: str
    rollback_considerations: str
    requires_human_decision: bool = True
    cve_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "confidence": self.confidence,
            "affected_asset_and_scope": self.affected_asset_and_scope,
            "evidence": self.evidence,
            "potential_impact": self.potential_impact,
            "recommended_remediation": self.recommended_remediation,
            "verification_steps": self.verification_steps,
            "rollback_considerations": self.rollback_considerations,
            "requires_human_decision": self.requires_human_decision,
            "cve_id": self.cve_id,
        }

    def format_markdown(self) -> str:
        return f"""### 🚨 Security Finding: {self.affected_asset_and_scope}
- **Severity & Confidence**: **{self.severity.value.upper()}** (Confidence: {self.confidence:.0%})
- **Affected Asset & Scope**: `{self.affected_asset_and_scope}`
- **Evidence**: {self.evidence}
- **Potential Impact**: {self.potential_impact}
- **Recommended Remediation**: {self.recommended_remediation}
- **Verification Steps**: {self.verification_steps}
- **Rollback or Recovery Considerations**: {self.rollback_considerations}
- **Human Decision Required**: {'⚠️ YES — Consequential Action' if self.requires_human_decision else 'No (Telemetry Only)'}
"""


def generate_firewall_advisory(
    evidence: str,
    src_dest: str,
    ports: str,
    outcome: str,
    impact: str,
    false_positives: str,
    rollback: str,
    verification: str,
    action: RuleAction = RuleAction.DROP,
) -> DefensiveFirewallRecommendation:
    """Construct an advisory recommendation complying with Section 8."""
    return DefensiveFirewallRecommendation(
        observed_evidence=evidence,
        source_and_destination_scope=src_dest,
        protocol_and_ports=ports,
        intended_security_outcome=outcome,
        expected_operational_impact=impact,
        potential_false_positives=false_positives,
        rollback_plan=rollback,
        verification_procedure=verification,
        action=action,
        requires_human_confirmation=True,
    )
