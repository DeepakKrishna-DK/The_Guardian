# ADR-0004: Storage Decision — Remain on SQLite + ChromaDB

| Field    | Value                          |
|----------|-------------------------------|
| Status   | ACCEPTED                       |
| Date     | 2026-09-26                     |
| Deciders | Project owner + lead engineer  |
| Supersedes | docs/adr/0004-storage-and-locality.md (PROPOSED) |

## Context

Guardian is a local-first single-user AI platform. It uses two storage
engines:

| Store | Technology | Location |
|-------|-----------|---------|
| Audit log | SQLite (`audit.db`) | `GUARDIAN_DATA_DIR` (default: `%LOCALAPPDATA%\Guardian`) |
| Threat intelligence | SQLite (`threats.db`) | `GUARDIAN_DATA_DIR` |
| Session memory | SQLite (`memory.db`) | `guardian/memory/` |
| Vector store (knowledge) | ChromaDB | `/knowledge/chroma.db` |

The previous ADR-0004 (now superseded) posed this as an open PROPOSED
decision between SQLite+ChromaDB and PostgreSQL+pgvector. The owner has
reviewed the options and made a decision.

## Decision

**Remain on SQLite + ChromaDB for all storage.**

## Reasoning

1. **Single-user, single-process**: Guardian runs as one process per user
   session. There is no concurrent writer scenario at present. SQLite
   handles single-writer workloads reliably with WAL mode enabled.

2. **Operational simplicity**: PostgreSQL requires Docker, a running server
   process, connection pooling, and schema migrations. None of these provide
   present value for a local-first desktop deployment.

3. **Zero external infrastructure**: ChromaDB runs in-process. SQLite is
   Python stdlib. No port exposure, no service management, no network
   attack surface.

4. **Audit log isolation**: The audit log intentionally uses its own SQLite
   file (not shared with ThreatStore or memory). This provides fault
   isolation: ThreatStore corruption cannot affect audit integrity.

5. **pgvector would require Docker**: The owner has confirmed Docker is not
   required for this deployment. pgvector is not available as a pure-Python
   in-process library.

## Constraints Accepted

| Constraint | Impact | Mitigation |
|-----------|--------|-----------|
| SQLite single-writer | Concurrent processes (e.g. CLI + background audit writer) would contend | Each store has its own file; `BEGIN IMMEDIATE` transactions in audit log prevent deadlock |
| ChromaDB not production-hardened | Acceptable for single-user | Data dir outside repo; `/knowledge/` in `.gitignore` |
| OneDrive sync risk | SQLite WAL files corrupt if synced mid-write | Documented in HARDENING_REPORT.md; owner action required to move repo |
| ChromaDB in repo root | Sensitive documents may sync to cloud | Owner action: set `GUARDIAN_DATA_DIR` to a non-synced path |

## Explicit Revisit Triggers

This decision **must be revisited** if any of the following occur:

1. **Write-lock contention observed** between two concurrent processes
   (e.g. audit writer + CLI + background knowledge ingestion all active)
   causing `OperationalError: database is locked`
2. **Multi-user requirement** — more than one person uses the same Guardian
   instance simultaneously
3. **Production/server deployment** — Guardian moved from desktop to a
   server or container environment
4. **Knowledge base >100 GB** — ChromaDB may not scale beyond this without
   external vector store

When triggered: evaluate PostgreSQL + pgvector (managed or Docker-based)
as the upgrade path.

## Alternatives Considered and Rejected

| Option | Rejected because |
|--------|-----------------|
| PostgreSQL + pgvector | Requires Docker/ops overhead with no present benefit; violates local-first simplicity |
| SQLite + sqlite-vss (vector extension) | Experimental; not well-maintained; ChromaDB already in use |
| Qdrant (local) | Another binary to install and manage; no advantage over ChromaDB in-process |
| DuckDB + HNSW | Interesting but immature for production vector workloads |

## Implementation Notes

No code changes required. This ADR formalizes the status quo.

Monitor: if `OperationalError: database is locked` appears in logs,
investigate whether a second process is holding a write lock before
escalating to a storage engine change.
