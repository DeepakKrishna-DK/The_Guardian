"""
Universal Intelligence & Responsible AI — Semantic Knowledge Engine
====================================================================
Hybrid retrieval engine combining:
  1. Lexical search via SQLite FTS5 (exact terminology, codes, identifiers)
  2. Semantic vector similarity via local embeddings (cosine similarity)
  3. Reciprocal Rank Fusion (RRF) with rank diagnostics and provenance

Key features:
  - Vector storage in SQLite BLOBs keyed by (chunk_id, model)
  - Auto-indexing of missing chunk embeddings on retrieval
  - Reciprocal Rank Fusion: RRF(d) = sum(1 / (k + rank_r(d))) with k = 60
  - CLI commands for corpus vector building, reindexing, and testing
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv

from guardian.logging.logger import get_logger

load_dotenv()
log = get_logger("semantic_search")

# ---------------------------------------------------------------------------
# Constants & Defaults
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)
BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
RRF_K = 60
CANDIDATE_LIMIT = 30


# ---------------------------------------------------------------------------
# Embedding Model Loader (Cached & Defensive)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=2)
def get_model(model_name: str = EMBEDDING_MODEL) -> Any:
    """
    Load the sentence embedding model once per process.
    Returns None if sentence-transformers is not available.
    """
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(model_name)
    except Exception as exc:
        log.warning(f"Could not load SentenceTransformer ('{model_name}'): {exc}")
        return None


# ---------------------------------------------------------------------------
# Database Utilities & Schema
# ---------------------------------------------------------------------------

def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open SQLite connection with row factory enabled."""
    path_obj = Path(db_path).resolve()
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path_obj), timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_embeddings_table(conn: sqlite3.Connection) -> None:
    """Create knowledge schema and chunk_embeddings table if they do not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            char_count INTEGER NOT NULL,
            chunk_count INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            content,
            document_id UNINDEXED,
            chunk_index UNINDEXED,
            tokenize='porter unicode61'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunk_embeddings (
            chunk_id TEXT NOT NULL,
            model TEXT NOT NULL,
            embedding BLOB NOT NULL,
            dim INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (chunk_id, model)
        )
    """)
    conn.commit()


def serialize_vector(vector: np.ndarray) -> bytes:
    """Convert float32 numpy array to raw bytes."""
    return vector.astype(np.float32).tobytes()


def deserialize_vector(blob: bytes) -> np.ndarray:
    """Convert raw bytes back to float32 numpy array."""
    return np.frombuffer(blob, dtype=np.float32)


# ---------------------------------------------------------------------------
# Vector Indexing
# ---------------------------------------------------------------------------

def index_missing_chunks(
    conn: sqlite3.Connection,
    model_name: str = EMBEDDING_MODEL,
    batch_size: int = BATCH_SIZE,
) -> int:
    """
    Find chunks in SQLite lacking embeddings for model_name and generate them.
    Returns the number of newly indexed chunks.
    """
    init_embeddings_table(conn)
    model = get_model(model_name)
    if model is None:
        log.info("SentenceTransformer unavailable; skipping embedding generation.")
        return 0

    try:
        cursor = conn.execute("""
            SELECT c.id, c.content
            FROM chunks c
            LEFT JOIN chunk_embeddings ce ON ce.chunk_id = c.id AND ce.model = ?
            WHERE ce.chunk_id IS NULL
        """, (model_name,))
        unindexed = cursor.fetchall()
    except sqlite3.OperationalError:
        return 0

    if not unindexed:
        return 0

    log.info(f"Generating semantic embeddings for {len(unindexed)} chunks using '{model_name}'...")
    total_indexed = 0
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for i in range(0, len(unindexed), batch_size):
        batch = unindexed[i : i + batch_size]
        chunk_ids = [row["id"] for row in batch]
        texts = [row["content"] for row in batch]

        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        dim = int(vectors.shape[1])

        records = [
            (cid, model_name, serialize_vector(vectors[idx]), dim, now_iso)
            for idx, cid in enumerate(chunk_ids)
        ]

        conn.executemany("""
            INSERT OR REPLACE INTO chunk_embeddings (chunk_id, model, embedding, dim, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, records)
        conn.commit()
        total_indexed += len(records)

    log.info(f"Successfully indexed {total_indexed} chunk embeddings.")
    return total_indexed


def reindex_all_chunks(
    conn: sqlite3.Connection,
    model_name: str = EMBEDDING_MODEL,
    batch_size: int = BATCH_SIZE,
) -> int:
    """
    Clear existing embeddings for model_name and rebuild from scratch.
    """
    init_embeddings_table(conn)
    conn.execute("DELETE FROM chunk_embeddings WHERE model = ?", (model_name,))
    conn.commit()
    log.info(f"Purged existing embeddings for '{model_name}'. Rebuilding...")
    return index_missing_chunks(conn, model_name=model_name, batch_size=batch_size)


# ---------------------------------------------------------------------------
# Retrieval Operations: Keyword & Semantic
# ---------------------------------------------------------------------------

def keyword_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = CANDIDATE_LIMIT,
) -> list[dict[str, Any]]:
    """
    Lexical retrieval using SQLite FTS5 with BM25 ranking (porter + unicode61 tokenizer).
    """
    cleaned_query = re.sub(r"[^\w\s]", "", query).strip()
    if not cleaned_query:
        return []

    tokens = cleaned_query.split()[:8]
    if not tokens:
        return []
    fts_tokens = " OR ".join(tokens)

    results: list[dict[str, Any]] = []
    try:
        cursor = conn.execute("""
            SELECT c.id as chunk_id, c.content, c.chunk_index, d.filename, d.id as doc_id, rank
            FROM chunks_fts(?) f
            JOIN chunks c ON c.document_id = f.document_id AND c.chunk_index = f.chunk_index
            JOIN documents d ON d.id = c.document_id
            ORDER BY rank
            LIMIT ?
        """, (fts_tokens, limit))
        for row in cursor.fetchall():
            results.append({
                "chunk_id": row["chunk_id"],
                "content": row["content"],
                "filename": row["filename"],
                "document_id": row["doc_id"],
                "chunk_index": row["chunk_index"],
                "keyword_score": round(-float(row["rank"]), 4) if row["rank"] is not None else 1.0,
            })
    except sqlite3.OperationalError as exc:
        log.warning(f"FTS query error ({exc}), falling back to LIKE...")
        cursor = conn.execute("""
            SELECT c.id as chunk_id, c.content, c.chunk_index, d.filename, d.id as doc_id
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.content LIKE ?
            LIMIT ?
        """, (f"%{cleaned_query[:30]}%", limit))
        for row in cursor.fetchall():
            results.append({
                "chunk_id": row["chunk_id"],
                "content": row["content"],
                "filename": row["filename"],
                "document_id": row["doc_id"],
                "chunk_index": row["chunk_index"],
                "keyword_score": 0.5,
            })

    return results


def semantic_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = CANDIDATE_LIMIT,
    model_name: str = EMBEDDING_MODEL,
) -> list[dict[str, Any]]:
    """
    Semantic retrieval computing cosine similarity over normalized stored vectors.
    """
    if not query.strip():
        return []

    model = get_model(model_name)
    if model is None:
        return []

    # Encode query into normalized float32 vector
    query_vec = model.encode(query.strip(), normalize_embeddings=True, show_progress_bar=False)
    query_vec = np.asarray(query_vec, dtype=np.float32)

    # Fetch stored vectors for the model
    cursor = conn.execute("""
        SELECT ce.chunk_id, ce.embedding, c.content, c.chunk_index, d.filename, d.id as doc_id
        FROM chunk_embeddings ce
        JOIN chunks c ON c.id = ce.chunk_id
        JOIN documents d ON d.id = c.document_id
        WHERE ce.model = ?
    """, (model_name,))
    rows = cursor.fetchall()

    if not rows:
        return []

    chunk_ids = []
    vector_list = []
    metadata = {}

    for row in rows:
        cid = row["chunk_id"]
        chunk_ids.append(cid)
        vector_list.append(deserialize_vector(row["embedding"]))
        metadata[cid] = {
            "chunk_id": cid,
            "content": row["content"],
            "filename": row["filename"],
            "document_id": row["doc_id"],
            "chunk_index": row["chunk_index"],
        }

    # Matrix multiplication: matrix (N, D) @ query_vec (D,) -> cosine similarities (N,)
    matrix = np.vstack(vector_list)
    sims = matrix @ query_vec

    # Sort descending
    top_indices = np.argsort(-sims)[:limit]

    results: list[dict[str, Any]] = []
    for idx in top_indices:
        cid = chunk_ids[idx]
        sim_score = float(sims[idx])
        item = dict(metadata[cid])
        item["semantic_score"] = round(sim_score, 4)
        results.append(item)

    return results


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion (RRF)
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    keyword_results: list[dict[str, Any]],
    semantic_results: list[dict[str, Any]],
    k: int = RRF_K,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Combine lexical and semantic rankings using Reciprocal Rank Fusion.
    RRF(d) = sum_{r in {keyword, semantic}} (1 / (k + rank_r(d)))
    """
    scores: dict[str, float] = {}
    items: dict[str, dict[str, Any]] = {}
    keyword_ranks: dict[str, int] = {}
    semantic_ranks: dict[str, int] = {}

    # 1. Process keyword candidates
    for rank_idx, item in enumerate(keyword_results, start=1):
        cid = item["chunk_id"]
        keyword_ranks[cid] = rank_idx
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank_idx))
        if cid not in items:
            items[cid] = dict(item)
        else:
            items[cid]["keyword_score"] = item.get("keyword_score")

    # 2. Process semantic candidates
    for rank_idx, item in enumerate(semantic_results, start=1):
        cid = item["chunk_id"]
        semantic_ranks[cid] = rank_idx
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank_idx))
        if cid not in items:
            items[cid] = dict(item)
        else:
            items[cid]["semantic_score"] = item.get("semantic_score")

    # 3. Sort by RRF score descending
    sorted_cids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:limit]

    merged_results: list[dict[str, Any]] = []
    for cid in sorted_cids:
        item = items[cid]
        merged_results.append({
            "chunk_id": cid,
            "content": item["content"],
            "filename": item["filename"],
            "document_id": item["document_id"],
            "chunk_index": item["chunk_index"],
            "rrf_score": round(scores[cid], 5),
            "score": round(scores[cid] * 100, 3),  # Normalized presentation score
            "keyword_rank": keyword_ranks.get(cid),
            "semantic_rank": semantic_ranks.get(cid),
            "keyword_score": item.get("keyword_score"),
            "semantic_score": item.get("semantic_score"),
        })

    return merged_results


# ---------------------------------------------------------------------------
# High-Level Hybrid Retrieval Interface
# ---------------------------------------------------------------------------

def hybrid_search(
    query: str,
    db_path: str | Path,
    limit: int = 5,
    model_name: str = EMBEDDING_MODEL,
    auto_index: bool = True,
) -> list[dict[str, Any]]:
    """
    Execute hybrid search combining FTS5 keyword retrieval and local vector similarity.
    Automatically indexes un-embedded chunks when auto_index is True.
    """
    with connect(db_path) as conn:
        init_embeddings_table(conn)

        if auto_index:
            try:
                index_missing_chunks(conn, model_name=model_name)
            except Exception as exc:
                log.warning(f"Auto-indexing warning: {exc}")

        # Lexical retrieval
        kw_results = keyword_search(conn, query, limit=CANDIDATE_LIMIT)

        # Semantic retrieval
        sem_results = semantic_search(conn, query, limit=CANDIDATE_LIMIT, model_name=model_name)

        # Fuse rankings
        fused = reciprocal_rank_fusion(kw_results, sem_results, k=RRF_K, limit=limit)

        return fused


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Universal Intelligence — Semantic Knowledge Engine")
    parser.add_argument("--db", type=str, default="data/knowledge.db", help="Path to knowledge.db SQLite file")
    parser.add_argument("--reindex", action="store_true", help="Delete and recompute embeddings for the active model")
    parser.add_argument("--query", type=str, default="", help="Test query to search against the knowledge base")
    parser.add_argument("--model", type=str, default=EMBEDDING_MODEL, help="Embedding model name")
    parser.add_argument("--limit", type=int, default=5, help="Number of results to return")

    args = parser.parse_args()
    db_file = Path(args.db)

    print(f"[Semantic Knowledge Engine] Database: {db_file.resolve()}")
    print(f"[Semantic Knowledge Engine] Embedding Model: {args.model}")

    with connect(db_file) as conn:
        init_embeddings_table(conn)

        if args.reindex:
            count = reindex_all_chunks(conn, model_name=args.model)
            print(f"[Reindex Complete] Recomputed {count} chunk embeddings.")
        else:
            count = index_missing_chunks(conn, model_name=args.model)
            print(f"[Index Check] Indexed {count} missing chunk embeddings.")

        if args.query.strip():
            print(f"\nSearching for: '{args.query}'...")
            results = hybrid_search(args.query, db_file, limit=args.limit, model_name=args.model, auto_index=False)
            print(f"Found {len(results)} matches:\n")
            for idx, r in enumerate(results, start=1):
                print(f"{idx}. [{r['filename']} #chunk{r['chunk_index']}] (RRF: {r['rrf_score']}, SemRank: {r['semantic_rank']}, KWRank: {r['keyword_rank']})")
                print(f"   {r['content'][:140]}...\n")


if __name__ == "__main__":
    main()
