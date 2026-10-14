"""
Universal Intelligence AI — Local Integration Application
==========================================================
Unified FastAPI service connecting:
  1. Open-weight LLM inference (OpenAI-compatible hosted API or Guardian local router)
  2. Academic research discovery (OpenAlex + Crossref)
  3. Live web intelligence (Tavily / Brave / fallback)
  4. Local knowledge persistence (SQLite FTS5 full-text search)

Run locally:
    uvicorn app:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from guardian.logging.logger import get_logger
from guardian.prompts import UIRA_MASTER_SYSTEM_PROMPT_V1
from guardian.research.academic import AcademicResearchClient
from guardian.web.search import WebSearchClient
from guardian.web.security import sanitize_web_content

load_dotenv()
log = get_logger("universal_ai_app")

# ---------------------------------------------------------------------------
# Configuration & Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/knowledge.db")
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIRECTORY", "data/uploads")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
MAX_EXTRACTED_CHARS = 500_000
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150

# Model configuration
MODEL_BASE_URL = os.getenv("MODEL_BASE_URL", "").strip()
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "").strip()
MODEL_NAME = os.getenv("MODEL_NAME", "llama3.2:3b").strip()

# System prompt — UIRA Master System Prompt Version 1.0
UNIVERSAL_SYSTEM_PROMPT = UIRA_MASTER_SYSTEM_PROMPT_V1


# ---------------------------------------------------------------------------
# SQLite Knowledge Storage (FTS5)
# ---------------------------------------------------------------------------

def get_db_connection() -> sqlite3.Connection:
    """Open SQLite connection with row factory enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQLite tables and FTS5 full-text index."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as conn:
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
        conn.commit()
    log.info(f"Database initialized at: {DB_PATH}")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping character blocks."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    chunks = []
    start = 0
    while start < len(cleaned):
        end = start + chunk_size
        chunks.append(cleaned[start:end])
        start += chunk_size - overlap
    return chunks


def search_local_knowledge(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Query SQLite FTS5 table for matching document chunks."""
    cleaned_query = re.sub(r"[^\w\s]", "", query).strip()
    if not cleaned_query:
        return []

    # FTS query tokens joined by OR
    fts_tokens = " OR ".join(cleaned_query.split()[:8])
    results = []

    with get_db_connection() as conn:
        try:
            cursor = conn.execute("""
                SELECT c.content, c.chunk_index, d.filename, d.id as doc_id, rank
                FROM chunks_fts(?) f
                JOIN chunks c ON c.document_id = f.document_id AND c.chunk_index = f.chunk_index
                JOIN documents d ON d.id = c.document_id
                ORDER BY rank
                LIMIT ?
            """, (fts_tokens, limit))
            for row in cursor.fetchall():
                results.append({
                    "content": row["content"],
                    "filename": row["filename"],
                    "document_id": row["doc_id"],
                    "chunk_index": row["chunk_index"],
                    "score": round(-float(row["rank"]), 3) if row["rank"] is not None else 1.0,
                })
        except sqlite3.OperationalError as e:
            log.warning(f"FTS search error ({e}), falling back to LIKE...")
            cursor = conn.execute("""
                SELECT c.content, c.chunk_index, d.filename, d.id as doc_id
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.content LIKE ?
                LIMIT ?
            """, (f"%{cleaned_query[:30]}%", limit))
            for row in cursor.fetchall():
                results.append({
                    "content": row["content"],
                    "filename": row["filename"],
                    "document_id": row["doc_id"],
                    "chunk_index": row["chunk_index"],
                    "score": 0.5,
                })

    return results


# ---------------------------------------------------------------------------
# LLM Generation Client
# ---------------------------------------------------------------------------

def generate_llm_answer(prompt: str, system_prompt: str = UNIVERSAL_SYSTEM_PROMPT, max_tokens: int = 1500) -> str:
    """
    Generate an answer via hosted OpenAI-compatible inference API
    or Guardian's multi-backend router fallback.
    """
    # 1. Direct OpenAI-compatible hosted API
    if MODEL_BASE_URL and MODEL_API_KEY:
        try:
            try:
                from openai import OpenAI
                client = OpenAI(base_url=MODEL_BASE_URL, api_key=MODEL_API_KEY)
                resp = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=max_tokens,
                )
                content = resp.choices[0].message.content
                if content:
                    return content
            except ImportError:
                endpoint = MODEL_BASE_URL.rstrip("/") + "/chat/completions"
                headers = {"Authorization": f"Bearer {MODEL_API_KEY}", "Content-Type": "application/json"}
                payload = {
                    "model": MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": max_tokens,
                }
                with httpx.Client(timeout=30.0) as http_client:
                    r = http_client.post(endpoint, headers=headers, json=payload)
                    r.raise_for_status()
                    data = r.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            log.warning(f"Hosted model API call failed ({e}), falling back to Guardian model backend...")

    # 2. Guardian Local Multi-Backend Fallback (Ollama / Groq / Gemini / Mock)
    try:
        from guardian.model.interface import Message, ModelRequest, Role
        from guardian.model.registry import get_model

        model = get_model()
        req = ModelRequest(
            messages=[
                Message(role=Role.SYSTEM, content=system_prompt),
                Message(role=Role.USER, content=prompt),
            ],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        resp = model.complete(req)
        return resp.content
    except Exception as e:
        log.error(f"All model backends failed: {e}")
        return f"Model inference error: {e}. (Ensure MODEL_BASE_URL or local Ollama is active)."


# ---------------------------------------------------------------------------
# Pydantic Request / Response Schemas
# ---------------------------------------------------------------------------

class IngestTextRequest(BaseModel):
    filename: str = Field(..., description="Document name or identifier (e.g. ai-principles.md)")
    text: str = Field(..., min_length=1, max_length=MAX_EXTRACTED_CHARS, description="Document body text")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=12000, description="The query or research question")
    use_knowledge: bool = Field(True, description="Search local SQLite document knowledge base")
    use_web: bool = Field(False, description="Search general web via search client")
    use_academic: bool = Field(False, description="Search academic research via OpenAlex and Crossref")
    max_sources: int = Field(5, ge=1, le=15, description="Maximum evidence items to retrieve per category")


# ---------------------------------------------------------------------------
# FastAPI Lifecycle & App Initialization
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    init_db()
    log.info("Universal Intelligence API ready.")
    yield


app = FastAPI(
    title="Universal Intelligence AI — Integration API",
    description="Multidisciplinary AI platform with live Web, Academic (OpenAlex/Crossref), and Local Knowledge retrieval.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "service": "Universal Intelligence AI",
        "documentation": "/docs",
        "health": "/health",
        "version": "1.0.0",
    }


@app.get("/health")
def health_check():
    """Reports system health, model status, search availability, and database metrics."""
    with get_db_connection() as conn:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    return {
        "status": "healthy",
        "model_configured": bool(MODEL_BASE_URL and MODEL_API_KEY),
        "model_name": MODEL_NAME,
        "web_search_available": bool(os.getenv("TAVILY_API_KEY") or os.getenv("BRAVE_API_KEY")),
        "academic_search_available": True,
        "database": {
            "path": str(DB_PATH),
            "documents_indexed": doc_count,
            "chunks_indexed": chunk_count,
        },
    }


@app.post("/ingest-text")
def ingest_text(req: IngestTextRequest):
    """Add a plain text or Markdown document to the local knowledge base."""
    chunks = chunk_text(req.text)
    if not chunks:
        raise HTTPException(status_code=400, detail="Provided text contains no extractable content.")

    doc_id = str(uuid.uuid4())[:12]
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    file_type = Path(req.filename).suffix.lstrip(".") or "txt"

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO documents (id, filename, file_type, uploaded_at, char_count, chunk_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (doc_id, req.filename, file_type, now_iso, len(req.text), len(chunks)))

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_{idx}"
            conn.execute("""
                INSERT INTO chunks (id, document_id, chunk_index, content)
                VALUES (?, ?, ?, ?)
            """, (chunk_id, doc_id, idx, chunk))
            conn.execute("""
                INSERT INTO chunks_fts (content, document_id, chunk_index)
                VALUES (?, ?, ?)
            """, (chunk, doc_id, idx))

        conn.commit()

    return {
        "status": "indexed",
        "document_id": doc_id,
        "filename": req.filename,
        "char_count": len(req.text),
        "chunk_count": len(chunks),
    }


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and ingest a document (TXT, Markdown, or PDF)."""
    filename = file.filename or "uploaded_file"
    file_bytes = await file.read()

    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum upload size ({MAX_UPLOAD_BYTES // (1024*1024)}MB)")

    extension = Path(filename).suffix.lower()
    extracted_text = ""

    # PDF extraction using pypdf or PyMuPDF
    if extension == ".pdf":
        try:
            try:
                import io
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                extracted_text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            except ImportError:
                import pymupdf
                doc = pymupdf.open(stream=file_bytes, filetype="pdf")
                extracted_text = "\n\n".join(doc[i].get_text() for i in range(len(doc)))
                doc.close()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF document: {e}")
    elif extension in (".txt", ".md", ".json", ".csv"):
        try:
            extracted_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            extracted_text = file_bytes.decode("latin-1", errors="replace")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}. Allowed: .txt, .md, .pdf")

    if not extracted_text.strip():
        raise HTTPException(status_code=400, detail="No readable text found in uploaded document.")

    # Save to disk
    save_path = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{filename}"
    save_path.write_bytes(file_bytes)

    # Ingest text
    chunks = chunk_text(extracted_text)
    doc_id = str(uuid.uuid4())[:12]
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO documents (id, filename, file_type, uploaded_at, char_count, chunk_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (doc_id, filename, extension.lstrip("."), now_iso, len(extracted_text), len(chunks)))

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_{idx}"
            conn.execute("""
                INSERT INTO chunks (id, document_id, chunk_index, content)
                VALUES (?, ?, ?, ?)
            """, (chunk_id, doc_id, idx, chunk))
            conn.execute("""
                INSERT INTO chunks_fts (content, document_id, chunk_index)
                VALUES (?, ?, ?)
            """, (chunk, doc_id, idx))

        conn.commit()

    return {
        "status": "indexed",
        "document_id": doc_id,
        "filename": filename,
        "chunks_indexed": len(chunks),
        "file_size_bytes": len(file_bytes),
    }


@app.post("/ask")
async def ask_question(req: AskRequest):
    """
    Evidence-grounded question answering across Knowledge Base, Web, and Academic literature.
    """
    sources_collected: list[dict[str, Any]] = []
    evidence_blocks: list[str] = []
    research_status = {
        "knowledge_searched": False,
        "web_searched": False,
        "academic_searched": False,
    }

    # 1. Local Knowledge Base Search
    if req.use_knowledge:
        research_status["knowledge_searched"] = True
        kb_results = search_local_knowledge(req.question, limit=req.max_sources)
        if kb_results:
            kb_lines = []
            for r in kb_results:
                src_tag = f"[Knowledge: {r['filename']}#chunk{r['chunk_index']}]"
                sources_collected.append({
                    "type": "local_knowledge",
                    "identifier": src_tag,
                    "filename": r["filename"],
                    "content": r["content"],
                })
                kb_lines.append(f"{src_tag}\n{r['content']}")
            evidence_blocks.append("### Local Knowledge Excerpts:\n" + "\n\n".join(kb_lines))

    # 2. General Web Search
    if req.use_web:
        research_status["web_searched"] = True
        web_client = WebSearchClient()
        web_results = web_client.search(req.question, max_results=req.max_sources)
        if web_results:
            web_lines = []
            for w in web_results:
                src_tag = f"[Web: {w.domain}]"
                sources_collected.append({
                    "type": "web",
                    "identifier": src_tag,
                    "title": w.title,
                    "url": w.url,
                    "snippet": w.snippet,
                })
                web_lines.append(f"{src_tag} Title: {w.title} ({w.url})\nSummary: {w.snippet}")
            evidence_blocks.append("### Live Web Search Findings:\n" + "\n\n".join(web_lines))

    # 3. Academic Research Search (OpenAlex + Crossref)
    if req.use_academic:
        research_status["academic_searched"] = True
        academic_client = AcademicResearchClient()
        papers = academic_client.search(req.question, limit=req.max_sources)
        if papers:
            paper_lines = []
            for p in papers:
                doi_str = p.doi or "no-doi"
                src_tag = f"[Paper: {p.title[:40]}]"
                sources_collected.append({
                    "type": "academic_paper",
                    "identifier": src_tag,
                    "title": p.title,
                    "doi": p.doi,
                    "authors": p.authors,
                    "year": p.publication_date[:4] if p.publication_date else "n.d.",
                    "url": p.url,
                })
                paper_lines.append(
                    f"{src_tag} Title: {p.title}\n"
                    f"Authors: {', '.join(p.authors[:2])} | Date: {p.publication_date} | DOI: {doi_str}\n"
                    f"Abstract: {p.abstract[:350] or 'Metadata only'}"
                )
            evidence_blocks.append("### Peer-Reviewed Academic Literature:\n" + "\n\n".join(paper_lines))

    # Assemble Evidence Block
    if evidence_blocks:
        formatted_evidence = "\n\n---\n\n".join(evidence_blocks)
        prompt = (
            f"Question: {req.question}\n\n"
            f"[UNTRUSTED EVIDENCE - USE ONLY TO GROUND ANSWER]\n"
            f"{formatted_evidence}\n"
            f"[/UNTRUSTED EVIDENCE]\n\n"
            "Please provide a rigorous, evidence-backed synthesis answering the question. "
            "Cite sources using the explicit bracketed identifiers provided above. "
            "Disclose any limitations or gaps in the evidence."
        )
    else:
        prompt = (
            f"Question: {req.question}\n\n"
            "(No external evidence retrieved. Answer based on foundational principles and clearly state any uncertainty.)"
        )

    # Generate answer
    answer = generate_llm_answer(prompt, system_prompt=UNIVERSAL_SYSTEM_PROMPT)

    return {
        "answer": answer,
        "sources": sources_collected,
        "research_status": research_status,
    }


@app.get("/documents")
def list_documents():
    """List all indexed documents and their chunk counts."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT id, filename, file_type, uploaded_at, char_count, chunk_count FROM documents")
        docs = [dict(row) for row in cursor.fetchall()]
    return {"documents": docs, "total": len(docs)}
