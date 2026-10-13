"""
Guardian Semantic Memory
========================
User-approved facts, preferences, and persistent knowledge.

Constitution reference: Section 8.3 — Semantic Memory
"Facts, preferences, and project context explicitly provided by the user."

Key rules:
  - ONLY stored when user explicitly asks Guardian to remember something
  - Readable by Guardian to personalise responses
  - Deletable by user at any time
  - Categories: 'preference', 'fact', 'project', 'general'
  - Keys are case-insensitive, normalised to lowercase

Examples of semantic facts:
  key="preferred_language"    value="Python"       category="preference"
  key="name"                  value="Alice"         category="preference"
  key="current_project"       value="AI Guardian"   category="project"
  key="timezone"              value="Asia/Kolkata"  category="preference"

Transparency:
  - Every set/delete is logged
  - All facts visible via list_all()
  - Context string injected into system prompt is shown on /status

Permissions: Level 1 — writes to workspace memory/ directory
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from guardian.logging.logger import get_logger
from guardian.memory.store import MemoryStore

log = get_logger(__name__)

VALID_CATEGORIES = {"preference", "fact", "project", "general"}


@dataclass
class SemanticFact:
    """A single stored fact or preference."""
    key: str
    value: str
    category: str
    source: str
    timestamp: datetime
    notes: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "SemanticFact":
        return cls(
            key=row["key"],
            value=row["value"],
            category=row.get("category", "general"),
            source=row.get("source", "user"),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            notes=row.get("notes", ""),
        )

    def to_context_line(self) -> str:
        """Format as a single line for injection into the system prompt."""
        return f"- {self.key}: {self.value}"


class SemanticMemory:
    """
    Persistent key-value store for facts and preferences.

    Usage:
        sm = SemanticMemory(store)
        sm.set("preferred_language", "Python", category="preference")
        value = sm.get("preferred_language")   # "Python"
        facts = sm.list_all()
        sm.delete("preferred_language")
    """

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def set(
        self,
        key: str,
        value: str,
        category: str = "general",
        source: str = "user",
        notes: str = "",
    ) -> None:
        """
        Store or update a fact. Key is normalised to lowercase.
        Overwrites existing value if key already exists.
        """
        if not key.strip():
            raise ValueError("Semantic memory key must not be empty")
        if not value.strip():
            raise ValueError("Semantic memory value must not be empty")
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Category must be one of {sorted(VALID_CATEGORIES)}, got {category!r}"
            )

        normalised_key = key.strip().lower()
        ts = datetime.now().isoformat()

        self._store.execute(
            """
            INSERT INTO semantic (key, value, category, source, timestamp, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                category=excluded.category,
                source=excluded.source,
                timestamp=excluded.timestamp,
                notes=excluded.notes
            """,
            (normalised_key, value.strip(), category, source, ts, notes),
        )
        log.info(f"Semantic set: key={normalised_key!r} category={category}")

    def get(self, key: str) -> str | None:
        """Return the value for a key, or None if not found."""
        normalised = key.strip().lower()
        rows = self._store.fetchall(
            "SELECT value FROM semantic WHERE key = ?", (normalised,)
        )
        return rows[0]["value"] if rows else None

    def get_fact(self, key: str) -> SemanticFact | None:
        """Return the full SemanticFact for a key, or None if not found."""
        normalised = key.strip().lower()
        rows = self._store.fetchall(
            "SELECT * FROM semantic WHERE key = ?", (normalised,)
        )
        return SemanticFact.from_row(rows[0]) if rows else None

    def delete(self, key: str) -> bool:
        """Permanently delete a fact. Returns True if it existed."""
        normalised = key.strip().lower()
        cur = self._store.execute(
            "DELETE FROM semantic WHERE key = ?", (normalised,)
        )
        deleted = cur.rowcount > 0
        if deleted:
            log.info(f"Semantic deleted: key={normalised!r}")
        else:
            log.warning(f"Semantic delete: key={normalised!r} not found")
        return deleted

    def clear(self, category: str | None = None) -> int:
        """
        Delete all facts (or all facts in a category).
        Returns count deleted. Logged at WARNING level.
        """
        if category:
            cur = self._store.execute(
                "DELETE FROM semantic WHERE category = ?", (category,)
            )
        else:
            cur = self._store.execute("DELETE FROM semantic")
        count = cur.rowcount
        scope = f"category={category!r}" if category else "ALL"
        log.warning(f"Semantic memory cleared ({scope}): {count} records deleted")
        return count

    def list_all(self, category: str | None = None) -> list[SemanticFact]:
        """Return all facts, optionally filtered by category."""
        if category:
            rows = self._store.fetchall(
                "SELECT * FROM semantic WHERE category = ? ORDER BY key",
                (category,),
            )
        else:
            rows = self._store.fetchall(
                "SELECT * FROM semantic ORDER BY category, key"
            )
        return [SemanticFact.from_row(r) for r in rows]

    def count(self) -> int:
        """Return total number of stored facts."""
        rows = self._store.fetchall("SELECT COUNT(*) as n FROM semantic")
        return rows[0]["n"] if rows else 0

    def to_context_prompt(self) -> str:
        """
        Return all stored facts as a formatted block for injection
        into the Guardian system prompt.

        Example output:
            User preferences and known facts:
            - name: Alice
            - preferred_language: Python
            - timezone: Asia/Kolkata
        """
        facts = self.list_all()
        if not facts:
            return ""
        lines = ["User preferences and known facts:"]
        lines.extend(f.to_context_line() for f in facts)
        return "\n".join(lines)
