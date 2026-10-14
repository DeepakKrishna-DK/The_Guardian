"""
Unit Tests for Semantic Knowledge Engine (semantic_search.py)
=============================================================
Verifies:
  - SQLite chunk_embeddings schema initialization
  - Vector serialization and deserialization
  - Incremental chunk indexing and reindexing
  - Keyword FTS5 retrieval
  - Semantic vector similarity with paraphrased queries
  - Reciprocal Rank Fusion (RRF) formula and ranking diagnostics
  - Hybrid search integration and defensive fallbacks
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semantic_search import (
    RRF_K,
    connect,
    deserialize_vector,
    hybrid_search,
    index_missing_chunks,
    init_embeddings_table,
    keyword_search,
    reciprocal_rank_fusion,
    reindex_all_chunks,
    semantic_search,
    serialize_vector,
)


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Creates a temporary SQLite database with documents, chunks, and FTS5 tables."""
    db_file = tmp_path / "test_knowledge.db"
    conn = sqlite3.connect(str(db_file))

    conn.execute("""
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            char_count INTEGER NOT NULL,
            chunk_count INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            content,
            document_id UNINDEXED,
            chunk_index UNINDEXED,
            tokenize='porter unicode61'
        )
    """)

    # Ingest test corpus
    doc1_id = "doc_rag"
    doc1_text = (
        "Retrieval-augmented generation allows a language model to consult external documents "
        "at inference time. It can improve factual grounding and access to specialized knowledge "
        "without updating the model's trained parameters."
    )
    conn.execute(
        "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
        (doc1_id, "retrieval-test.md", "md", "2026-10-14T00:00:00Z", len(doc1_text), 1),
    )
    conn.execute(
        "INSERT INTO chunks VALUES (?, ?, ?, ?)",
        ("doc_rag_0", doc1_id, 0, doc1_text),
    )
    conn.execute(
        "INSERT INTO chunks_fts (content, document_id, chunk_index) VALUES (?, ?, ?)",
        (doc1_text, doc1_id, 0),
    )

    doc2_id = "doc_quantum"
    doc2_text = (
        "Topological quantum computation employs non-Abelian anyons to protect quantum "
        "information against environmental decoherence and local perturbations."
    )
    conn.execute(
        "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
        (doc2_id, "quantum_physics.txt", "txt", "2026-10-14T00:00:00Z", len(doc2_text), 1),
    )
    conn.execute(
        "INSERT INTO chunks VALUES (?, ?, ?, ?)",
        ("doc_quantum_0", doc2_id, 0, doc2_text),
    )
    conn.execute(
        "INSERT INTO chunks_fts (content, document_id, chunk_index) VALUES (?, ?, ?)",
        (doc2_text, doc2_id, 0),
    )

    conn.commit()
    conn.close()
    return db_file


class TestVectorSerialization:
    """Verifies vector byte conversions."""

    def test_roundtrip(self):
        vec = np.array([0.1, -0.5, 0.99, 0.0], dtype=np.float32)
        blob = serialize_vector(vec)
        restored = deserialize_vector(blob)
        assert np.allclose(vec, restored, atol=1e-6)
        assert restored.dtype == np.float32


class TestEmbeddingIndexing:
    """Verifies SQLite vector persistence and reindexing."""

    def test_index_missing_chunks(self, test_db: Path):
        with connect(test_db) as conn:
            init_embeddings_table(conn)
            count = index_missing_chunks(conn)
            assert count == 2

            # Second call should find 0 missing
            count_repeat = index_missing_chunks(conn)
            assert count_repeat == 0

            # Verify rows in chunk_embeddings
            cursor = conn.execute("SELECT COUNT(*) FROM chunk_embeddings")
            assert cursor.fetchone()[0] == 2

    def test_reindex_all_chunks(self, test_db: Path):
        with connect(test_db) as conn:
            init_embeddings_table(conn)
            index_missing_chunks(conn)
            reindexed = reindex_all_chunks(conn)
            assert reindexed == 2


class TestKeywordAndSemanticSearch:
    """Verifies individual retrieval channels."""

    def test_keyword_exact_term(self, test_db: Path):
        with connect(test_db) as conn:
            results = keyword_search(conn, "non-Abelian anyons perturbations")
            assert len(results) >= 1
            assert results[0]["filename"] == "quantum_physics.txt"
            assert "anyons" in results[0]["content"]

    def test_semantic_paraphrased_query(self, test_db: Path):
        # Query uses completely different words:
        # "How can an AI access new information without retraining its neural network?"
        # Matches doc1: "Retrieval-augmented generation allows a language model to consult external documents at inference time without updating parameters."
        with connect(test_db) as conn:
            index_missing_chunks(conn)
            results = semantic_search(
                conn,
                "How can an AI access new information without retraining its neural network?",
                limit=2,
            )
            assert len(results) >= 1
            top = results[0]
            assert top["filename"] == "retrieval-test.md"
            assert top["semantic_score"] > 0.3


class TestReciprocalRankFusion:
    """Verifies RRF calculation and diagnostics."""

    def test_rrf_scoring_and_deduplication(self):
        kw_results = [
            {"chunk_id": "c1", "content": "chunk 1", "filename": "f1", "document_id": "d1", "chunk_index": 0, "keyword_score": 5.0},
            {"chunk_id": "c2", "content": "chunk 2", "filename": "f2", "document_id": "d2", "chunk_index": 0, "keyword_score": 3.0},
        ]
        sem_results = [
            {"chunk_id": "c2", "content": "chunk 2", "filename": "f2", "document_id": "d2", "chunk_index": 0, "semantic_score": 0.95},
            {"chunk_id": "c3", "content": "chunk 3", "filename": "f3", "document_id": "d3", "chunk_index": 0, "semantic_score": 0.85},
        ]

        fused = reciprocal_rank_fusion(kw_results, sem_results, k=60, limit=5)
        assert len(fused) == 3

        # c2 is present in both channels (rank 2 in KW, rank 1 in Sem)
        # RRF(c2) = (1 / (60 + 2)) + (1 / (60 + 1)) = (1/62) + (1/61) = 0.016129 + 0.016393 = ~0.03252
        # c1 has rank 1 in KW only: 1 / 61 = ~0.01639
        # Therefore, c2 MUST rank first due to reciprocal fusion!
        assert fused[0]["chunk_id"] == "c2"
        assert fused[0]["keyword_rank"] == 2
        assert fused[0]["semantic_rank"] == 1
        assert fused[0]["semantic_score"] == 0.95
        assert fused[0]["keyword_score"] == 3.0

        expected_c2_rrf = round((1.0 / 62.0) + (1.0 / 61.0), 5)
        assert fused[0]["rrf_score"] == expected_c2_rrf


class TestHybridSearchIntegration:
    """Verifies complete end-to-end hybrid retrieval."""

    def test_hybrid_search_end_to_end(self, test_db: Path):
        # Search with a query that benefits from both keyword and semantics
        results = hybrid_search(
            "How can a model consult external knowledge without retraining?",
            test_db,
            limit=2,
        )
        assert len(results) >= 1
        assert results[0]["filename"] == "retrieval-test.md"
        assert "rrf_score" in results[0]
        assert "score" in results[0]

    def test_hybrid_search_fallback_when_model_fails(self, test_db: Path):
        # When get_model returns None, fallback to keyword retrieval
        with patch("semantic_search.get_model", return_value=None):
            results = hybrid_search("quantum anyons", test_db, limit=2)
            assert len(results) >= 1
            assert results[0]["filename"] == "quantum_physics.txt"
            assert results[0]["keyword_rank"] == 1
            assert results[0]["semantic_rank"] is None
