"""
Guardian Audit Redaction — guardian/audit/redact.py
====================================================
Scrubs secret patterns from audit payloads before they are stored or hashed.
Reuses the same SECRET_LEAK patterns as the guardrails scanner.

Apache-2.0.
"""

from __future__ import annotations

import re
from typing import Any

_REDACT_TOKEN = "[REDACTED]"


def _load_secret_patterns() -> list[re.Pattern[str]]:
    """Load compiled SECRET_LEAK regex patterns from guardrails."""
    try:
        import guardian.guardrails.patterns as p
        # ALL_GROUPS is a tuple of PatternGroup NamedTuples: (name, patterns_tuple, severity)
        for pg in p.ALL_GROUPS:
            if pg[0] == "SECRET_LEAK":
                return list(pg[1])  # pg[1] is a tuple of compiled re.Pattern
    except Exception:
        pass
    return []


def redact_string(text: str, patterns: list[re.Pattern[str]] | None = None) -> str:
    """Replace secret-matching substrings in text with [REDACTED]."""
    if patterns is None:
        patterns = _load_secret_patterns()
    for pat in patterns:
        text = pat.sub(_REDACT_TOKEN, text)
    return text


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively walk a dict and redact string values matching secret patterns.
    The dict is NOT mutated; a new dict is returned.
    It also outright removes or redacts keys corresponding to raw prompts/content
    to enforce Constitution §5.
    """
    patterns = _load_secret_patterns()
    result = _redact_value(payload, patterns)
    assert isinstance(result, dict)
    
    # Constitution §5: never store raw prompt/response
    forbidden_keys = {"content", "prompt", "messages", "response"}
    for k in list(result.keys()):
        if k in forbidden_keys:
            result[k] = "[REDACTED_CONTENT_POLICY]"
            
    return result


def _redact_value(obj: Any, patterns: list[re.Pattern[str]]) -> Any:
    if isinstance(obj, dict):
        return {k: _redact_value(v, patterns) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_value(v, patterns) for v in obj]
    if isinstance(obj, str):
        return redact_string(obj, patterns)
    return obj
