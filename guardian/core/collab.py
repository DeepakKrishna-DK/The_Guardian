"""
Guardian Agent/Human Collaboration Protocol (M3)
================================================
Defines structured escalation rules and sub-agent handoffs.
Constitution compliance:
- §13 Failure Policy (ask for clarification when essential)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from guardian.audit import get_audit_log


class EscalationReason(str, Enum):
    AMBIGUOUS_SCOPE = "ambiguous_scope"
    CONFLICTING_INSTRUCTIONS = "conflicting_instructions"
    POLICY_APPROVAL_REQUIRED = "policy_approval_required"
    UNCLEAR_OUTCOME = "unclear_outcome"


@dataclass
class Escalation:
    reason: EscalationReason
    message: str
    pending_action: str


@dataclass
class CollaborationSummary:
    """Session-level summary of collaboration checkpoints."""
    tasks_done: list[str] = field(default_factory=list)
    escalations: list[Escalation] = field(default_factory=list)
    handoffs: list[dict[str, Any]] = field(default_factory=list)

    def render(self) -> str:
        out = ["=== Guardian Collaboration Checkpoint ==="]
        if self.tasks_done:
            out.append(f"Completed: {len(self.tasks_done)} steps")
        if self.handoffs:
            out.append(f"Handoffs: {len(self.handoffs)}")
        for e in self.escalations:
            out.append(f"[ESCALATION REQUIRED: {e.reason.value}]")
            out.append(f"  {e.message}")
            out.append(f"  Pending: {e.pending_action}")
        return "\n".join(out)


def record_agent_handoff(from_agent: str, to_agent: str, asked: str, found: str, passing_on: str) -> dict[str, Any]:
    """
    Record a structured handoff between sub-agents.
    Recorded in audit log as metadata only (raw content redacted by policy).
    """
    payload = {
        "from": from_agent,
        "to": to_agent,
        "asked": asked,
        "found": found,
        "passing_on": passing_on
    }
    
    get_audit_log().append(
        "agent.handoff",
        actor=from_agent,
        payload=payload
    )
    
    return payload
