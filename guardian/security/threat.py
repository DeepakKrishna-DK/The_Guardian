"""
Guardian Threat Records
========================
Data structures for recording detected security findings.

Constitution reference: Section 4 (Security), Section 11 (Transparency)

ThreatRecord:
  - Every finding is assigned a severity (INFO/LOW/MEDIUM/HIGH/CRITICAL)
  - Every finding has a category, description, and recommendation
  - Findings are stored in SQLite for audit history
  - Findings can be acknowledged (suppressed after review)
  - All stored findings are visible to the user at any time

Permissions: Level 0 (observe) for detection
             Level 1 (write) for storing findings to DB
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO     = "info"
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]

    def __lt__(self, other: "Severity") -> bool:
        return self.rank < other.rank

    def display(self) -> str:
        colors = {
            "info": "dim",
            "low": "cyan",
            "medium": "yellow",
            "high": "red",
            "critical": "bold red",
        }
        return f"[{colors.get(self.value, 'white')}]{self.value.upper()}[/{colors.get(self.value, 'white')}]"


class Category(str, Enum):
    SECRET      = "secret"        # Exposed credentials, keys, tokens
    CONFIG      = "config"        # Misconfiguration
    PERMISSION  = "permission"    # File/directory permission issue
    PROCESS     = "process"       # Suspicious process or service
    NETWORK     = "network"       # Open ports, unexpected listeners
    CODE        = "code"          # Code-level finding
    INTEGRITY   = "integrity"     # File hash mismatch, unexpected change
    GENERAL     = "general"       # Catch-all


@dataclass
class ThreatRecord:
    """A single security finding."""
    id: str
    severity: Severity
    category: Category
    title: str
    description: str
    recommendation: str
    source: str                     # Which scanner found this
    timestamp: datetime
    context: dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: str = ""
    technique_id: str = ""          # M2 MITRE ATT&CK technique mapping

    @classmethod
    def new(
        cls,
        severity: Severity,
        category: Category,
        title: str,
        description: str,
        recommendation: str,
        source: str,
        context: dict[str, Any] | None = None,
        technique_id: str = "",
    ) -> "ThreatRecord":
        return cls(
            id=str(uuid.uuid4()),
            severity=severity,
            category=category,
            title=title,
            description=description,
            recommendation=recommendation,
            source=source,
            timestamp=datetime.now(),
            context=context or {},
            technique_id=technique_id,
        )

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ThreatRecord":
        return cls(
            id=row["id"],
            severity=Severity(row["severity"]),
            category=Category(row["category"]),
            title=row["title"],
            description=row["description"],
            recommendation=row["recommendation"],
            source=row["source"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            context=json.loads(row.get("context", "{}")),
            acknowledged=bool(row.get("acknowledged", 0)),
            acknowledged_at=datetime.fromisoformat(row["acknowledged_at"]) if row.get("acknowledged_at") else None,
            acknowledged_by=row.get("acknowledged_by", ""),
            technique_id=row.get("technique_id", ""),
        )

    def summary(self) -> str:
        return f"[{self.severity.value.upper()}] {self.category.value}: {self.title}"

    def is_active(self) -> bool:
        return not self.acknowledged


class ThreatStore:
    """
    SQLite-backed persistent store for ThreatRecords.
    Uses :memory: for tests. Real path: memory/threats.db
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS threats (
        id              TEXT PRIMARY KEY,
        severity        TEXT NOT NULL,
        category        TEXT NOT NULL,
        title           TEXT NOT NULL,
        description     TEXT NOT NULL,
        recommendation  TEXT NOT NULL,
        source          TEXT NOT NULL,
        timestamp       TEXT NOT NULL,
        context         TEXT DEFAULT '{}',
        acknowledged    INTEGER DEFAULT 0,
        acknowledged_at TEXT,
        acknowledged_by TEXT DEFAULT '',
        technique_id    TEXT DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_threats_severity ON threats(severity);
    CREATE INDEX IF NOT EXISTS idx_threats_ts       ON threats(timestamp);
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        import sqlite3
        self._db_path = db_path
        if db_path != ":memory:":
            from pathlib import Path
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def save(self, record: ThreatRecord) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO threats
               (id,severity,category,title,description,recommendation,
                source,timestamp,context,acknowledged,acknowledged_at,acknowledged_by,technique_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (record.id, record.severity.value, record.category.value,
             record.title, record.description, record.recommendation,
             record.source, record.timestamp.isoformat(),
             json.dumps(record.context), int(record.acknowledged),
             record.acknowledged_at.isoformat() if record.acknowledged_at else None,
             record.acknowledged_by, record.technique_id),
        )
        self._conn.commit()

    def save_many(self, records: list[ThreatRecord]) -> None:
        for r in records:
            self.save(r)

    def list_active(self, min_severity: Severity = Severity.INFO) -> list[ThreatRecord]:
        rows = self._conn.execute(
            "SELECT * FROM threats WHERE acknowledged=0 ORDER BY timestamp DESC"
        ).fetchall()
        results = [ThreatRecord.from_row(dict(r)) for r in rows]
        return [r for r in results if r.severity.rank >= min_severity.rank]

    def list_all(self) -> list[ThreatRecord]:
        rows = self._conn.execute(
            "SELECT * FROM threats ORDER BY timestamp DESC"
        ).fetchall()
        return [ThreatRecord.from_row(dict(r)) for r in rows]

    def acknowledge(self, threat_id: str, by: str = "user") -> bool:
        cur = self._conn.execute(
            "UPDATE threats SET acknowledged=1, acknowledged_at=?, acknowledged_by=? WHERE id=?",
            (datetime.now().isoformat(), by, threat_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def count_active(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM threats WHERE acknowledged=0"
        ).fetchone()
        return row[0]

    def close(self) -> None:
        self._conn.close()
