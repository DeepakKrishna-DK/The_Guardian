# Guardian — Unified AI Platform

A modular, local-first AI platform with 6 capability modules:

1. **General assistant core** — agentic orchestration, tool-calling, memory
2. **Security module** — AI/LLM security (guardrails, prompt-injection defense, vuln scanning)
3. **Voice I/O** — local STT/TTS, wake-word, offline-capable
4. **Vision I/O** — image/document understanding (planned)
5. **Knowledge layer** — RAG + knowledge graph over own documents
6. **Pentest copilot** — natural-language interface over authorized testing tools

## License

Apache-2.0 — see [LICENSE](LICENSE).

GPL/AGPL components (Piper, ComfyUI, Wazuh, Neo4j) run as **separate processes only**, never imported.

## Setup

```bash
# Requires Python 3.13
python -m venv venv
venv\Scripts\activate        # Windows
pip install -e .
pip install -r requirements-dev.txt  # dev tools: ruff, mypy, pytest-cov, etc.
```

## Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `GUARDIAN_GROQ_API_KEY` | Groq API key for cloud LLM | — |
| `GUARDIAN_GOOGLE_API_KEY` | Google Gemini API key | — |
| `GUARDIAN_PIPER_PATH` | Path to Piper TTS binary (optional) | — |
| `GUARDIAN_DATA_DIR` | Runtime data directory (audit DB, etc.) | `%LOCALAPPDATA%\Guardian` (Win) / `~/.local/share/guardian` |
| `GUARDIAN_OTEL_EXPORTER` | OpenTelemetry exporter: `none` (default) or `console` | `none` |
| `GUARDIAN_SCOPE_FILE` | Path to JSON pentest scope file | — |
| `GUARDIAN_SCOPE_HMAC_KEY` | HMAC-SHA256 key for scope signature verification | — |

Set as **User environment variables** (never in code or `.env` files committed to git).
Copy `.env.example` to `.env` locally (`.env` is already in `.gitignore`).

> **Warning**: if the repo is inside an OneDrive folder, runtime data
> (audit.db, ChromaDB, `.git` history) may sync to the cloud and SQLite
> WAL files can corrupt. Set `GUARDIAN_DATA_DIR` to a non-synced path and
> move the repo outside OneDrive when practical.

## Tests

```bash
# Windows — PYTHONNOUSERSITE avoids chromadb conflict from user site-packages
set PYTHONNOUSERSITE=1
python -m pytest tests/ -q --tb=short

# With coverage
python -m pytest tests/ -q --cov=guardian --cov-report=term-missing
```

## Lint and Type Checks

```bash
# Lint (ruff — must pass CI)
python -m ruff check .

# Type check (mypy — lenient global, strict for new packages)
python -m mypy guardian

# Security audit of dependencies
pip-audit -r requirements.txt

# License check
pip-licenses --format=markdown
```

## CLI

```bash
guardian status              # System status
guardian chat                # Interactive chat (--agentic for tool use)
guardian security audit      # Security self-audit
guardian knowledge ingest .  # Ingest documents
guardian guardrails scan "text"  # Scan for threats
guardian voice status        # Voice I/O backends
```

## Architecture

- **Thin core** with ports/adapters: LLM, tools, memory, guardrails behind ABCs
- **Local hub** is source of truth; cloud = stateless GPU workers (planned)
- **MCP** for the control plane — `guardian/mcp/adapter.py` is the sole SDK entry point
- **PolicyEngine** — single choke-point for every tool call (`guardian/policy/`)
- **Audit log** — append-only, hash-chained SQLite (`guardian/audit/`)
- **Guardrails** on every input/output path (regex patterns, configurable rails)
- **Tool sandbox** with authority levels (L0=read, L1=write+approval, L2=dangerous+confirmation)
- **Telemetry** — OpenTelemetry, OFF by default (`guardian/telemetry/`)

## Hardening

See [`docs/HARDENING_REPORT.md`](docs/HARDENING_REPORT.md) for milestone status and metrics.
See [`docs/adr/`](docs/adr/) for architecture decision records.
See [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) for threat model v0.