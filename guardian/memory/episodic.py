"""
Guardian Episodic Memory
========================
Records of past conversation turns for long-term recall.

Constitution reference: Section 8.2 — Episodic Memory
"Records of significant past interactions that inform current context."

What is stored:
  - user_message      What the user asked
  - assistant_reply   What Guardian answered
  - model_provider    Which backend answered
  - model_name        Which specific model
  - tokens_used       Tokens consumed
  - duration_ms       Response latency
  - timestamp         When it happened (ISO 8601)
  - tags              Optional user tags (JSON list)
  - session_id        Which session this came from

What is NOT stored without explicit user action:
  - Sensitive data flagged by the user
  - System prompts (stored in prompts.py, not per-turn)

Transparency guarantee:
  - Every save() call is logged at INFO level
  - All records visible via list_recent() / search()
  - delete() and clear() are permanent and logged

Permissions: Level 1 — writes to workspace memory/ directory
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from guardian.logging.logger import get_logger
from guardian.memory.store import MemoryStore

log = get_logger(__name__)


@dataclass
class EpisodicRecord:
    """A single stored conversation turn."""
    id: str
    session_id: str
    turn_number: int
    user_message: str
    assistant_reply: str
    model_provider: str
    model_name: str
    tokens_used: int
    duration_ms: float
    timestamp: datetime
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "EpisodicRecord":
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            turn_number=row["turn_number"],
            user_message=row["user_message"],
            assistant_reply=row["assistant_reply"],
            model_provider=row.get("model_provider", ""),
            model_name=row.get("model_name", ""),
            tokens_used=row.get("tokens_used", 0),
            duration_ms=row.get("duration_ms", 0.0),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            tags=json.loads(row.get("tags", "[]")),
        )

    def preview(self, max_chars: int = 80) -> str:
        """Short string for display."""
        msg = self.user_message[:max_chars]
        if len(self.user_message) > max_chars:
            msg += "..."
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {msg}"


class EpisodicMemory:
    """
    Stores and retrieves past Guardian conversation turns.

    Usage:
        em = EpisodicMemory(store)
        record_id = em.save_turn(
            session_id="...", turn_number=1,
            user_message="...", assistant_reply="...",
            model_provider="groq", model_name="compound-mini",
            tokens_used=500, duration_ms=1200.0
        )
        records = em.list_recent(10)
        results = em.search("python")
        em.delete(record_id)
    """

    def __init__(self, store: MemoryStore, vector_store = None, embedder = None) -> None:
        self._store = store
        self._vector_store = vector_store
        self._embedder = embedder

    def save_turn(
        self,
        session_id: str,
        turn_number: int,
        user_message: str,
        assistant_reply: str,
        model_provider: str = "",
        model_name: str = "",
        tokens_used: int = 0,
        duration_ms: float = 0.0,
        tags: list[str] | None = None,
    ) -> str:
        """
        Persist one conversation turn. Returns the record ID.
        Logged at INFO level (transparency guarantee).
        """
        record_id = str(uuid.uuid4())
        ts = datetime.now().isoformat()
        tags_json = json.dumps(tags or [])

        self._store.execute(
            """
            INSERT INTO episodic
              (id, session_id, turn_number, user_message, assistant_reply,
               model_provider, model_name, tokens_used, duration_ms, timestamp, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (record_id, session_id, turn_number, user_message, assistant_reply,
             model_provider, model_name, tokens_used, duration_ms, ts, tags_json),
        )

        log.info(
            f"Episodic saved: id={record_id[:8]}... "
            f"turn={turn_number} tokens={tokens_used} "
            f"model={model_provider}/{model_name}"
        )
        if hasattr(self, '_vector_store') and self._vector_store and self._embedder:
            try:
                text = f"User: {user_message}\\nGuardian: {assistant_reply}"
                embedding = self._embedder.embed([text])[0]
                self._vector_store.add(
                    ids=[record_id],
                    embeddings=[embedding],
                    documents=[text],
                    metadatas=[{"source": "episodic", "session_id": session_id}]
                )
            except Exception as e:
                log.warning(f"Failed to embed turn {record_id}: {e}")
                
        return record_id

    def list_recent(self, limit: int = 20) -> list[EpisodicRecord]:
        """Return the most recent `limit` records, newest first."""
        rows = self._store.fetchall(
            "SELECT * FROM episodic ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [EpisodicRecord.from_row(r) for r in rows]

    def search(self, query: str, limit: int = 20) -> list[EpisodicRecord]:
        """
        Search over conversation history.
        Uses semantic embedding search if configured, falling back to SQLite LIKE search.
        """
        if hasattr(self, '_vector_store') and self._vector_store and self._embedder:
            try:
                if self._vector_store.count() > 0:
                    emb = self._embedder.embed([query])[0]
                    # We might get chunks from other sources if vector_store is shared,
                    # so filter by source="episodic"
                    results = self._vector_store.query(query_embedding=emb, n_results=limit, source_filter="episodic")
                    if results:
                        record_ids = [r.chunk_id for r in results]
                        placeholders = ",".join("?" for _ in record_ids)
                        rows = self._store.fetchall(
                            f"SELECT * FROM episodic WHERE id IN ({placeholders})",
                            tuple(record_ids)
                        )
                        row_map = {r["id"]: EpisodicRecord.from_row(r) for r in rows}
                        return [row_map[rid] for rid in record_ids if rid in row_map]
            except Exception as e:
                log.warning(f"Semantic search failed, falling back to SQL: {e}")
                
        # Fallback keyword search
        pattern = f"%{query}%"
        rows = self._store.fetchall(
            """
            SELECT * FROM episodic
            WHERE user_message LIKE ? OR assistant_reply LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (pattern, pattern, limit),
        )
        return [EpisodicRecord.from_row(r) for r in rows]

    def get(self, record_id: str) -> EpisodicRecord | None:
        """Retrieve one record by ID. Returns None if not found."""
        rows = self._store.fetchall(
            "SELECT * FROM episodic WHERE id = ?", (record_id,)
        )
        return EpisodicRecord.from_row(rows[0]) if rows else None

    def delete(self, record_id: str) -> bool:
        """
        Permanently delete one record. Returns True if deleted, False if not found.
        Logged at INFO level.
        """
        cur = self._store.execute(
            "DELETE FROM episodic WHERE id = ?", (record_id,)
        )
        deleted = cur.rowcount > 0
        if deleted:
            log.info(f"Episodic deleted: id={record_id[:8]}...")
        else:
            log.warning(f"Episodic delete: id={record_id[:8]}... not found")
        return deleted

    def clear(self) -> int:
        """
        Delete ALL episodic records. Returns count deleted.
        Logged at WARNING level — this is irreversible.
        """
        cur = self._store.execute("DELETE FROM episodic")
        count = cur.rowcount
        log.warning(f"Episodic memory cleared: {count} records deleted")
        return count

    def count(self) -> int:
        """Return total number of stored records."""
        rows = self._store.fetchall("SELECT COUNT(*) as n FROM episodic")
        return rows[0]["n"] if rows else 0

    def count_for_session(self, session_id: str) -> int:
        """Return number of records for a specific session."""
        rows = self._store.fetchall(
            "SELECT COUNT(*) as n FROM episodic WHERE session_id = ?",
            (session_id,),
        )
        return rows[0]["n"] if rows else 0
