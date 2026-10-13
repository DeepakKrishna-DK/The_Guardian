from dataclasses import dataclass
from typing import List, Optional, Dict
from .pii_detector import get_pii_detector

@dataclass
class OutputResult:
    allowed: bool
    action: str
    sanitized_output: str
    reasons: List[str]

class OutputFirewall:
    def __init__(self):
        self.pii_detector = get_pii_detector()
        self.unsafe_keywords = ["__proto__", "eval(", "os.system"]
        
    def inspect(self, output: str, security_ctx: Optional[Dict] = None) -> OutputResult:
        if not output:
            return OutputResult(allowed=True, action="ALLOW", sanitized_output="", reasons=[])
            
        reasons = []
        action = "ALLOW"
        
        pii_res = self.pii_detector.detect(output)
        sanitized = pii_res.redacted_text
        
        if pii_res.has_pii and ("API_KEY" in pii_res.pii_types or "PRIVATE_KEY" in pii_res.pii_types):
            reasons.append("secret_detected")
            action = "REDACT"
            
        for kw in self.unsafe_keywords:
            if kw in output.lower():
                reasons.append(f"unsafe_keyword: {kw}")
                action = "BLOCK"
                sanitized = ""
                break
                
        if action == "BLOCK":
            return OutputResult(allowed=False, action="BLOCK", sanitized_output="", reasons=reasons)
            
        return OutputResult(allowed=True, action=action, sanitized_output=sanitized, reasons=reasons)

_output_firewall = OutputFirewall()
def get_output_firewall():
    return _output_firewall
