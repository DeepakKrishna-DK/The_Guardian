"""
Guardian Knowledge — Vector Store
=====================================
Persistent vector storage and similarity search via ChromaDB.

Design:
  - ChromaDB PersistentClient for production (keeps db on disk)
  - ChromaDB EphemeralClient for tests (in-memory, zero disk writes)
  - Pre-computed embeddings passed from the Embedder — ChromaDB's built-in
    embedding function is NOT used (avoids onnxruntime in the hot path)
  - Cosine similarity via ChromaDB HNSW (hnsw:space = "cosine")

Authority: Level 0 (read) for search; Level 1 (write) for add/delete.
License: ChromaDB (Apache 2.0) ✅
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guardian.logging.logger import get_logger

log = get_logger(__name__)

_COLLECTION_NAME = "guardian_knowledge"


@dataclass
class SearchResult:
    """One result from a similarity search."""
    chunk_id: str
    content: str
    source: str
    chunk_index: int
    distance: float        # 0 = identical, 2 = opposite (cosine distance)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def relevance(self) -> float:
        """Cosine similarity score: 1 = identical, -1 = opposite."""
        return 1.0 - self.distance


class VectorStore:
    """
    ChromaDB-backed vector store for Guardian knowledge chunks.

    Usage (production):
        store = VectorStore(db_path=Path("knowledge/chroma.db"))

    Usage (tests — pass unique collection_name to avoid shared state):
        store = VectorStore(in_memory=True, collection_name="test_foo")
    """

    def __init__(
        self,
        db_path: Path | None = None,
        in_memory: bool = False,
        collection_name: str = _COLLECTION_NAME,
    ) -> None:
        try:
            import chromadb
        except ImportError:
            raise ImportError("chromadb is required. Run: pip install chromadb")

        if in_memory:
            self._client = chromadb.EphemeralClient()
            log.debug("VectorStore: in-memory (ephemeral)")
        else:
            if db_path is None:
                raise ValueError("db_path required when not using in_memory=True")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(db_path))
            log.info(f"VectorStore: persistent at {db_path}")

        # Use "cosine" distance (1 - cosine_similarity)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Write operations (Level 1) ─────────────────────────────────────────

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Add or update chunks. IDs that already exist are replaced."""
        if not ids:
            return
        # ChromaDB upserts by ID
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        log.debug(f"VectorStore.add: {len(ids)} chunk(s)")

    def delete_by_source(self, source: str) -> int:
        """Delete all chunks from a given source. Returns count deleted."""
        existing = self._collection.get(where={"source": source})
        ids_to_delete = existing.get("ids", [])
        if ids_to_delete:
            self._collection.delete(ids=ids_to_delete)
            log.info(f"VectorStore: deleted {len(ids_to_delete)} chunk(s) from {source!r}")
        return len(ids_to_delete)

    def clear(self) -> None:
        """Delete all chunks from the store."""
        all_ids = self._collection.get()["ids"]
        if all_ids:
            self._collection.delete(ids=all_ids)
        log.info("VectorStore: cleared all chunks")

    # ── Read operations (Level 0) ──────────────────────────────────────────

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        source_filter: str | None = None,
    ) -> list[SearchResult]:
        """
        Return top-n chunks most similar to the query embedding.
        Optional source_filter restricts results to one document.
        """
        where = {"source": source_filter} if source_filter else None
        count = self.count()
        if count == 0:
            return []
        n = min(n_results, count)

        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        raw = self._collection.query(**kwargs)

        results: list[SearchResult] = []
        for i in range(len(raw["ids"][0])):
            meta = raw["metadatas"][0][i] or {}
            results.append(SearchResult(
                chunk_id    = raw["ids"][0][i],
                content     = raw["documents"][0][i],
                source      = meta.get("source", ""),
                chunk_index = int(meta.get("chunk_index", 0)),
                distance    = float(raw["distances"][0][i]),
                metadata    = meta,
            ))
        return results

    def list_sources(self) -> list[str]:
        """Return sorted list of distinct source paths ingested."""
        all_meta = self._collection.get(include=["metadatas"])["metadatas"]
        sources = {m.get("source", "") for m in (all_meta or []) if m}
        return sorted(sources)

    def count(self) -> int:
        """Total number of chunks in the store."""
        return self._collection.count()

    def get_by_source(self, source: str) -> list[dict[str, Any]]:
        """Return all raw chunks for a given source (for inspection)."""
        raw = self._collection.get(
            where={"source": source},
            include=["documents", "metadatas"],
        )
        results = []
        for i, doc_id in enumerate(raw.get("ids", [])):
            results.append({
                "id": doc_id,
                "content": (raw.get("documents") or [])[i] if raw.get("documents") else "",
                "metadata": (raw.get("metadatas") or [])[i] if raw.get("metadatas") else {},
            })
        return results
