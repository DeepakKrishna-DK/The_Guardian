"""
Guardian Memory Manager
========================
Coordinates all Guardian memory types and provides a single entry point.

Constitution reference: Section 8 (Memory), Section 11 (Transparency)

Memory types managed:
  episodic   — past conversation turns (auto-saved per turn, opt-out possible)
  semantic   — user facts and preferences (opt-in, explicit user action)

Usage:
    from guardian.memory import get_memory_manager
    mm = get_memory_manager()

    # Save a turn (call after each successful GuardianCore.process())
    mm.episodic.save_turn(session_id=..., turn_number=..., ...)

    # Store a user fact
    mm.semantic.set("name", "Alice", category="preference")

    # Get context for injection into system prompt
    context = mm.semantic.to_context_prompt()

    # Build a context-enriched system prompt
    full_prompt = mm.build_system_prompt(base_prompt)
"""

from __future__ import annotations

from pathlib import Path

from guardian.logging.logger import get_logger
from guardian.memory.episodic import EpisodicMemory
from guardian.memory.semantic import SemanticMemory
from guardian.memory.store import MemoryStore

log = get_logger(__name__)

# Default database location within the Guardian workspace
_DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "memory" / "guardian.db"


class MemoryManager:
    """
    Facade for all Guardian memory subsystems.

    Always use get_memory_manager() for the shared singleton.
    Construct directly only for testing (pass a MemoryStore with ':memory:').
    """

    def __init__(self, store: MemoryStore) -> None:
        self._store = store
        self.episodic = EpisodicMemory(store)
        self.semantic = SemanticMemory(store)
        log.debug(f"MemoryManager ready: db={store.path()}")

    def build_system_prompt(self, base_prompt: str) -> str:
        """
        Enrich the base system prompt with stored semantic facts.

        If the user has no stored facts, returns base_prompt unchanged.
        This is the mechanism by which Guardian personalises responses.
        """
        context = self.semantic.to_context_prompt()
        if not context:
            return base_prompt
        return f"{base_prompt}\n\n{context}"

    def status(self) -> dict[str, object]:
        """Return a summary dict for display in guardian status."""
        return {
            "db_path": self._store.path(),
            "episodic_count": self.episodic.count(),
            "semantic_count": self.semantic.count(),
        }

    def close(self) -> None:
        """Close the underlying database connection."""
        self._store.close()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: MemoryManager | None = None


def get_memory_manager(db_path: str | Path | None = None) -> MemoryManager:
    """
    Return the shared MemoryManager singleton.
    On first call, creates the store at db_path (or the default location).
    Subsequent calls ignore db_path and return the existing instance.
    """
    global _manager
    if _manager is None:
        resolved = Path(db_path) if db_path else _DEFAULT_DB
        store = MemoryStore(resolved)
        _manager = MemoryManager(store)
        log.info(f"Memory initialised: {resolved}")
    return _manager


def reset_memory_manager() -> None:
    """
    Reset the singleton (for testing only).
    Closes the existing connection before resetting.
    """
    global _manager
    if _manager is not None:
        _manager.close()
        _manager = None


__all__ = [
    "EpisodicMemory",
    "MemoryManager",
    "SemanticMemory",
    "MemoryStore",
    "get_memory_manager",
    "reset_memory_manager",
]
