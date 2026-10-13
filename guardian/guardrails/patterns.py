"""
Guardian Guardrails -- Threat Detection Patterns
=================================================
All patterns are compiled at import time (fast, no network, no model).
Apache-2.0.  Pattern taxonomy: OWASP LLM Top 10, Greshake et al. 2023.
"""

from __future__ import annotations

import re
from typing import NamedTuple

_F = re.IGNORECASE | re.DOTALL

class PatternGroup(NamedTuple):
    name: str
    patterns: tuple
    severity: str        # low | medium | high | critical
    description: str

PROMPT_INJECTION = PatternGroup(
    name='PROMPT_INJECTION',
    severity='high',
    description='Attempt to override system prompt or hijack model behaviour',
    patterns=tuple(re.compile(p, _F) for p in [
        r'ignore\s+(all\s+)?(previous|above|prior|earlier)\s+(instructions?|prompts?|context|rules?)',
        r'disregard\s+(all\s+)?(previous|above|prior)\s+(instructions?|rules?)',
        r'forget\s+(everything|all)\s+(you|i|we)\s+(told|said|gave|provided)',
        r'new\s+instructions?\s*:',
        r'your\s+(new\s+)?(instructions?|rules?|role|task)\s+(is|are|from\s+now)',
        r'from\s+now\s+on\s+(you|ignore|act|pretend)',
        r'you\s+are\s+now\s+(an?|the)\s+\w+\s+(that|who|with)\s+(no|without)\s+(restrictions?|limits?|filters?)',
        r'act\s+as\s+(if\s+you\s+are\s+)?(dan|jailbreak|evil|unrestricted|unfiltered)',
        r'act\s+as\s+(an?\s+)?\w+(\s+\w+)?\s+(with\s+)?(no|without)\s+(restrictions?|limits?|filters?|ethics?)',
        r'(role[\s\-]?play|roleplay)\s+as\s+(an?\s+)?(evil|unethical|unrestricted|dangerous)',
        r'you\s+are\s+(now\s+)?(an?\s+)?\w+\s+(with\s+)?(no|without)\s+(restrictions?|limits?|filters?)',
        r'pretend\s+(you\s+are|to\s+be)\s+.{0,30}(no\s+(rules?|restrictions?|ethics?|morals?))',
        r'switch\s+to\s+(developer|god|root|admin|jailbreak)\s+mode',
        r'enable\s+(developer|jailbreak|unrestricted|god)\s+mode',
        r'\bDAN\b',
        r'(print|show|reveal|repeat|output|display|tell\s+me)\s+(your|the)\s+(system\s+)?(prompt|instructions?|context|rules?)',
        r'what\s+(is|are|were)\s+your\s+(original\s+)?(instructions?|system\s+prompt|rules?)',
        r'ignore\s+your\s+(guidelines?|training|instructions?)',
        r'<\|im_start\|>',
        r'<\|system\|>',
        r'###\s*system\s*:',
        r'IGNORE\s+INSTRUCTIONS',
        r'STOP\s+FOLLOWING',
        r'\[\[SYSTEM\]\]',
        r'act\s+as\s+(an?\s+)?\w+(\s+\w+)?\s+(with\s+)?(no|without)\s+(restrictions?|limits?|filters?)',
        r'you\s+are\s+(now\s+)?(an?\s+)?\w+\s+(that|who)\s+(has\s+)?(no|without)\s+(restrictions?|limits?|ethics?)',
        r'(roleplay|role-play)\s+as\s+(an?\s+)?(evil|unethical|unrestricted)',
    ]),
)

PII = PatternGroup(
    name='PII',
    severity='medium',
    description='Personally Identifiable Information detected',
    patterns=tuple(re.compile(p, re.IGNORECASE) for p in [
        r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b',
        r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        r'\b\+\d{1,3}[-.\s]?\d{6,14}\b',
        r'\b(?:4\d{12}(?:\d{3})?|5[1-5]\d{14}|3[47]\d{13}|6011\d{12})\b',
        r'\b\d{3}[-\s]\d{2}[-\s]\d{4}\b',
    ]),
)

SECRET_LEAK = PatternGroup(
    name='SECRET_LEAK',
    severity='critical',
    description='API key, token, or credential detected in text',
    patterns=tuple(re.compile(p, re.IGNORECASE) for p in [
        r'(?:api[_\-]?key|secret[_\-]?key?|token|password|passwd|auth[_\-]?token)\s*[=:]\s*[' + "'" + r'"]?[A-Za-z0-9+/=_\-]{20,}',
        r'\bsk-[A-Za-z0-9]{32,}\b',
        r'\bsk-ant-[A-Za-z0-9\-_]{32,}\b',
        r'\bAIza[A-Za-z0-9\-_]{35}\b',
        r'\bgsk_[A-Za-z0-9]{40,}\b',
        r'\bAKIA[A-Z0-9]{16}\b',
        r'\bghp_[A-Za-z0-9]{36}\b',
        r'\beyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+',
        r'-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+|PGP\s+)?PRIVATE\s+KEY',
        r'\bBearer\s+[A-Za-z0-9\-_.]{20,}',
    ]),
)

SENSITIVE_REQUEST = PatternGroup(
    name='SENSITIVE_REQUEST',
    severity='high',
    description='Request targeting sensitive system files or environment secrets',
    patterns=tuple(re.compile(p, _F) for p in [
        r'/etc/(passwd|shadow|sudoers|hosts|ssh/|ssl/)',
        r'\.ssh/(id_rsa|id_ed25519|authorized_keys|known_hosts)',
        r'\.aws/(credentials|config)',
        r'(?<!\w)\.env\b',
        r'\bos\.environ\b',
        r'\bprocess\.env\b',
        r'\bgetenv\s*\(',
        r'print\s+(all\s+)?(environment\s+variables?|env\s+vars?)',
        r'list\s+all\s+api\s+keys',
        r'HKEY_(?:LOCAL_MACHINE|CURRENT_USER)\\',
    ]),
)

TOXIC = PatternGroup(
    name='TOXIC',
    severity='medium',
    description='Potentially toxic or harmful content',
    patterns=tuple(re.compile(p, _F) for p in [
        r'\b(kill|murder|bomb|detonate)\s+(yourself|them|everyone|the\s+\w+)\b',
        r'how\s+to\s+(make|build|create|synthesize)\s+(a\s+)?(bomb|explosive|weapon|poison|malware|ransomware|virus)',
    ]),
)

ALL_GROUPS = (PROMPT_INJECTION, PII, SECRET_LEAK, SENSITIVE_REQUEST, TOXIC)
