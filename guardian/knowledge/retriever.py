"""
Guardian Knowledge — Retriever
=================================
High-level façade: ingest documents and answer queries via RAG.

Constitution reference: Section 8 (Memory) — Knowledge tier.
This is the component that all other modules call.

Flow:
  ingest(path)  →  load → chunk → embed → store
  query(text)   →  embed → search → format → return

Attribution: every result carries its source document + chunk position.
Level 0 (read/search), Level 1 (ingest/delete).

Integration with GuardianCore:
  build_context(question) returns a formatted string injected into the
  system prompt BEFORE the model call, providing grounded reference material.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guardian.knowledge.chunk import Chunker
from guardian.knowledge.embedder import Embedder
from guardian.knowledge.loader import Document, DocumentLoader
from guardian.knowledge.vector_store import SearchResult, VectorStore
from guardian.logging.logger import get_logger

log = get_logger(__name__)

_DEFAULT_N_RESULTS   = 5
_RELEVANCE_THRESHOLD = 0.25   # minimum cosine similarity to include in context
_MAX_CONTEXT_CHARS   = 3500   # cap on total chars injected per turn


@dataclass
class IngestResult:
    """Summary of a completed ingest operation."""
    source: str
    chunks_added: int
    chars_loaded: int
    skipped: bool = False
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error and not self.skipped


@dataclass
class QueryResult:
    """Wrapper around search results with formatted context."""
    question: str
    hits: list[SearchResult] = field(default_factory=list)
    context: str = ""

    @property
    def found(self) -> bool:
        return len(self.hits) > 0


class KnowledgeRetriever:
    """
    Orchestrates document ingestion and knowledge retrieval.

    Usage:
        retriever = KnowledgeRetriever(
            store=VectorStore(in_memory=True),
            embedder=MockEmbedder(),
            workspace_root=Path("."),
        )
        retriever.ingest(Path("docs/guide.md"))
        result = retriever.query("What is the authority model?")
        print(result.context)
    """

    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        workspace_root: Path,
        chunker: Chunker | None = None,
        n_results: int = _DEFAULT_N_RESULTS,
        relevance_threshold: float = _RELEVANCE_THRESHOLD,
    ) -> None:
        self._store     = store
        self._embedder  = embedder
        self._loader    = DocumentLoader(workspace_root)
        self._chunker   = chunker or Chunker()
        self._n         = n_results
        self._threshold = relevance_threshold

    # ── Ingest ────────────────────────────────────────────────────────────

    def ingest(self, path: Path, replace: bool = True) -> IngestResult:
        """
        Ingest a single file or directory.
        If replace=True, existing chunks for the source are deleted first.
        Returns IngestResult with chunk count and any error.
        """
        resolved = path if path.is_absolute() else (self._loader.root / path)

        if resolved.is_dir():
            return self._ingest_directory(resolved, replace)

        doc = self._loader.load(resolved)
        if doc is None:
            return IngestResult(source=str(path), chunks_added=0, chars_loaded=0, skipped=True)

        return self._ingest_document(doc, replace)

    def _ingest_document(self, doc: Document, replace: bool) -> IngestResult:
        try:
            if replace:
                self._store.delete_by_source(doc.source_label)

            chunks = self._chunker.chunk(doc.content, source=doc.source_label)
            if not chunks:
                return IngestResult(
                    source=doc.source_label, chunks_added=0,
                    chars_loaded=len(doc.content), skipped=True,
                )

            embeddings = self._embedder.embed([c.content for c in chunks])

            self._store.add(
                ids=[c.id for c in chunks],
                embeddings=embeddings,
                documents=[c.content for c in chunks],
                metadatas=[{
                    "source": c.source,
                    "chunk_index": c.chunk_index,
                    "total_chunks": c.total_chunks,
                    "word_count": c.word_count,
                } for c in chunks],
            )

            log.info(f"Ingested: {doc.source_label!r} → {len(chunks)} chunk(s)")
            return IngestResult(
                source=doc.source_label,
                chunks_added=len(chunks),
                chars_loaded=len(doc.content),
            )
        except Exception as exc:
            log.error(f"Ingest error for {doc.source_label!r}: {exc}")
            return IngestResult(
                source=doc.source_label, chunks_added=0,
                chars_loaded=0, error=str(exc),
            )

    def _ingest_directory(self, directory: Path, replace: bool) -> IngestResult:
        total_chunks = 0
        total_chars  = 0
        errors: list[str] = []

        for doc in self._loader.load_directory(directory):
            result = self._ingest_document(doc, replace)
            total_chunks += result.chunks_added
            total_chars  += result.chars_loaded
            if result.error:
                errors.append(result.error)

        return IngestResult(
            source=str(directory),
            chunks_added=total_chunks,
            chars_loaded=total_chars,
            error="; ".join(errors) if errors else "",
        )

    # ── Query ─────────────────────────────────────────────────────────────

    def query(
        self,
        question: str,
        n_results: int | None = None,
        source_filter: str | None = None,
    ) -> QueryResult:
        """
        Embed question, search vector store, return hits + formatted context.
        Returns QueryResult with empty hits if the store is empty.
        """
        if self._store.count() == 0:
            return QueryResult(question=question)

        q_vec = self._embedder.embed([question])[0]
        hits  = self._store.query(
            query_embedding=q_vec,
            n_results=n_results or self._n,
            source_filter=source_filter,
        )

        # Filter by relevance threshold
        hits = [h for h in hits if h.relevance >= self._threshold]

        context = self._format_context(question, hits)
        return QueryResult(question=question, hits=hits, context=context)

    def build_context(self, question: str) -> str:
        """
        Return a formatted knowledge context string ready for system prompt injection.
        Returns empty string if the store is empty or no relevant results found.
        """
        result = self.query(question)
        return result.context

    def _format_context(self, question: str, hits: list[SearchResult]) -> str:
        if not hits:
            return ""

        parts = ["## Relevant Knowledge\n"]
        total_chars = 0

        for hit in hits:
            snippet = hit.content.strip()
            entry = (
                f"**Source:** {hit.source} (chunk {hit.chunk_index + 1})\n"
                f"**Relevance:** {hit.relevance:.2f}\n"
                f"{snippet}\n"
            )
            if total_chars + len(entry) > _MAX_CONTEXT_CHARS:
                break
            parts.append(entry)
            parts.append("---")
            total_chars += len(entry)

        if len(parts) == 1:
            return ""

        parts.append("\n*Use the above excerpts to ground your answer. Always cite the source.*")
        return "\n".join(parts)

    # ── Management ────────────────────────────────────────────────────────

    def list_sources(self) -> list[str]:
        return self._store.list_sources()

    def delete_source(self, source: str) -> int:
        return self._store.delete_by_source(source)

    def status(self) -> dict[str, Any]:
        return {
            "total_chunks": self._store.count(),
            "sources": self._store.list_sources(),
            "embedder": type(self._embedder).__name__,
            "threshold": self._threshold,
        }
