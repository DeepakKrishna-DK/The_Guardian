"""
Guardian Device Pairing & Registry
==================================
Manages one-time client device registration (e.g. phone/PWA), approval workflows,
and token-based cryptographic authentication.

Security Properties:
- Untrusted by default: Connections require an active approved device token.
- Explicit Hub Operator Approval: A 6-digit pairing code is shown on the hub.
  An operator must approve the request explicitly.
- Audit Trail: Every approval, pairing, and revocation event is committed to
  the append-only SHA-256 cryptographic audit chain.
- Secret Hygiene: Device tokens are never stored in plaintext — only SHA-256
  digests are stored in the persistent database.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

from guardian.logging.logger import get_logger

log = get_logger(__name__)

# Default pairing code time-to-live: 5 minutes (300 seconds)
DEFAULT_PAIRING_TTL = 300.0


@dataclass
class PairedDevice:
    device_id: str
    device_name: str
    token_hash: str
    paired_at: str
    last_seen: Optional[str] = None
    is_revoked: bool = False
    metadata: Optional[str] = None


@dataclass
class PendingPairing:
    request_id: str
    pairing_code: str
    device_name: str
    client_nonce: str
    created_at: float
    expires_at: float
    is_approved: bool = False
    approved_at: Optional[float] = None
    approved_by: Optional[str] = None


class DeviceRegistry:
    """
    Persistent SQLite storage and workflow engine for paired devices.
    """

    def __init__(self, db_path: Optional[Path] = None, audit: Optional[Any] = None):
        if db_path is None:
            # Persistent directory outside source (mounted in Docker)
            base_dir = Path(os.getenv("GUARDIAN_DATA_DIR", ".guardian"))
            base_dir.mkdir(parents=True, exist_ok=True)
            db_path = base_dir / "devices.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit = audit
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paired_devices (
                    device_id TEXT PRIMARY KEY,
                    device_name TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    paired_at TEXT NOT NULL,
                    last_seen TEXT,
                    is_revoked INTEGER DEFAULT 0,
                    metadata TEXT
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_pairings (
                    request_id TEXT PRIMARY KEY,
                    pairing_code TEXT NOT NULL,
                    device_name TEXT NOT NULL,
                    client_nonce TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    is_approved INTEGER DEFAULT 0,
                    approved_at REAL,
                    approved_by TEXT
                );
            """)
            conn.commit()

    def _audit(self, event_type: str, payload: dict, actor: str = "system") -> None:
        try:
            if self.audit is not None:
                self.audit.append(event_type=event_type, actor=actor, payload=payload)
            else:
                from guardian.audit.log import AuditLog
                audit = AuditLog()
                audit.append(event_type=event_type, actor=actor, payload=payload)
        except Exception as e:
            log.warning(f"Failed to record audit event '{event_type}': {e}")

    def initiate_pairing(self, device_name: str, client_nonce: str, ttl_seconds: float = DEFAULT_PAIRING_TTL) -> PendingPairing:
        """
        Initiates a pairing request for a new device.
        Generates a 6-digit numeric pairing code displayed on the hub.
        """
        request_id = f"pair_{secrets.token_hex(8)}"
        pairing_code = f"{secrets.randbelow(900000) + 100000:06d}"
        now = time.time()
        expires_at = now + ttl_seconds

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO pending_pairings (
                    request_id, pairing_code, device_name, client_nonce, created_at, expires_at, is_approved
                ) VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (request_id, pairing_code, device_name, client_nonce, now, expires_at),
            )
            conn.commit()

        log.info(f"Pairing initiated for '{device_name}'. Code: {pairing_code} (Expires in {int(ttl_seconds)}s)")
        return PendingPairing(
            request_id=request_id,
            pairing_code=pairing_code,
            device_name=device_name,
            client_nonce=client_nonce,
            created_at=now,
            expires_at=expires_at,
            is_approved=False,
        )

    def list_pending(self) -> List[PendingPairing]:
        """Returns all unexpired, pending pairing requests."""
        now = time.time()
        results: List[PendingPairing] = []
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM pending_pairings WHERE expires_at > ? ORDER BY created_at DESC",
                (now,),
            ).fetchall()
            for r in rows:
                results.append(PendingPairing(
                    request_id=r["request_id"],
                    pairing_code=r["pairing_code"],
                    device_name=r["device_name"],
                    client_nonce=r["client_nonce"],
                    created_at=r["created_at"],
                    expires_at=r["expires_at"],
                    is_approved=bool(r["is_approved"]),
                    approved_at=r["approved_at"],
                    approved_by=r["approved_by"],
                ))
        return results

    def approve_pairing(self, code_or_request_id: str, operator: str = "hub_operator") -> Optional[PendingPairing]:
        """
        Explicitly approves a pending pairing request.
        Audited to the append-only cryptographic log.
        """
        now = time.time()
        clean_target = code_or_request_id.strip()
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM pending_pairings 
                WHERE (request_id = ? OR pairing_code = ?) AND expires_at > ?
                """,
                (clean_target, clean_target, now),
            ).fetchone()

            if not row:
                return None

            request_id = row["request_id"]
            device_name = row["device_name"]

            conn.execute(
                """
                UPDATE pending_pairings 
                SET is_approved = 1, approved_at = ?, approved_by = ?
                WHERE request_id = ?
                """,
                (now, operator, request_id),
            )
            conn.commit()

        self._audit(
            event_type="device.pairing_approved",
            actor=operator,
            payload={
                "request_id": request_id,
                "device_name": device_name,
                "approved_by": operator,
            },
        )
        log.info(f"Device pairing approved by {operator} for '{device_name}' (ID: {request_id})")

        return PendingPairing(
            request_id=request_id,
            pairing_code=row["pairing_code"],
            device_name=device_name,
            client_nonce=row["client_nonce"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            is_approved=True,
            approved_at=now,
            approved_by=operator,
        )

    def complete_pairing(self, request_id: str, client_nonce: str) -> Optional[Tuple[str, PairedDevice]]:
        """
        Client exchanges approved request_id and matching nonce for a permanent device token.
        Returns (raw_device_token, PairedDevice) or None.
        """
        now = time.time()
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM pending_pairings 
                WHERE request_id = ? AND client_nonce = ? AND is_approved = 1 AND expires_at > ?
                """,
                (request_id, client_nonce, now),
            ).fetchone()

            if not row:
                return None

            device_id = f"dev_{secrets.token_hex(8)}"
            raw_token = f"gdt_{secrets.token_hex(32)}"
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            device_name = row["device_name"]
            paired_at_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

            conn.execute(
                """
                INSERT INTO paired_devices (
                    device_id, device_name, token_hash, paired_at, is_revoked, metadata
                ) VALUES (?, ?, ?, ?, 0, ?)
                """,
                (device_id, device_name, token_hash, paired_at_iso, json.dumps({"approved_by": row["approved_by"]})),
            )
            # Remove completed pending record
            conn.execute("DELETE FROM pending_pairings WHERE request_id = ?", (request_id,))
            conn.commit()

        device = PairedDevice(
            device_id=device_id,
            device_name=device_name,
            token_hash=token_hash,
            paired_at=paired_at_iso,
            is_revoked=False,
        )

        self._audit(
            event_type="device.paired",
            actor="hub_gateway",
            payload={
                "device_id": device_id,
                "device_name": device_name,
                "paired_at": paired_at_iso,
            },
        )
        log.info(f"Device successfully paired: '{device_name}' (ID: {device_id})")
        return raw_token, device

    def validate_token(self, raw_token: str) -> Optional[PairedDevice]:
        """
        Validates an incoming bearer token against stored SHA-256 hashes.
        Updates last_seen on successful validation.
        """
        if not raw_token or not raw_token.startswith("gdt_"):
            return None

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM paired_devices WHERE token_hash = ? AND is_revoked = 0",
                (token_hash,),
            ).fetchone()

            if not row:
                return None

            device_id = row["device_id"]
            conn.execute(
                "UPDATE paired_devices SET last_seen = ? WHERE device_id = ?",
                (now_iso, device_id),
            )
            conn.commit()

            return PairedDevice(
                device_id=device_id,
                device_name=row["device_name"],
                token_hash=row["token_hash"],
                paired_at=row["paired_at"],
                last_seen=now_iso,
                is_revoked=bool(row["is_revoked"]),
                metadata=row["metadata"],
            )

    def revoke_device(self, device_id: str, operator: str = "hub_operator") -> bool:
        """Revokes an existing paired device."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE paired_devices SET is_revoked = 1 WHERE device_id = ? AND is_revoked = 0",
                (device_id,),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return False

        self._audit(
            event_type="device.revoked",
            actor=operator,
            payload={"device_id": device_id, "revoked_by": operator},
        )
        log.warning(f"Device revoked: {device_id} by {operator}")
        return True

    def list_devices(self) -> List[PairedDevice]:
        """Lists all registered paired devices."""
        results: List[PairedDevice] = []
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM paired_devices ORDER BY paired_at DESC").fetchall()
            for r in rows:
                results.append(PairedDevice(
                    device_id=r["device_id"],
                    device_name=r["device_name"],
                    token_hash=r["token_hash"],
                    paired_at=r["paired_at"],
                    last_seen=r["last_seen"],
                    is_revoked=bool(r["is_revoked"]),
                    metadata=r["metadata"],
                ))
        return results


# Global singleton instance
_registry_instance: Optional[DeviceRegistry] = None

def get_device_registry() -> DeviceRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = DeviceRegistry()
    return _registry_instance
