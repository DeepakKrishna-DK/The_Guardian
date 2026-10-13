import re
from dataclasses import dataclass
from typing import List

@dataclass
class FirewallResult:
    blocked: bool
    threats: List[str]
    risk_score: float
    redacted_text: str

class AIFirewall:
    JAILBREAK_PHRASES = [
        "ignore previous instructions", "you are now", "act as", "dan", "developer mode",
        "pretend you have no restrictions", "disregard your", "reveal your system prompt", "bypass safety"
    ]
    
    def inspect(self, text: str, source: str = 'user') -> FirewallResult:
        if not text:
            return FirewallResult(blocked=False, threats=[], risk_score=0.0, redacted_text="")
            
        threats = []
        lower_text = text.lower()
        
        for phrase in self.JAILBREAK_PHRASES:
            if phrase in lower_text:
                threats.append(f"jailbreak_phrase_detected: {phrase}")
                
        if re.search(r'([A-Za-z0-9+/]{40,})', text):
            threats.append("suspicious_base64_blob")
        if re.search(r'(?:\\u[0-9a-fA-F]{4}){5,}', text):
            threats.append("suspicious_unicode_escapes")
            
        if len(text) > 10000:
            threats.append("excessive_length")
            
        risk_score = min(1.0, len(threats) * 0.3)
        blocked = risk_score >= 0.8
        
        redacted_text = text
        if source != 'user' and not blocked:
            redacted_text = f"[UNTRUSTED: {source}]\n{text}\n[/UNTRUSTED]"
            
        return FirewallResult(blocked=blocked, threats=threats, risk_score=risk_score, redacted_text=redacted_text)

_firewall = AIFirewall()
def get_firewall():
    return _firewall
