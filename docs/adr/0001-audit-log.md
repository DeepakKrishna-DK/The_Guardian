# ADR-0001: Append-Only Hash-Chained Audit Log

| Field    | Value                          |
|----------|-------------------------------|
| Status   | ACCEPTED                       |
| Date     | 2026-09-22                     |
| Deciders | Project owner                  |

## Context

Guardian is a local-first AI platform that invokes cloud-backed LLMs and
executes system tools. Accountability requires a durable record of every
policy decision, tool invocation, model call, and guardrail event.

## Decision

Implement a separate append-only audit log (`guardian/audit/`) backed by
SQLite with:

1. **Hash chain**: each row stores `hash = sha256(prev_hash || canonical_json)`.
   Genesis `prev_hash = '0' * 64`.
2. **Append-only enforcement**: SQLite `BEFORE UPDATE` and `BEFORE DELETE`
   triggers raise `ABORT`. Direct DB writes can bypass this (see Consequences).
3. **Thread safety**: one `threading.Lock` + `BEGIN IMMEDIATE` transaction.
4. **`PRAGMA synchronous=FULL`** for durability.
5. **Payload redaction**: SECRET_LEAK patterns scrubbed before storage.
   Raw prompt/response text is never stored — only `{sha256, len, status,
   duration_ms}`.
6. **`verify_chain()`**: detects edited rows, missing rows, and seq gaps.

## Alternatives Considered

| Option | Rejected because |
|--------|-----------------|
| Append to ThreatStore | ThreatStore is a mutable working store (acknowledge(), status updates); mixing concerns breaks auditability |
| File-based append log | No atomic multi-writer guarantee; harder to query; SQLite is already a project dependency |
| Structured logging only | Log files are easy to truncate/rotate; no chain integrity |
| PostgreSQL + WAL | No Docker; adds external infrastructure for a local-first platform |

## Consequences

### Positive
- Chain integrity is verifiable without trusted third party.
- Separate store means audit log survives ThreatStore corruption.
- SQLite is already in stdlib (`sqlite3`); no new runtime dependency.

### Negative / Limitations

> **tamper-EVIDENT, not tamper-PROOF.** An attacker with write access to the
> DB file can drop the triggers, rewrite all rows, and rebuild a valid chain
> from genesis. Tail truncation is also undetected.

**Future work**: anchor the head hash externally (signed file, public ledger,
HSM, or periodic email digest) so chain rewrites are detectable.

## Compliance

Runtime data directory (default `%LOCALAPPDATA%\Guardian\audit.db`) is
outside the repository. Override with `GUARDIAN_DATA_DIR`. Tests must
use `tmp_path` only.
