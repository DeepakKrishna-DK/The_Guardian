"""
Guardian Guardrails -- Configurable Rails
==========================================
YAML-driven rule engine for input/output moderation.
Inspired by NeMo-Guardrails Colang patterns, but original
implementation (no Colang dependency, Apache-2.0).

A "rail" is a named rule with a trigger condition and an action.
Rails are evaluated in order; first match wins.

Example guardrails.yaml:
  rails:
    - name: no_system_prompt_leak
      trigger: PROMPT_INJECTION
      action: block
      message: "I cannot follow instructions that try to override my guidelines."

    - name: warn_pii_input
      trigger: PII
      action: warn
      severity_min: medium

    - name: redact_secrets_output
      trigger: SECRET_LEAK
      action: redact
      direction: output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from guardian.logging.logger import get_logger

log = get_logger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "guardrails.yaml"

Action = Literal["block", "warn", "redact", "allow"]
Direction = Literal["input", "output", "both"]


@dataclass
class Rail:
    name: str
    trigger: str                          # PatternGroup.name or "ANY"
    action: Action = "block"
    direction: Direction = "both"
    severity_min: str = "low"            # only apply if violation >= this severity
    message: str = ""                    # override reply message for "block"
    enabled: bool = True

    _SEV_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

    def matches_violation(self, category: str, severity: str) -> bool:
        if not self.enabled:
            return False
        if self.trigger != "ANY" and self.trigger != category:
            return False
        if self._SEV_ORDER.get(severity, 0) < self._SEV_ORDER.get(self.severity_min, 0):
            return False
        return True


@dataclass
class GuardrailsConfig:
    """
    Loaded from guardrails.yaml or built programmatically.
    Provides the default rail set when no file is present.
    """
    rails: list[Rail] = field(default_factory=list)
    input_block_severities: set[str] = field(default_factory=lambda: {"critical", "high"})
    output_block_on_secret: bool = True
    output_redact_pii: bool = True
    audit_violations: bool = True

    @classmethod
    def default(cls) -> GuardrailsConfig:
        return cls(
            rails=[
                Rail(
                    name="block_prompt_injection",
                    trigger="PROMPT_INJECTION",
                    action="block",
                    direction="input",
                    severity_min="high",
                    message=(
                        "I detected an attempt to override my guidelines. "
                        "I cannot follow those instructions."
                    ),
                ),
                Rail(
                    name="block_secret_in_output",
                    trigger="SECRET_LEAK",
                    action="redact",
                    direction="output",
                    severity_min="critical",
                ),
                Rail(
                    name="warn_pii_input",
                    trigger="PII",
                    action="warn",
                    direction="input",
                    severity_min="medium",
                ),
                Rail(
                    name="block_sensitive_request",
                    trigger="SENSITIVE_REQUEST",
                    action="block",
                    direction="input",
                    severity_min="high",
                    message=(
                        "That request involves sensitive system files or "
                        "credentials. I cannot assist with it."
                    ),
                ),
            ],
        )

    @classmethod
    def from_yaml(cls, path: Path | None = None) -> GuardrailsConfig:
        p = path or _DEFAULT_CONFIG_PATH
        if not p.exists():
            log.debug(f"No guardrails.yaml at {p}; using defaults")
            return cls.default()
        try:
            import yaml  # PyYAML (MIT)
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            cfg = cls.default()
            if "rails" in data:
                cfg.rails = [Rail(**r) for r in data["rails"]]
            if "input_block_severities" in data:
                cfg.input_block_severities = set(data["input_block_severities"])
            cfg.audit_violations = data.get("audit_violations", True)
            return cfg
        except Exception as exc:
            log.warning(f"Failed to load {p}: {exc} — using defaults")
            return cls.default()

    def get_block_message(self, category: str, direction: Direction) -> str:
        for rail in self.rails:
            if rail.action == "block" and rail.trigger == category:
                if rail.direction in (direction, "both"):
                    return rail.message
        return "This request was blocked by Guardian's safety filters."
