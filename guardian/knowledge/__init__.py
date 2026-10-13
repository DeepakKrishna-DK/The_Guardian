"""
Guardian Knowledge Layer — Public API
========================================
Usage:
    from guardian.knowledge import get_knowledge_layer, KnowledgeLayer

    kl = get_knowledge_layer()
    kl.ingest(Path("docs/"))
    result = kl.query("what is the authority model?")
    context = kl.build_context("how do tools work?")  # inject into system prompt
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from guardian.knowledge.chunk import Chunk, Chunker
from guardian.knowledge.embedder import Embedder, MockEmbedder, SentenceTransformerEmbedder
from guardian.knowledge.loader import Document, DocumentLoader
from guardian.knowledge.retriever import IngestResult, KnowledgeRetriever, QueryResult
from guardian.knowledge.vector_store import SearchResult, VectorStore
from guardian.logging.logger import get_logger

log = get_logger(__name__)

# Default paths
_DEFAULT_DB   = Path(__file__).resolve().parent.parent.parent / "knowledge" / "chroma.db"
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent.parent


class KnowledgeLayer:
    """
    Unified façade for all knowledge operations.

    Wraps KnowledgeRetriever with singleton management and
    convenient status reporting.
    """

    def __init__(self, retriever: KnowledgeRetriever) -> None:
        self._retriever = retriever

    def ingest(self, path: Path | str, replace: bool = True) -> IngestResult:
        return self._retriever.ingest(Path(path), replace=replace)

    def query(self, question: str, n_results: int = 5) -> QueryResult:
        return self._retriever.query(question, n_results=n_results)

    def build_context(self, question: str) -> str:
        """Return context string for system prompt injection. Empty if nothing relevant."""
        return self._retriever.build_context(question)

    def list_sources(self) -> list[str]:
        return self._retriever.list_sources()

    def delete_source(self, source: str) -> int:
        return self._retriever.delete_source(source)

    def status(self) -> dict[str, Any]:
        return self._retriever.status()

    def is_empty(self) -> bool:
        return self._retriever.status()["total_chunks"] == 0


# ── Singleton ─────────────────────────────────────────────────────────────────

_layer: KnowledgeLayer | None = None


def get_knowledge_layer(
    db_path: Path | None = None,
    workspace_root: Path | None = None,
    use_mock_embedder: bool = False,
) -> KnowledgeLayer:
    """
    Return the shared KnowledgeLayer singleton.

    use_mock_embedder=True is for tests only — no model download.
    Otherwise, SentenceTransformerEmbedder is used (model downloaded on first embed).
    """
    global _layer
    if _layer is None:
        root  = workspace_root or _DEFAULT_ROOT
        store = VectorStore(db_path=db_path or _DEFAULT_DB)

        if use_mock_embedder:
            embedder: Embedder = MockEmbedder()
        else:
            embedder = SentenceTransformerEmbedder()

        retriever = KnowledgeRetriever(
            store=store,
            embedder=embedder,
            workspace_root=root,
        )
        _layer = KnowledgeLayer(retriever)
        log.info(f"KnowledgeLayer initialised: db={db_path or _DEFAULT_DB}")
    return _layer


def reset_knowledge_layer() -> None:
    """Reset singleton (for testing)."""
    global _layer
    _layer = None


def make_test_layer(workspace_root: Path) -> KnowledgeLayer:
    """
    Factory for tests: in-memory ChromaDB + MockEmbedder.
    No files written, no model downloaded.
    """
    store     = VectorStore(in_memory=True)
    embedder  = MockEmbedder()
    retriever = KnowledgeRetriever(
        store=store,
        embedder=embedder,
        workspace_root=workspace_root,
    )
    return KnowledgeLayer(retriever)


from guardian.knowledge.domains import (
    DOMAINS,
    STUDY_DIMENSIONS,
    KnowledgeDomain,
    KnowledgeLayerEnum,
    classify_domain_context,
    get_all_domains,
    get_domain,
)

__all__ = [
    "Chunk",
    "Chunker",
    "Document",
    "DocumentLoader",
    "Embedder",
    "IngestResult",
    "KnowledgeDomain",
    "KnowledgeLayer",
    "KnowledgeLayerEnum",
    "KnowledgeRetriever",
    "MockEmbedder",
    "QueryResult",
    "SearchResult",
    "SentenceTransformerEmbedder",
    "VectorStore",
    "DOMAINS",
    "STUDY_DIMENSIONS",
    "classify_domain_context",
    "get_all_domains",
    "get_domain",
    "get_knowledge_layer",
    "make_test_layer",
    "reset_knowledge_layer",
]
