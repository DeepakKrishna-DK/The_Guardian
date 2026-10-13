"""
Guardian Guardrails -- Public API
===================================
GuardrailsLayer: unified facade wrapping InputScanner + OutputScanner + Rails.

Usage in GuardianCore (chat loop):
    layer = get_guardrails_layer()

    # Before model call:
    result = layer.scan_input(user_text)
    if result.blocked:
        return layer.block_message(result)

    # After model call:
    out = layer.scan_output(model_reply)
    return out.sanitised_text

Usage from CLI:
    guardian guardrails scan "<text>"
    guardian guardrails status
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from guardian.guardrails.patterns import ALL_GROUPS, PatternGroup
from guardian.guardrails.rails import GuardrailsConfig
from guardian.guardrails.scanner import (
    GuardrailBlocked,
    InputScanner,
    OutputScanner,
    ScanResult,
    Violation,
)
from guardian.logging.logger import get_logger

log = get_logger(__name__)


@dataclass
class GuardrailsStatus:
    input_block_severities: set[str]
    output_block_on_secret: bool
    output_redact_pii: bool
    audit_enabled: bool
    rails_count: int
    pattern_groups: list[str]
    pattern_total: int


class GuardrailsLayer:
    """
    Unified guardrails facade.

    Holds InputScanner + OutputScanner configured from GuardrailsConfig.
    Provides block_message() which returns a safe, user-facing reply string
    that does NOT reveal what pattern matched (preventing oracle attacks).
    """

    def __init__(self, config: GuardrailsConfig) -> None:
        self._config  = config
        self._input   = InputScanner(
            block_severities=config.input_block_severities,
            audit=config.audit_violations,
        )
        self._output  = OutputScanner(
            block_on_secret=config.output_block_on_secret,
            redact_pii=config.output_redact_pii,
            audit=config.audit_violations,
        )

    def scan_input(self, text: str) -> ScanResult:
        """Scan user input before sending to model. Raises nothing — caller decides."""
        return self._input.scan(text)

    def scan_output(self, text: str) -> ScanResult:
        """Scan model output; returns sanitised_text with secrets/PII redacted."""
        return self._output.scan(text)

    def block_message(self, result: ScanResult) -> str:
        """
        Return a safe user-facing block message.
        Does NOT leak which pattern matched (oracle resistance).
        Uses rail-specific message if configured, else generic.
        """
        if result.violations:
            cat = result.violations[0].category
            msg = self._config.get_block_message(cat, "input")
            if msg:
                return msg
        return "Your request was blocked by Guardian's safety filters."

    def status(self) -> GuardrailsStatus:
        total = sum(len(g.patterns) for g in ALL_GROUPS)
        return GuardrailsStatus(
            input_block_severities=self._config.input_block_severities,
            output_block_on_secret=self._config.output_block_on_secret,
            output_redact_pii=self._config.output_redact_pii,
            audit_enabled=self._config.audit_violations,
            rails_count=len(self._config.rails),
            pattern_groups=[g.name for g in ALL_GROUPS],
            pattern_total=total,
        )

    def quick_scan(self, text: str) -> dict[str, Any]:
        """
        Scan text as both input and output; return a summary dict.
        Used by CLI and tests.
        """
        in_r  = self.scan_input(text)
        out_r = self.scan_output(text)
        all_v = in_r.violations + [
            v for v in out_r.violations
            if v.category not in {iv.category for iv in in_r.violations}
        ]
        return {
            "passed":     in_r.passed and out_r.passed,
            "risk_score": max(in_r.risk_score, out_r.risk_score),
            "violations": [
                {
                    "category": v.category,
                    "severity": v.severity,
                    "match":    v.match[:40],
                }
                for v in all_v
            ],
            "sanitised": out_r.sanitised_text,
        }


# ── Singleton ──────────────────────────────────────────────────────────────────

_layer: GuardrailsLayer | None = None


def get_guardrails_layer(config_path: Path | None = None) -> GuardrailsLayer:
    """Return the shared GuardrailsLayer singleton."""
    global _layer
    if _layer is None:
        config = GuardrailsConfig.from_yaml(config_path)
        _layer = GuardrailsLayer(config)
        log.info(
            f"GuardrailsLayer ready: "
            f"{len(config.rails)} rails, "
            f"{sum(len(g.patterns) for g in ALL_GROUPS)} patterns"
        )
    return _layer


def reset_guardrails_layer() -> None:
    """Reset singleton (for tests)."""
    global _layer
    _layer = None


def make_test_layer() -> GuardrailsLayer:
    """Factory for tests: default config, no audit writes."""
    config = GuardrailsConfig.default()
    config.audit_violations = False
    return GuardrailsLayer(config)


__all__ = [
    "GuardrailBlocked",
    "GuardrailsConfig",
    "GuardrailsLayer",
    "GuardrailsStatus",
    "InputScanner",
    "OutputScanner",
    "Rail",
    "ScanResult",
    "Violation",
    "get_guardrails_layer",
    "make_test_layer",
    "reset_guardrails_layer",
]
