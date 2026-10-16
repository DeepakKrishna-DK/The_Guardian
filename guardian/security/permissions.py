"""
Guardian Permission & Operational Safety Gateway
=================================================
Implementation of Layer 4 (Permission and Security Layer) per Universal Digital Intelligence
Architecture (Version 2.0).

Features:
  1. Three Operational Permission Levels (Section 9):
     - LEVEL 1 — READ: Search, retrieve, inspect, summarize, analyze permitted resources.
     - LEVEL 2 — PREPARE: Draft files, stage code changes, prepare messages, recommend security rules,
                          construct proposed actions without committing.
     - LEVEL 3 — EXECUTE: Commit changes only when permissions, configured policy, and confirmations are met.
  2. Strict Confirmation Gates:
     - Enforces human authorization before high-impact operations (firewall rules, file deletes, shell execution).
     - Controlled by GUARDIAN_REQUIRE_APPROVAL (defaults to True).
  3. Structured JSONL Audit Logging (GUARDIAN_AUDIT_LOG=data/audit/guardian.jsonl):
     - Captures every action, level transition, tool invocation, model call, and security event.
  4. Emergency Stop & Kill Switch integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from guardian.logging.logger import get_logger
from guardian.security.kill_switch import get_kill_switch

log = get_logger(__name__)


class PermissionLevel(str, Enum):
    """The 3 Operational Permission Levels defined in Section 9."""
    LEVEL_1_READ = "LEVEL 1 — READ"
    LEVEL_2_PREPARE = "LEVEL 2 — PREPARE"
    LEVEL_3_EXECUTE = "LEVEL 3 — EXECUTE"


# Actions that strictly require Level 3 and explicit confirmation
CONSEQUENTIAL_ACTIONS = {
    "firewall_change",
    "access_control_change",
    "file_delete",
    "shell_execute",
    "infrastructure_alter",
    "publish_content",
    "send_communication",
    "spend_money",
    "credential_modify",
}


@dataclass
class ActionProposal:
    """Action prepared under Level 2 awaiting confirmation for Level 3 execution."""
    action_id: str
    action_type: str
    description: str
    level_required: PermissionLevel
    requires_approval: bool
    status: str = "pending"  # "pending", "approved", "rejected", "executed"
    target: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "description": self.description,
            "level_required": self.level_required.value,
            "requires_approval": self.requires_approval,
            "status": self.status,
            "target": self.target,
            "payload": self.payload,
            "created_at": self.created_at,
        }


class JsonlAuditLogger:
    """Appends audit events to data/audit/guardian.jsonl in JSON Lines format."""

    def __init__(self, log_path: Optional[str] = None) -> None:
        default_path = os.environ.get("GUARDIAN_AUDIT_LOG", "data/audit/guardian.jsonl")
        self.log_path = Path(log_path or default_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record_event(
        self,
        event_type: str,
        actor: str = "guardian_orchestrator",
        level: Optional[PermissionLevel] = None,
        action: str = "",
        target: str = "",
        status: str = "completed",
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an auditable operation event."""
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "epoch": time.time(),
            "event_type": event_type,
            "actor": actor,
            "permission_level": level.value if level else None,
            "action": action,
            "target": target,
            "status": status,
            "details": details or {},
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            log.warning(f"Failed to append to JSONL audit log: {exc}")

        return record

    def read_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Read the most recent audit records."""
        if not self.log_path.exists():
            return []
        try:
            lines = self.log_path.read_text(encoding="utf-8").strip().splitlines()
            records = []
            for line in lines[-limit:]:
                if line.strip():
                    records.append(json.loads(line))
            return list(reversed(records))
        except Exception as exc:
            log.warning(f"Failed to read audit log: {exc}")
            return []


class PermissionGateway:
    """
    Evaluates permissions, gates Level 3 actions, and records operations in the audit log.
    """

    def __init__(self) -> None:
        self.require_approval = os.environ.get("GUARDIAN_REQUIRE_APPROVAL", "true").lower() in ("1", "true", "yes")
        self.audit_logger = JsonlAuditLogger()
        self.kill_switch = get_kill_switch()
        self._proposals: Dict[str, ActionProposal] = {}

    def check_kill_switch(self) -> None:
        """Raise PermissionError if emergency stop is triggered."""
        if self.kill_switch.is_active():
            raise PermissionError("Emergency kill switch is ACTIVE. All operations halted per safety policy.")

    def evaluate_action(
        self,
        action_type: str,
        target: str = "",
        description: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> ActionProposal:
        """
        Classify action into Permission Level 1, 2, or 3.
        If Level 3, stages as a pending proposal requiring confirmation.
        """
        self.check_kill_switch()

        is_consequential = action_type in CONSEQUENTIAL_ACTIONS or any(k in action_type for k in ("delete", "modify", "exec", "firewall", "kill"))
        level = PermissionLevel.LEVEL_3_EXECUTE if is_consequential else PermissionLevel.LEVEL_1_READ

        needs_approval = is_consequential and self.require_approval
        action_id = f"act_{int(time.time() * 1000)}"

        proposal = ActionProposal(
            action_id=action_id,
            action_type=action_type,
            description=description or f"Action {action_type} on {target}",
            level_required=level,
            requires_approval=needs_approval,
            status="pending" if needs_approval else "approved",
            target=target,
            payload=payload or {},
        )

        self._proposals[action_id] = proposal

        # Audit proposal creation
        self.audit_logger.record_event(
            event_type="action_proposed",
            level=level,
            action=action_type,
            target=target,
            status="pending" if needs_approval else "auto_approved",
            details={"action_id": action_id, "requires_approval": needs_approval},
        )

        return proposal

    def approve_proposal(self, action_id: str, approver: str = "human_operator") -> Dict[str, Any]:
        """Human approval gate satisfying Level 3 execution requirements."""
        self.check_kill_switch()
        proposal = self._proposals.get(action_id)
        if not proposal:
            return {"success": False, "error": f"Proposal {action_id} not found."}

        proposal.status = "approved"
        self.audit_logger.record_event(
            event_type="action_approved",
            actor=approver,
            level=proposal.level_required,
            action=proposal.action_type,
            target=proposal.target,
            status="approved",
            details={"action_id": action_id, "approver": approver},
        )
        return {"success": True, "action_id": action_id, "status": "approved"}

    def reject_proposal(self, action_id: str, reason: str = "Rejected by user") -> Dict[str, Any]:
        """Reject a pending proposal."""
        proposal = self._proposals.get(action_id)
        if not proposal:
            return {"success": False, "error": f"Proposal {action_id} not found."}

        proposal.status = "rejected"
        self.audit_logger.record_event(
            event_type="action_rejected",
            level=proposal.level_required,
            action=proposal.action_type,
            target=proposal.target,
            status="rejected",
            details={"action_id": action_id, "reason": reason},
        )
        return {"success": True, "action_id": action_id, "status": "rejected"}

    def execute_proposal(self, action_id: str) -> Dict[str, Any]:
        """Commit an approved action under Level 3."""
        self.check_kill_switch()
        proposal = self._proposals.get(action_id)
        if not proposal:
            return {"success": False, "error": f"Proposal {action_id} not found."}

        if proposal.requires_approval and proposal.status != "approved":
            return {"success": False, "error": "Approval required before committing Level 3 change."}

        proposal.status = "executed"
        self.audit_logger.record_event(
            event_type="action_executed",
            level=PermissionLevel.LEVEL_3_EXECUTE,
            action=proposal.action_type,
            target=proposal.target,
            status="executed",
            details={"action_id": action_id},
        )
        return {"success": True, "action_id": action_id, "status": "executed"}

    def get_security_status(self) -> Dict[str, Any]:
        """Return operational safety posture."""
        return {
            "kill_switch_active": self.kill_switch.is_active(),
            "require_approval": self.require_approval,
            "pending_proposals": [p.to_dict() for p in self._proposals.values() if p.status == "pending"],
            "recent_audit_records": len(self.audit_logger.read_recent_events(50)),
            "permission_levels": [lvl.value for lvl in PermissionLevel],
        }


_permission_gateway_instance: Optional[PermissionGateway] = None


def get_permission_gateway() -> PermissionGateway:
    """Singleton getter for the PermissionGateway."""
    global _permission_gateway_instance
    if _permission_gateway_instance is None:
        _permission_gateway_instance = PermissionGateway()
    return _permission_gateway_instance
