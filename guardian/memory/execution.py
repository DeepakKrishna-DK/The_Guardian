from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import json
import uuid

from guardian.logging.logger import get_logger
from guardian.memory.store import MemoryStore

log = get_logger(__name__)

@dataclass
class ExecutionOutcome:
    """Metadata-only record of a tool/skill/procedure execution outcome (M4)."""
    id: str
    target_id: str          # tool_name, skill_name, technique_id, etc.
    target_type: str        # 'tool', 'skill', 'technique', 'procedure'
    success: bool
    duration_ms: float
    risk_flags: list[str]
    timestamp: datetime

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ExecutionOutcome":
        return cls(
            id=row["id"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            success=bool(row["success"]),
            duration_ms=row["duration_ms"],
            risk_flags=json.loads(row.get("risk_flags", "[]")),
            timestamp=datetime.fromisoformat(row["timestamp"])
        )


class ExecutionMemory:
    """
    Stores and retrieves metadata-only execution outcomes.
    Calculates decaying proficiency scores.
    """
    def __init__(self, store: MemoryStore, vector_store=None, embedder=None):
        self._store = store
        self._vector_store = vector_store
        self._embedder = embedder
        self._ensure_table()

    def _ensure_table(self):
        self._store.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_outcomes (
              id TEXT PRIMARY KEY,
              target_id TEXT NOT NULL,
              target_type TEXT NOT NULL,
              success INTEGER NOT NULL,
              duration_ms REAL NOT NULL,
              risk_flags TEXT,
              timestamp TEXT NOT NULL
            )
            """
        )
        self._store.execute(
            "CREATE INDEX IF NOT EXISTS idx_exec_target ON execution_outcomes(target_id, target_type)"
        )

    def save_outcome(self, target_id: str, target_type: str, success: bool, duration_ms: float, risk_flags: list[str] = None) -> str:
        record_id = str(uuid.uuid4())
        ts = datetime.now().isoformat()
        flags_json = json.dumps(risk_flags or [])
        
        self._store.execute(
            """
            INSERT INTO execution_outcomes 
              (id, target_id, target_type, success, duration_ms, risk_flags, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (record_id, target_id, target_type, int(success), duration_ms, flags_json, ts)
        )
        log.info(f"Saved outcome for {target_type} '{target_id}': success={success}")
        
        if hasattr(self, '_vector_store') and self._vector_store and self._embedder:
            try:
                text = f"Execution Outcome - Target: {target_id} ({target_type}), Success: {success}, Flags: {flags_json}"
                embedding = self._embedder.embed([text])[0]
                self._vector_store.add(
                    ids=[record_id],
                    embeddings=[embedding],
                    documents=[text],
                    metadatas=[{"source": "execution", "target_id": target_id, "success": success}]
                )
            except Exception as e:
                log.warning(f"Failed to embed execution outcome {record_id}: {e}")

        return record_id

    def list_recent(self, limit: int = 10, target_id: str = None) -> list[ExecutionOutcome]:
        if target_id:
            rows = self._store.fetchall(
                "SELECT * FROM execution_outcomes WHERE target_id = ? ORDER BY timestamp DESC LIMIT ?",
                (target_id, limit)
            )
        else:
            rows = self._store.fetchall(
                "SELECT * FROM execution_outcomes ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
        return [ExecutionOutcome.from_row(r) for r in rows]

    def compute_proficiency(self, target_id: str, half_life_days: float = 7.0) -> float:
        """
        Compute a decaying proficiency score between 0.0 and 1.0 based on recent successes and failures.
        Recent successes increase the score more than older ones.
        """
        outcomes = self.list_recent(limit=50, target_id=target_id)
        if not outcomes:
            return 0.5  # Neutral baseline
            
        now = datetime.now()
        total_weight = 0.0
        weighted_success = 0.0
        
        for outcome in outcomes:
            age_days = (now - outcome.timestamp).total_seconds() / 86400.0
            weight = 0.5 ** (age_days / half_life_days)
            
            total_weight += weight
            if outcome.success:
                weighted_success += weight
                
        if total_weight == 0.0:
            return 0.5
            
        return weighted_success / total_weight
