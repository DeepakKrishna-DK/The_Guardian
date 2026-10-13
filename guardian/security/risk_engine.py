from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class RiskResult:
    risk_score: float
    risk_level: str
    reasons: List[str]
    required_controls: List[str]
    decision: str

class RiskEngine:
    def evaluate(self, text: str, user_context: Dict, tool_name: Optional[str] = None, firewall_result=None, pii_result=None) -> RiskResult:
        score = 0.0
        reasons = []
        
        if firewall_result and firewall_result.threats:
            score += 0.5
            reasons.append("jailbreak_detected")
            
        if pii_result and pii_result.has_pii:
            if "API_KEY" in pii_result.pii_types or "PRIVATE_KEY" in pii_result.pii_types:
                score += 0.4
                reasons.append("secret_detected")
            else:
                score += 0.2
                reasons.append("pii_detected")
                
        if tool_name in ["shell", "file_write", "code_exec"]:
            score += 0.3
            reasons.append("high_risk_tool")
            
        if not user_context.get("is_authenticated", False):
            score += 0.2
            reasons.append("unauthenticated_user")
            
        if score < 0.2:
            level = "low"
            decision = "allow"
        elif score <= 0.5:
            level = "medium"
            decision = "allow"
        elif score <= 0.8:
            level = "high"
            decision = "require_approval"
        else:
            level = "critical"
            decision = "deny"
            
        return RiskResult(
            risk_score=min(1.0, score),
            risk_level=level,
            reasons=reasons,
            required_controls=["audit_log"] if level != "low" else [],
            decision=decision
        )

_risk_engine = RiskEngine()
def get_risk_engine():
    return _risk_engine
