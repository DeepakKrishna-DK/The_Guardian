import re
from dataclasses import dataclass
from typing import List

@dataclass
class PIIResult:
    has_pii: bool
    pii_types: List[str]
    redacted_text: str

class PIIDetector:
    PATTERNS = {
        "EMAIL": r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
        "PHONE": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        "SSN": r'\b\d{3}-\d{2}-\d{4}\b',
        "API_KEY": r'\b(sk-[a-zA-Z0-9]{20,}|AIza[0-9A-Za-z-_]{35}|ghp_[0-9a-zA-Z]{36})\b',
        "PRIVATE_KEY": r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
        "PASSWORD": r'(?i)password\s*[:=]\s*\S+'
    }
    
    def detect(self, text: str) -> PIIResult:
        if not text:
            return PIIResult(has_pii=False, pii_types=[], redacted_text="")
            
        pii_types = []
        redacted = text
        
        for ptype, pattern in self.PATTERNS.items():
            if re.search(pattern, redacted):
                pii_types.append(ptype)
                redacted = re.sub(pattern, f"[REDACTED-{ptype}]", redacted)
                
        return PIIResult(has_pii=bool(pii_types), pii_types=pii_types, redacted_text=redacted)

_pii_detector = PIIDetector()
def get_pii_detector():
    return _pii_detector
