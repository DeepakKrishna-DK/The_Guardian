"""
Tests for Phase 9 — Knowledge Layer (RAG) and Phase 9a — MCP Adapter
======================================================================
All tests are deterministic:
  - MockEmbedder (no model download, no torch, deterministic vectors)
  - VectorStore(in_memory=True, collection_name=unique) — no files written
    (chromadb 1.5.9 EphemeralClient is NOT isolated between instances,
     so each fixture gets a unique collection name)
  - chromadb 1.5.9 requires non-empty metadata dicts

Covers:
  Chunker, MockEmbedder, VectorStore, DocumentLoader,
  KnowledgeRetriever, KnowledgeLayer, MCP server schema
"""

from __future__ import annotations

import math
import uuid
from pathlib import Path

import pytest

from guardian.knowledge import (
    KnowledgeLayer,
    reset_knowledge_layer,
)
from guardian.knowledge.chunk import Chunk, Chunker
from guardian.knowledge.embedder import MockEmbedder, SentenceTransformerEmbedder
from guardian.knowledge.loader import Document, DocumentLoader
from guardian.knowledge.retriever import KnowledgeRetriever
from guardian.knowledge.vector_store import SearchResult, VectorStore


def _unique_store(dims: int = 64) -> VectorStore:
    """Create an in-memory VectorStore with a unique collection name (test isolation)."""
    return VectorStore(in_memory=True, collection_name=f"test_{uuid.uuid4().hex[:12]}")


def _make_embedder(dims: int = 64) -> MockEmbedder:
    return MockEmbedder(dims=dims)


def _make_retriever(workspace: Path, dims: int = 64) -> KnowledgeRetriever:
    store    = _unique_store(dims)
    embedder = _make_embedder(dims)
    return KnowledgeRetriever(
        store=store,
        embedder=embedder,
        workspace_root=workspace,
        relevance_threshold=-1.0,  # MockEmbedder is random — accept any similarity
    )


def _make_layer(workspace: Path, dims: int = 64) -> KnowledgeLayer:
    store    = _unique_store(dims)
    embedder = _make_embedder(dims)
    from guardian.knowledge.retriever import KnowledgeRetriever
    retriever = KnowledgeRetriever(
        store=store, embedder=embedder, workspace_root=workspace,
        relevance_threshold=-1.0,  # accept all in tests — MockEmbedder is not semantic
    )
    return KnowledgeLayer(retriever)


@pytest.fixture(autouse=True)
def reset():
    reset_knowledge_layer()
    yield
    reset_knowledge_layer()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


# ─── Chunker ──────────────────────────────────────────────────────────────────

class TestChunker:
    def test_empty_text_returns_no_chunks(self):
        chunker = Chunker(chunk_size=10, overlap=2)
        assert chunker.chunk("", "test.txt") == []

    def test_whitespace_only_returns_no_chunks(self):
        chunker = Chunker(chunk_size=10, overlap=2)
        assert chunker.chunk("   \n\n  ", "test.txt") == []

    def test_single_chunk_for_short_text(self):
        chunker = Chunker(chunk_size=100, overlap=10)
        text = "hello world this is a short document"
        chunks = chunker.chunk(text, "test.txt")
        assert len(chunks) == 1
        assert chunks[0].source == "test.txt"
        assert chunks[0].chunk_index == 0
        assert chunks[0].total_chunks == 1

    def test_multiple_chunks_for_long_text(self):
        chunker = Chunker(chunk_size=5, overlap=1)
        words = ["word"] * 20
        text = " ".join(words)
        chunks = chunker.chunk(text, "test.txt")
        assert len(chunks) > 1

    def test_chunk_ids_are_deterministic(self):
        chunker = Chunker(chunk_size=5, overlap=1)
        text = " ".join(["word"] * 20)
        c1 = chunker.chunk(text, "test.txt")
        c2 = chunker.chunk(text, "test.txt")
        assert [c.id for c in c1] == [c.id for c in c2]

    def test_chunk_ids_differ_by_source(self):
        chunker = Chunker(chunk_size=5, overlap=1)
        text = " ".join(["word"] * 10)
        c1 = chunker.chunk(text, "a.txt")
        c2 = chunker.chunk(text, "b.txt")
        ids1 = {c.id for c in c1}
        ids2 = {c.id for c in c2}
        assert ids1.isdisjoint(ids2)

    def test_overlap_is_less_than_chunk_size(self):
        with pytest.raises(ValueError):
            Chunker(chunk_size=5, overlap=5)

    def test_preview_truncates(self):
        chunk = Chunk(
            id="abc", content="a " * 200, source="x.txt",
            chunk_index=0, total_chunks=1, word_count=200,
        )
        assert len(chunk.preview(max_chars=50)) <= 53  # 50 + "..."

    def test_word_count_is_accurate(self):
        chunker = Chunker(chunk_size=10, overlap=2)
        text = " ".join(["hello"] * 10)
        chunks = chunker.chunk(text, "t.txt")
        assert chunks[0].word_count == len(chunks[0].content.split())


# ─── MockEmbedder ─────────────────────────────────────────────────────────────

class TestMockEmbedder:
    def test_dimensions_match(self):
        e = MockEmbedder(dims=128)
        vecs = e.embed(["test"])
        assert len(vecs[0]) == 128
        assert e.dimensions == 128

    def test_deterministic(self):
        e = MockEmbedder(dims=32)
        v1 = e.embed(["hello world"])
        v2 = e.embed(["hello world"])
        assert v1 == v2

    def test_different_texts_give_different_vectors(self):
        e = MockEmbedder(dims=64)
        v1 = e.embed(["hello"])[0]
        v2 = e.embed(["goodbye"])[0]
        assert v1 != v2

    def test_vectors_are_normalised(self):
        e = MockEmbedder(dims=64)
        vec = e.embed(["test sentence"])[0]
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-6

    def test_batch_embed(self):
        e = MockEmbedder(dims=32)
        texts = ["alpha", "beta", "gamma"]
        vecs = e.embed(texts)
        assert len(vecs) == 3
        for v in vecs:
            assert len(v) == 32

    def test_empty_list_returns_empty(self):
        e = MockEmbedder()
        assert e.embed([]) == []


# ─── SentenceTransformerEmbedder (interface only, no model load) ───────────────

class TestSentenceTransformerEmbedderInterface:
    def test_dimensions_without_loading_returns_default(self):
        e = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
        assert e.dimensions == 384

    def test_model_name(self):
        e = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
        assert "MiniLM" in e.model_name


# ─── VectorStore ──────────────────────────────────────────────────────────────

class TestVectorStore:
    def _make_embedding(self, seed: int = 0, dims: int = 8) -> list[float]:
        import random
        rng = random.Random(seed)
        vec = [rng.gauss(0, 1) for _ in range(dims)]
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec]

    def _new_store(self, dims: int = 8) -> VectorStore:
        return VectorStore(in_memory=True, collection_name=f"vs_{uuid.uuid4().hex[:12]}")

    def test_count_starts_at_zero(self):
        store = self._new_store()
        assert store.count() == 0

    def test_add_and_count(self):
        store = self._new_store()
        store.add(
            ids=["a", "b"],
            embeddings=[self._make_embedding(0), self._make_embedding(1)],
            documents=["doc a", "doc b"],
            metadatas=[{"source": "f.txt", "chunk_index": 0},
                       {"source": "f.txt", "chunk_index": 1}],
        )
        assert store.count() == 2

    def test_add_empty_is_safe(self):
        store = self._new_store()
        store.add(ids=[], embeddings=[], documents=[], metadatas=[])
        assert store.count() == 0

    def test_query_returns_results(self):
        store = self._new_store()
        store.add(
            ids=["x"],
            embeddings=[self._make_embedding(42)],
            documents=["firewall rules"],
            metadatas=[{"source": "sec.md", "chunk_index": 0}],
        )
        results = store.query(self._make_embedding(42), n_results=1)
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].relevance > 0.9

    def test_query_empty_store_returns_empty(self):
        store = self._new_store()
        assert store.query(self._make_embedding(0)) == []

    def test_list_sources(self):
        store = self._new_store()
        store.add(
            ids=["a", "b"],
            embeddings=[self._make_embedding(0), self._make_embedding(1)],
            documents=["text a", "text b"],
            metadatas=[{"source": "a.txt", "chunk_index": 0},
                       {"source": "b.txt", "chunk_index": 0}],
        )
        sources = store.list_sources()
        assert "a.txt" in sources
        assert "b.txt" in sources

    def test_delete_by_source(self):
        store = self._new_store()
        store.add(
            ids=["a"],
            embeddings=[self._make_embedding(0)],
            documents=["text"],
            metadatas=[{"source": "target.txt", "chunk_index": 0}],
        )
        assert store.count() == 1
        deleted = store.delete_by_source("target.txt")
        assert deleted == 1
        assert store.count() == 0

    def test_delete_nonexistent_source_returns_zero(self):
        store = self._new_store()
        assert store.delete_by_source("nonexistent.txt") == 0

    def test_clear_removes_all(self):
        store = self._new_store()
        store.add(
            ids=["a", "b"],
            embeddings=[self._make_embedding(0), self._make_embedding(1)],
            documents=["text a", "text b"],
            metadatas=[{"source": "f.txt", "chunk_index": 0},
                       {"source": "f.txt", "chunk_index": 1}],
        )
        store.clear()
        assert store.count() == 0

    def test_upsert_same_id_replaces(self):
        store = self._new_store()
        emb = self._make_embedding(0)
        store.add(ids=["same-id"], embeddings=[emb],
                  documents=["original"], metadatas=[{"source": "f.txt", "chunk_index": 0}])
        store.add(ids=["same-id"], embeddings=[emb],
                  documents=["updated"], metadatas=[{"source": "f.txt", "chunk_index": 0}])
        assert store.count() == 1

    def test_get_by_source(self):
        store = self._new_store()
        store.add(
            ids=["z"],
            embeddings=[self._make_embedding(5)],
            documents=["content"],
            metadatas=[{"source": "z.txt", "chunk_index": 0}],
        )
        chunks = store.get_by_source("z.txt")
        assert len(chunks) == 1
        assert chunks[0]["content"] == "content"


# ─── DocumentLoader ───────────────────────────────────────────────────────────

class TestDocumentLoader:
    def test_load_txt(self, workspace):
        (workspace / "doc.txt").write_text("Hello world content", encoding="utf-8")
        loader = DocumentLoader(workspace)
        doc = loader.load(Path("doc.txt"))
        assert doc is not None
        assert "Hello world" in doc.content
        assert doc.extension == ".txt"

    def test_load_markdown(self, workspace):
        (workspace / "guide.md").write_text("# Title\n\nSome markdown content.", encoding="utf-8")
        loader = DocumentLoader(workspace)
        doc = loader.load(Path("guide.md"))
        assert doc is not None
        assert "Title" in doc.content

    def test_load_python_source(self, workspace):
        (workspace / "main.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
        loader = DocumentLoader(workspace)
        doc = loader.load(Path("main.py"))
        assert doc is not None
        assert "def hello" in doc.content

    def test_nonexistent_returns_none(self, workspace):
        loader = DocumentLoader(workspace)
        assert loader.load(Path("does_not_exist.txt")) is None

    def test_empty_file_returns_none(self, workspace):
        (workspace / "empty.txt").write_text("", encoding="utf-8")
        loader = DocumentLoader(workspace)
        assert loader.load(Path("empty.txt")) is None

    def test_unknown_extension_returns_none(self, workspace):
        f = workspace / "file.xyz123"
        f.write_bytes(b"\x00\x01\x02\x03")
        loader = DocumentLoader(workspace)
        assert loader.load(Path("file.xyz123")) is None

    def test_source_label_is_relative(self, workspace):
        f = workspace / "sub" / "doc.md"
        f.parent.mkdir()
        f.write_text("content", encoding="utf-8")
        loader = DocumentLoader(workspace)
        doc = loader.load(f)
        assert ".." not in doc.source_label
        assert doc.source_label.endswith("doc.md")

    def test_load_directory(self, workspace):
        (workspace / "a.txt").write_text("text a", encoding="utf-8")
        (workspace / "b.md").write_text("text b", encoding="utf-8")
        (workspace / "__pycache__").mkdir()
        (workspace / "__pycache__" / "skip.pyc").write_bytes(b"\x00")
        loader = DocumentLoader(workspace)
        docs = list(loader.load_directory(workspace))
        labels = {d.source_label for d in docs}
        assert any("a.txt" in l for l in labels)
        assert any("b.md" in l for l in labels)
        assert all("__pycache__" not in l for l in labels)

    def test_absolute_path_load(self, workspace):
        f = workspace / "abs.txt"
        f.write_text("absolute path test", encoding="utf-8")
        loader = DocumentLoader(workspace)
        doc = loader.load(f)
        assert doc is not None

    def test_pdf_graceful_on_empty(self, workspace):
        f = workspace / "doc.pdf"
        f.write_bytes(b"%PDF-1.4")  # minimal/corrupt PDF — loader handles gracefully
        loader = DocumentLoader(workspace)
        result = loader.load(f)
        # Either None (empty content) or a Document (if pypdf extracted something)
        assert result is None or isinstance(result, Document)


# ─── KnowledgeRetriever ───────────────────────────────────────────────────────

class TestKnowledgeRetriever:
    def test_ingest_txt_file(self, workspace):
        r = _make_retriever(workspace)
        f = workspace / "doc.txt"
        f.write_text("The Guardian authority model has three levels.", encoding="utf-8")
        result = r.ingest(Path("doc.txt"))
        assert result.success
        assert result.chunks_added >= 1

    def test_ingest_returns_chunk_count(self, workspace):
        r = _make_retriever(workspace)
        words = " ".join(["word"] * 1000)
        (workspace / "long.txt").write_text(words, encoding="utf-8")
        result = r.ingest(Path("long.txt"))
        assert result.chunks_added > 1

    def test_ingest_nonexistent_skipped(self, workspace):
        r = _make_retriever(workspace)
        result = r.ingest(Path("no_such_file.txt"))
        assert result.skipped

    def test_ingest_replaces_on_reingest(self, workspace):
        r = _make_retriever(workspace)
        f = workspace / "doc.txt"
        f.write_text("version one content here for test", encoding="utf-8")
        r.ingest(Path("doc.txt"))
        count1 = r._store.count()

        f.write_text("version two updated content here", encoding="utf-8")
        r.ingest(Path("doc.txt"), replace=True)
        count2 = r._store.count()
        assert count2 == count1  # replaced, not doubled

    def test_query_returns_results_after_ingest(self, workspace):
        r = _make_retriever(workspace)
        (workspace / "sec.md").write_text(
            "Level 0 means observe only. Level 1 allows writes. Level 2 is dangerous.",
            encoding="utf-8",
        )
        r.ingest(Path("sec.md"))
        result = r.query("what are the authority levels?")
        assert result.found
        assert len(result.hits) >= 1

    def test_query_empty_store_returns_no_hits(self, workspace):
        r = _make_retriever(workspace)
        result = r.query("anything")
        assert not result.found
        assert result.context == ""

    def test_build_context_returns_string(self, workspace):
        r = _make_retriever(workspace)
        (workspace / "ctx.txt").write_text("Guardian uses skills for routing.", encoding="utf-8")
        r.ingest(Path("ctx.txt"))
        ctx = r.build_context("how does routing work?")
        assert isinstance(ctx, str)

    def test_build_context_empty_store_returns_empty_string(self, workspace):
        r = _make_retriever(workspace)
        assert r.build_context("hello") == ""

    def test_list_sources_after_ingest(self, workspace):
        r = _make_retriever(workspace)
        (workspace / "a.txt").write_text("content a here for test", encoding="utf-8")
        (workspace / "b.md").write_text("content b here for test", encoding="utf-8")
        r.ingest(Path("a.txt"))
        r.ingest(Path("b.md"))
        sources = r.list_sources()
        assert any("a.txt" in s for s in sources)
        assert any("b.md" in s for s in sources)

    def test_delete_source(self, workspace):
        r = _make_retriever(workspace)
        (workspace / "d.txt").write_text("deletable content here for test", encoding="utf-8")
        r.ingest(Path("d.txt"))
        sources_before = r.list_sources()
        assert any("d.txt" in s for s in sources_before)

        target = [s for s in sources_before if "d.txt" in s][0]
        r.delete_source(target)
        sources_after = r.list_sources()
        assert all("d.txt" not in s for s in sources_after)

    def test_status_dict(self, workspace):
        r = _make_retriever(workspace)
        (workspace / "s.txt").write_text("some content here", encoding="utf-8")
        r.ingest(Path("s.txt"))
        status = r.status()
        assert "total_chunks" in status
        assert status["total_chunks"] >= 1
        assert "MockEmbedder" in status["embedder"]

    def test_ingest_directory(self, workspace):
        r = _make_retriever(workspace)
        sub = workspace / "docs"
        sub.mkdir()
        (sub / "a.txt").write_text("document a text content here", encoding="utf-8")
        (sub / "b.md").write_text("document b markdown content here", encoding="utf-8")
        result = r.ingest(sub)
        assert result.chunks_added >= 2


# ─── KnowledgeLayer ───────────────────────────────────────────────────────────

class TestKnowledgeLayer:
    def test_is_empty_initially(self, workspace):
        layer = _make_layer(workspace)
        assert layer.is_empty()

    def test_ingest_makes_not_empty(self, workspace):
        layer = _make_layer(workspace)
        (workspace / "doc.txt").write_text("content here for test", encoding="utf-8")
        layer.ingest(Path("doc.txt"))
        assert not layer.is_empty()

    def test_query_returns_query_result(self, workspace):
        layer = _make_layer(workspace)
        (workspace / "q.txt").write_text("authority levels are zero one two", encoding="utf-8")
        layer.ingest(Path("q.txt"))
        result = layer.query("what are authority levels?")
        assert result.found

    def test_list_sources_empty_initially(self, workspace):
        layer = _make_layer(workspace)
        assert layer.list_sources() == []

    def test_status(self, workspace):
        layer = _make_layer(workspace)
        status = layer.status()
        assert "total_chunks" in status
        assert status["total_chunks"] == 0

    def test_build_context_empty_is_empty_string(self, workspace):
        layer = _make_layer(workspace)
        assert layer.build_context("anything") == ""

    def test_delete_source(self, workspace):
        layer = _make_layer(workspace)
        (workspace / "del.txt").write_text("content to delete here", encoding="utf-8")
        layer.ingest(Path("del.txt"))
        sources = layer.list_sources()
        assert sources
        layer.delete_source(sources[0])
        assert layer.is_empty()


# ─── MCP Server (schema-only, no stdio transport) ─────────────────────────────

class TestMCPServerSchema:
    def test_server_buildable(self):
        """MCPServer can be constructed without starting stdio transport."""
        from guardian.mcp.server import _make_mcp_server
        server = _make_mcp_server()
        assert server is not None

    def test_tool_names_registered(self):
        from guardian.mcp.server import _make_mcp_server
        server = _make_mcp_server()
        # MCPServer 2.x uses ._tool_manager (same as FastMCP)
        tool_names = list(server._tool_manager._tools.keys())
        assert "file_read" in tool_names
        assert "directory" in tool_names
        assert "search" in tool_names
        assert "knowledge_query" in tool_names
        assert "security_audit" in tool_names
        # Shell is NOT exposed over MCP for safety
        assert "shell" not in tool_names
