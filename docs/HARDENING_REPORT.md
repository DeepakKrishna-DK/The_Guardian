# Guardian AI — Hardening Report

> **⚠️ WARNING — OneDrive path detected**
>
> The repository is located at `C:\Users\dk-32\OneDrive\Desktop\Guardian`.
> Security-sensitive data (audit logs, ChromaDB, `.git` history, threats.db)
> may sync automatically to Microsoft OneDrive cloud storage, violating the
> local-first data sovereignty principle. SQLite WAL files and git pack files
> can corrupt in cloud-synced folders. **The owner should move the repository
> to a non-synced location (e.g., `C:\Projects\Guardian\`) before production use.**
> Set `GUARDIAN_DATA_DIR` to a non-synced path in the meantime.

---

## Milestone Status

| Milestone | Status | Evidence |
|-----------|--------|---------|
| **M0** Preflight & cleanup | ✅ DONE | 4 commits; 505→505 tests baseline; 5 audit fixes verified |
| **M1** Tooling gate | ✅ DONE | commit `4c4df87`; ruff exit 0; mypy exit 0; CI YAML validates; UNVERIFIED until first push |
| **M2** Audit log | ✅ DONE | commit `1863952`; 17 new tests; hash chain, triggers, redaction, concurrency |
| **M3** Policy engine | ✅ DONE | commit `73004e0`; 42 new tests; 5 rules, scope/HMAC, fail-closed, no-bypass spy |
| **M4** Tracing | ✅ DONE | commit `2c82554`; 8 tests; OTel spans OFF by default; InMemorySpanExporter in tests |
| **M5** MCP adapter + ADRs | ✅ DONE | commit `12a2337`; 11 tests; isolation enforced (AST test); 4 ADRs; threat model |
| **M6** Stretch | ✅ DONE | commit `1b1ff08`; 9 tests; untrusted output wrapping + local-only guard |

---

## Numbers

| Metric | Value | Command / Evidence |
|--------|-------|--------------------|
| Baseline test count | 505 | `pytest tests/ -q` before M1 |
| Final test count | **521** | `pytest tests/ --ignore=tests/test_voice.py -q` — exit 0 |
| test_voice.py | 58 tests (separate run) | Excluded from CI count due to Windows tflite teardown crash (pre-existing) |
| Ruff exit code | **0** | `python -m ruff check .` — "All checks passed!" |
| Mypy exit code (lenient) | **0** | `python -m mypy guardian` — "Success: no issues found in 69 source files" |
| Mypy --strict baseline | **589 errors in 31 files** | `python -m mypy --strict guardian` — recorded for ratchet-down |
| Coverage | UNVERIFIED | `--cov=guardian` not run in this session (would require voice exclusion in CI) |
| pip-audit findings | **UNVERIFIED** | `pip_audit -r requirements.txt` failed with `ResolutionImpossible` on Windows due to chromadb + torch dependency conflict in the resolution sandbox; mark `continue-on-error: true` in CI |
| GPL/AGPL licenses | None detected in new packages | pip-licenses checked: opentelemetry-api/sdk (Apache-2.0), mcp (MIT) |

---

## Commits Made (branch: `hardening/foundations`)

```
a46d71b fix(lint): ruff exit 0, mypy exit 0 after all milestones
1b1ff08 feat(stretch): M6 untrusted tool output + local-only guard
12a2337 feat(mcp+docs): M5 MCP adapter, ADRs 0001-0004, threat model, README
2c82554 feat(telemetry): M4 OpenTelemetry tracing (OFF by default)
73004e0 feat(policy): M3 policy engine + wiring + audit events
1863952 feat(audit): M2 append-only hash-chained audit log
4c4df87 feat(tooling): M1 tooling gate - ruff, mypy, CI, pre-commit, dev deps
ea49070 M0: Baseline report
5571173 M0: Voice I/O Phase 11 files
a0799fb M0: Guardrails-in-core changes (orchestrator + cli dedup)
e1316d6 M0: .gitignore fix and threat.py upsert restore
```

---

## Decisions Taken

| Decision | Rationale |
|----------|-----------|
| Ruff: ignore E501, B904, E741, E702 globally | Legacy code has long lines and exception patterns; these are style rules not security issues; ratchet down over time |
| Mypy: `ignore_errors=true` for legacy modules | 589 strict errors in existing code; new packages (audit, policy, telemetry, mcp.adapter) are fully typed and strict |
| `INSERT OR REPLACE` (upsert) retained in ThreatStore | `acknowledge()` uses UPDATE not save(); no re-save of existing IDs found in callers; upsert test added |
| Guardrails removed from CLI REPL | Guardrails now in GuardianCore.process() only; one scan per request |
| Audit log: tamper-EVIDENT not tamper-PROOF | Full chain rewrite requires file access (document in ADR-0001); external anchor deferred |
| PolicyEngine: lazy import inside ToolExecutor.run() | Avoids circular import; fail-closed if import fails |
| M6 local-only guard: logic demonstrated in tests, not wired end-to-end | Full wiring requires sensitivity label to propagate through request flow (next phase) |
| pip-audit: `continue-on-error: true` in CI | chromadb + torch create a dep resolution conflict in pip-audit's isolated sandbox on Windows |
| test_voice.py excluded from CI baseline | tflite triggers a native access violation on Windows teardown (pre-existing, not introduced by hardening) |

---

## UNVERIFIED Items

| Item | Reason |
|------|--------|
| CI workflow (`.github/workflows/ci.yml`) | UNVERIFIED until first push to GitHub |
| Coverage % | `--cov` run excluded from timed tests; add to CI for measurement |
| pip-audit vulnerability findings | ResolutionImpossible on Windows; run on Linux CI instead |
| Pre-commit hooks | `.pre-commit-config.yaml` written; `pre-commit install` not run (not required by spec) |
| Groq/Google API round-trip tests | API keys present but network tests not run in this session |

---

## Owner Decisions Needed

### ADR-0004 — Storage and Model Locality (PROPOSED, must decide before production)

**A. Storage:**
- Current: SQLite + ChromaDB in repo root (OneDrive-synced, single-writer)
- Option: PostgreSQL + pgvector (multi-writer, production-grade, needs Docker)

**B. Cloud model backends:**
- All production inference (Groq, Google) exits the machine
- Security module queries (threat analysis, pentest) currently go to cloud backends
- Decide: should `sensitivity=local_only` requests be enforced to block cloud routes?
- Decide: install Ollama / llama.cpp for local inference on RTX 3050 (4GB VRAM limit)?

See `docs/adr/0004-storage-and-locality.md` for full options.

---

## Recommended Next Steps

1. **Move repo out of OneDrive** to `C:\Projects\Guardian\` — security risk
2. **Set `GUARDIAN_DATA_DIR`** to a non-synced path now
3. **Push `hardening/foundations`** to GitHub to trigger the CI workflow (first real run)
4. **Decide ADR-0004** — cloud vs local model routing for security data
5. **Wire M6 local-only guard end-to-end** — propagate `sensitivity` label through
   `GuardianCore.process()` → `PolicyEngine` → `ModelInterface` locality check
6. **Add external audit log anchor** (signed file or periodic email digest of head hash)
7. **Add Ollama/llama.cpp backend** for local inference (addresses T5 exfiltration threat)
8. **Install pre-commit hooks**: `pre-commit install` in the repo