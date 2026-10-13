import pytest

try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

pytestmark = pytest.mark.skipif(not HAS_CHROMADB, reason="chromadb is required for VectorStore tests")

from guardian.memory.store import MemoryStore
from guardian.memory.episodic import EpisodicMemory
from guardian.knowledge.vector_store import VectorStore
from guardian.knowledge.embedder import MockEmbedder

class SemanticMockEmbedder(MockEmbedder):
    def embed(self, texts: list[str]) -> list[list[float]]:
        normalized = []
        for t in texts:
            if "canine" in t.lower() or "retriever" in t.lower():
                normalized.append("dog")
            else:
                normalized.append(t)
        return super().embed(normalized)

def test_m8_semantic_search_fallback():
    store = MemoryStore(":memory:")
    vector_store = VectorStore(in_memory=True, collection_name="test_m8")
    embedder = SemanticMockEmbedder(dims=10)
    
    memory = EpisodicMemory(store, vector_store=vector_store, embedder=embedder)
    
    session_id = "test-session-m8"
    memory.save_turn(
        session_id=session_id,
        turn_number=1,
        user_message="I have a golden retriever.",
        assistant_reply="It is a great pet!"
    )
    
    # Semantic search with completely different keywords
    results = memory.search("Tell me about your canine.", limit=1)
    
    assert len(results) == 1
    assert "retriever" in results[0].user_message

def test_m8_sqlite_fallback():
    # If vector store is empty, it should fallback to sqlite LIKE
    store = MemoryStore(":memory:")
    vector_store = VectorStore(in_memory=True, collection_name="test_m8_fallback")
    embedder = SemanticMockEmbedder(dims=10)
    
    memory = EpisodicMemory(store, vector_store=vector_store, embedder=embedder)
    
    memory._store.execute(
        "INSERT INTO episodic (id, session_id, turn_number, user_message, assistant_reply, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        ("legacy_id", "session1", 1, "Raw SQLite data", "Reply", "2026-01-01")
    )
    
    results = memory.search("SQLite", limit=1)
    assert len(results) == 1
    assert results[0].user_message == "Raw SQLite data"
