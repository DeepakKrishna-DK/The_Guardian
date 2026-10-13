"""
Guardian Autonomous Canary & Honeypot Token System
===================================================
Provides proactive intrusion detection and secret exfiltration defense:
  1. Deception Artifacts (Honey-files planted in workspace)
  2. Decoy Secret Lures (Fake API keys, AWS credentials, database passwords)
  3. Real-time Leak Inspection (Scans inputs/outputs for canary values)
  4. File Integrity Monitoring (Monitors honey-files for unauthorized access/tampering)
  5. Cryptographic Audit Escalation (Logs security incidents to tamper-evident audit trail)
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class CanaryType(str, Enum):
    HONEY_FILE = "honey_file"
    DECOY_SECRET = "decoy_secret"
    DECOY_CREDENTIAL = "decoy_credential"


@dataclass
class CanaryToken:
    id: str
    name: str
    token_type: str
    value: str
    file_path: Optional[str] = None
    expected_hash: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    triggered: bool = False
    trigger_count: int = 0
    last_triggered_at: Optional[str] = None
    last_trigger_context: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanaryToken:
        return cls(**data)


class CanaryManager:
    """
    Manages generation, storage, integrity checking, and alert triggers for canary tokens.
    """

    def __init__(self, storage_path: Optional[Path] = None, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.canary_dir = self.workspace_root / ".guardian" / "canaries"
        self.canary_dir.mkdir(parents=True, exist_ok=True)

        self.storage_path = storage_path or (self.workspace_root / ".guardian" / "canary_registry.json")
        self._tokens: dict[str, CanaryToken] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for t in data.get("tokens", []):
                    token = CanaryToken.from_dict(t)
                    self._tokens[token.id] = token
            except Exception:
                self._tokens = {}

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "tokens": [t.to_dict() for t in self._tokens.values()],
        }
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def plant_decoy_secret(self, name: str, secret_prefix: str = "sk-guardian-canary-") -> CanaryToken:
        """Plant a high-entropy decoy secret token."""
        token_id = secrets.token_hex(8)
        canary_secret = f"{secret_prefix}{secrets.token_urlsafe(24)}"

        token = CanaryToken(
            id=token_id,
            name=name,
            token_type=CanaryType.DECOY_SECRET.value,
            value=canary_secret,
        )
        self._tokens[token.id] = token
        self._save()
        return token

    def plant_honey_file(
        self,
        name: str,
        relative_path: Optional[str] = None,
        custom_content: Optional[str] = None,
    ) -> CanaryToken:
        """Plant a decoy file on disk with a tracked canary value."""
        token_id = secrets.token_hex(8)
        canary_secret = f"CANARY_{token_id.upper()}_{secrets.token_hex(16)}"

        if relative_path:
            target_path = self.workspace_root / relative_path
        else:
            target_path = self.canary_dir / f"{name}.canary"

        target_path.parent.mkdir(parents=True, exist_ok=True)

        if not custom_content:
            custom_content = (
                f"# CONFIDENTIAL INTERNAL CONFIGURATION\n"
                f"# Generated for system administration\n"
                f"ADMIN_API_TOKEN={canary_secret}\n"
                f"DATABASE_URL=postgres://canary_admin:{secrets.token_urlsafe(12)}@internal-db:5432/main\n"
            )

        target_path.write_bytes(custom_content.encode("utf-8"))
        file_hash = hashlib.sha256(custom_content.encode("utf-8")).hexdigest()

        token = CanaryToken(
            id=token_id,
            name=name,
            token_type=CanaryType.HONEY_FILE.value,
            value=canary_secret,
            file_path=str(target_path),
            expected_hash=file_hash,
        )
        self._tokens[token.id] = token
        self._save()
        return token

    def check_integrity(self) -> list[dict[str, Any]]:
        """Verify all honey-files on disk; detects tampering, deletion, or modification."""
        alerts = []
        for token in self._tokens.values():
            if token.token_type == CanaryType.HONEY_FILE.value and token.file_path:
                p = Path(token.file_path)
                if not p.exists():
                    alert = {
                        "token_id": token.id,
                        "name": token.name,
                        "status": "TAMPERED_DELETED",
                        "reason": f"Honey-file {token.file_path} was deleted or moved",
                    }
                    self._mark_triggered(token, "Honey-file deleted")
                    alerts.append(alert)
                    continue

                try:
                    content = p.read_bytes()
                    current_hash = hashlib.sha256(content).hexdigest()
                    if current_hash != token.expected_hash:
                        alert = {
                            "token_id": token.id,
                            "name": token.name,
                            "status": "TAMPERED_MODIFIED",
                            "reason": f"Honey-file {token.file_path} content hash mismatch",
                        }
                        self._mark_triggered(token, "Honey-file modified")
                        alerts.append(alert)
                except Exception as e:
                    alert = {
                        "token_id": token.id,
                        "name": token.name,
                        "status": "ERROR",
                        "reason": f"Failed reading honey-file: {e}",
                    }
                    alerts.append(alert)

        return alerts

    def inspect_text_leak(self, text: str) -> list[CanaryToken]:
        """Check if any active canary token secret is present in the text."""
        if not text:
            return []

        tripped: list[CanaryToken] = []
        for token in self._tokens.values():
            if token.value and token.value in text:
                self._mark_triggered(token, f"Canary token leaked in text: {token.name}")
                tripped.append(token)

        return tripped

    def _mark_triggered(self, token: CanaryToken, context: str) -> None:
        """Mark token as triggered and escalate alert to AuditLog and ThreatStore."""
        token.triggered = True
        token.trigger_count += 1
        token.last_triggered_at = datetime.now().isoformat()
        token.last_trigger_context = context
        self._save()

        # Audit escalation
        try:
            from guardian.audit import get_audit_log
            audit = get_audit_log()
            audit.append(
                "security.canary_triggered",
                actor="CanarySystem",
                payload={
                    "token_id": token.id,
                    "token_name": token.name,
                    "token_type": token.token_type,
                    "context": context,
                    "trigger_count": token.trigger_count,
                },
            )
        except Exception:
            pass

        # Threat store escalation
        try:
            from guardian.security import get_security_guardian
            from guardian.security.threat import ThreatRecord, Severity, Category
            sg = get_security_guardian()
            threat = ThreatRecord.new(
                severity=Severity.CRITICAL,
                category=Category.GENERAL,
                title=f"Canary Token Tripped: {token.name}",
                description=f"Intrusion detected! Decoy canary token ({token.token_type}) was touched/exfiltrated. Context: {context}",
                evidence=f"token_id={token.id}, context={context}",
            )
            sg.store.add(threat)
        except Exception:
            pass

    def list_tokens(self) -> list[CanaryToken]:
        return list(self._tokens.values())

    def get_token(self, token_id: str) -> Optional[CanaryToken]:
        return self._tokens.get(token_id)

    def remove_token(self, token_id: str) -> bool:
        if token_id in self._tokens:
            token = self._tokens.pop(token_id)
            if token.file_path and Path(token.file_path).exists():
                try:
                    Path(token.file_path).unlink()
                except Exception:
                    pass
            self._save()
            return True
        return False


_CANARY_MGR: Optional[CanaryManager] = None


def get_canary_manager() -> CanaryManager:
    global _CANARY_MGR
    if _CANARY_MGR is None:
        _CANARY_MGR = CanaryManager()
    return _CANARY_MGR
