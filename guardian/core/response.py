"""
Guardian Response
=================
Structured output returned by GuardianCore for every user interaction.

Every response records what happened, what model was used, how long it took,
and any error. This makes the system transparent and auditable per Constitution
section 11 (Transparency) and section 7 (Auditability).

Inputs:   Produced by GuardianCore.process()
Outputs:  Consumed by CLI, future APIs, future evaluators
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class GuardianResponse:
    """
    Structured response from the Guardian orchestrator.

    Fields:
        content         The assistant's reply text (empty string on error)
        model_provider  Which backend produced this response (e.g. "groq")
        model_name      The specific model used
        session_turn    Which turn in the session produced this (1-indexed)
        duration_ms     Wall-clock time for the model call in milliseconds
        tokens_used     Total tokens consumed (0 if not reported)
        timestamp       When this response was produced
        error           Error message if the call failed; None on success
        metadata        Pass-through dict for future extensibility
    """

    content: str
    model_provider: str
    model_name: str
    session_turn: int
    duration_ms: float
    tokens_used: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    error: str | None = None
    active_skill: str = "guardian"   # Which skill processed this turn
    metadata: dict[str, Any] = field(default_factory=dict)
    escalations: list[Any] = field(default_factory=list)  # list[Escalation]

    @property
    def success(self) -> bool:
        """True if the response was produced without error."""
        return self.error is None and bool(self.content)

    @property
    def duration_s(self) -> float:
        """Duration in seconds (convenience)."""
        return round(self.duration_ms / 1000, 3)

    def __bool__(self) -> bool:
        return self.success

    def summary(self) -> str:
        """One-line summary for logging."""
        status = "OK" if self.success else f"ERROR: {self.error}"
        return (
            f"[turn={self.session_turn} "
            f"skill={self.active_skill} "
            f"provider={self.model_provider} "
            f"model={self.model_name} "
            f"tokens={self.tokens_used} "
            f"ms={self.duration_ms:.0f} "
            f"status={status}]"
        )
