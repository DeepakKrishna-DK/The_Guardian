"""
Guardian Guardrails -- Input & Output Scanners
===============================================
InputScanner: scans user input BEFORE the model call.
OutputScanner: scans model output AFTER the model call.

Both produce a ScanResult:
  - passed: bool              (False = block/warn)
  - violations: list[Violation]
  - sanitised_text: str       (text with secrets/PII redacted)
  - risk_score: float         (0.0 = clean, 1.0 = critical)

Integration with GuardianCore.process():
  1. InputScanner.scan(user_text)  → if not passed: raise GuardrailBlocked
  2. ... model call ...
  3. OutputScanner.scan(model_reply) → log violations, redact if configured

Design:
  - Fast path: all regex, no model calls.
  - Optional slow path: llm-guard (MIT) loaded lazily if installed.
  - Audit: every violation is logged via security.ThreatStore.
  - Config: thresholds and modes read from GuardrailsConfig.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from guardian.guardrails.patterns import (
    ALL_GROUPS,
    SECRET_LEAK,
    PatternGroup,
)
from guardian.logging.logger import get_logger

log = get_logger(__name__)

_REDACT_TOKEN = "[REDACTED]"


@dataclass
class Violation:
    """A single detected threat in a piece of text."""
    category:    str    # PatternGroup.name
    severity:    str    # critical | high | medium | low
    description: str
    match:       str    # the matched substring (truncated to 80 chars)
    pattern:     str    # the regex pattern that matched

    @property
    def is_blocking(self) -> bool:
        return self.severity in ("critical", "high")


@dataclass
class ScanResult:
    """Result of scanning a single piece of text."""
    passed:          bool
    text:            str                       # original text
    sanitised_text:  str                       # text with secrets redacted
    violations:      list[Violation] = field(default_factory=list)
    risk_score:      float = 0.0              # 0.0 = clean, 1.0 = critical

    @property
    def blocked(self) -> bool:
        return not self.passed

    @property
    def summary(self) -> str:
        if self.passed:
            return "PASS"
        cats = ", ".join({v.category for v in self.violations})
        return f"BLOCK [{cats}]  risk={self.risk_score:.2f}"


def _severity_score(sev: str) -> float:
    return {"critical": 1.0, "high": 0.75, "medium": 0.4, "low": 0.1}.get(sev, 0.0)


def _scan_groups(
    text: str,
    groups: tuple[PatternGroup, ...],
    block_severities: set[str],
) -> tuple[list[Violation], str, float]:
    """
    Core scan loop: run each PatternGroup against text.
    Returns (violations, sanitised_text, risk_score).
    """
    violations: list[Violation] = []
    sanitised  = text
    max_score  = 0.0

    for group in groups:
        for pattern in group.patterns:
            for m in pattern.finditer(text):
                matched = m.group(0)[:80]
                v = Violation(
                    category=group.name,
                    severity=group.severity,
                    description=group.description,
                    match=matched,
                    pattern=pattern.pattern[:120],
                )
                violations.append(v)
                score = _severity_score(group.severity)
                if score > max_score:
                    max_score = score
                # Redact secrets and PII from output
                if group.name in ("SECRET_LEAK", "PII"):
                    sanitised = sanitised.replace(m.group(0), _REDACT_TOKEN)
                break  # one match per pattern per group is enough to flag

    return violations, sanitised, max_score


class InputScanner:
    """
    Scans user input BEFORE it reaches the model.

    Blocking severities (configurable):
      - "critical" and "high" block by default.
      - "medium" and "low" log but allow (can be upgraded in config).

    Usage:
        scanner = InputScanner()
        result = scanner.scan(user_input)
        if result.blocked:
            raise GuardrailBlocked(result.summary)
    """

    # Groups applied to INPUT (not output)
    _INPUT_GROUPS = ALL_GROUPS

    def __init__(
        self,
        block_severities: set[str] | None = None,
        audit: bool = True,
    ) -> None:
        self._block_sev = block_severities or {"critical", "high"}
        self._audit     = audit

    def scan(self, text: str) -> ScanResult:
        if not text or not text.strip():
            return ScanResult(passed=True, text=text, sanitised_text=text)

        violations, sanitised, score = _scan_groups(
            text, self._INPUT_GROUPS, self._block_sev
        )
        passed = not any(v.severity in self._block_sev for v in violations)
        result = ScanResult(
            passed=passed,
            text=text,
            sanitised_text=sanitised,
            violations=violations,
            risk_score=score,
        )

        if violations:
            cats = {v.category for v in violations}
            if passed:
                log.warning(f"InputScanner WARN [{', '.join(cats)}] score={score:.2f}")
            else:
                log.warning(f"InputScanner BLOCK [{', '.join(cats)}] score={score:.2f}")
            if self._audit:
                self._audit_violations(violations, text, direction="input")

        return result

    def _audit_violations(
        self, violations: list[Violation], text: str, direction: str
    ) -> None:
        try:
            from guardian.security import get_security_guardian
            from guardian.security.threat import Category, Severity
            sg = get_security_guardian()
            for v in violations:
                try:
                    cat = Category(v.category.lower())
                except ValueError:
                    cat = Category.DATA_PRIVACY
                try:
                    sev = Severity(v.severity)
                except ValueError:
                    sev = Severity.MEDIUM
                sg.store.record(
                    severity=sev,
                    category=cat,
                    title=f"Guardrail [{direction}]: {v.category}",
                    detail=f"match={v.match!r}",
                    recommendation="Review and investigate this input.",
                )
        except Exception as exc:
            log.debug(f"Audit write skipped: {exc}")


class OutputScanner:
    """
    Scans model output AFTER the model call.

    Primarily prevents secret/PII leakage in responses.
    Does NOT block output by default (only redacts and logs) — blocking
    output would confuse users; instead we alert and redact.

    Usage:
        scanner = OutputScanner()
        result = scanner.scan(model_reply)
        safe_reply = result.sanitised_text
    """

    # For output we only check leakage categories, not injection (model output
    # can legitimately discuss injection for educational purposes)
    _OUTPUT_GROUPS = (SECRET_LEAK,)   # PII optionally added via config

    def __init__(
        self,
        block_on_secret: bool = True,
        redact_pii: bool = True,
        audit: bool = True,
    ) -> None:
        self._block_secret = block_on_secret
        self._redact_pii   = redact_pii
        self._audit        = audit

        from guardian.guardrails.patterns import PII
        self._groups = (SECRET_LEAK,) + ((PII,) if redact_pii else ())

    def scan(self, text: str) -> ScanResult:
        if not text or not text.strip():
            return ScanResult(passed=True, text=text, sanitised_text=text)

        block_sev = {"critical"} if self._block_secret else set()
        violations, sanitised, score = _scan_groups(
            text, self._groups, block_sev
        )
        passed = not any(v.severity in block_sev for v in violations)
        result = ScanResult(
            passed=passed,
            text=text,
            sanitised_text=sanitised,
            violations=violations,
            risk_score=score,
        )

        if violations:
            cats = {v.category for v in violations}
            log.warning(
                f"OutputScanner {'BLOCK' if result.blocked else 'REDACT'} "
                f"[{', '.join(cats)}] score={score:.2f}"
            )
            if self._audit:
                self._audit_output(violations)

        return result

    def _audit_output(self, violations: list[Violation]) -> None:
        try:
            from guardian.security import get_security_guardian
            from guardian.security.threat import Category, Severity
            sg = get_security_guardian()
            for v in violations:
                sg.store.record(
                    severity=Severity.CRITICAL if v.severity == "critical" else Severity.HIGH,
                    category=Category.DATA_PRIVACY,
                    title=f"Guardrail [output]: {v.category}",
                    detail=f"match={v.match!r}",
                    recommendation="A secret or PII was detected in model output. Investigate.",
                )
        except Exception as exc:
            log.debug(f"Audit write skipped: {exc}")


class GuardrailBlocked(Exception):
    """Raised when InputScanner blocks a request."""
    def __init__(self, result: ScanResult) -> None:
        self.result = result
        super().__init__(result.summary)
