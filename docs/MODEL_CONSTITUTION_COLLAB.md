# MODEL, CONSTITUTION & COLLABORATION PASS

## M0 Preflight Findings (2026-10-03)

### Baseline
- **Test suite**: 572 passed, 0 failed (excluding test_voice.py per known Windows CPython bug)
- **Branch**: `features/model-constitution-collab` from `features/rules-compliance` HEAD (commit 8ec33f1)

### Prior pass artifacts confirmed present

| Pass | Evidence |
|------|----------|
| `features/skills-tools-ai` | `guardian/model/router.py` with `CallType`+`ModelRouter`; commit `56ab2f1` (multi-model routing) |
| `features/voice-pass` | `guardian/core/presence_server.py`, `test_voice_pipeline.py`; commit `77b2b66` |
| `features/cognitive-pass` | `guardian/memory/episodic.py`, `guardian/core/planning.py`, `tests/agent_eval/`; commit `c748285` |
| `features/predictive-agents` | `guardian/core/agents.py`, `guardian/security/anomaly.py`, `guardian/security/epss.py`; commit `8ec33f1` |
| `features/rules-compliance` | `guardian/policy/compliance.py`, `guardian/policy/dsl.py`, `guardian/security/detection.py` — **IN WORKING TREE, NOT YET COMMITTED as separate branch** |

### Key findings vs. CONTEXT assumptions
1. **Ollama backend ALREADY EXISTS** at `guardian/model/backends/ollama_backend.py` using stdlib `urllib`, no `ollama` PyPI package.
2. **ModelRouter ALREADY EXISTS** in `guardian/model/router.py` with `require_local` hard-deny path.
3. **`evaluate_model_call` WIRED** in `guardian/core/orchestrator.py` — router is called with `skill_obj.local_only`.
4. **GUARDIAN_CONSTITUTION_v0.1.md** is the actual filename (not `GUARDIAN_CONSTITUTION.md`). Currently a text document only, no hash guard.
5. **Ollama `llama3.2:3b` (Q4_K_M)** is running locally. Measured first-call latency: **62,742 ms** (cold VRAM load). Subsequent calls will be faster. VRAM usage: ~2.0 GB (Q4_K_M 3B), fits within 4 GB constraint.
6. **No `ConstitutionCheck` suite exists** — must build.
7. **No collaboration/escalation protocol** exists — must build.
8. **Existing no-bypass spy tests** found in: `tests/test_agents.py`, `tests/test_m6_stretch.py` (local-only guard), `tests/test_m4_infra.py`.

### CONSTITUTION principals extracted from v0.1
- § 2.1 User Sovereignty: Level-2 actions require explicit approval
- § 2.2 Privacy by Default: local-only data never reaches cloud backends  
- § 2.5 Least Privilege: sub-agents get only required tool permissions
- § 2.7 Auditability: all tool calls produce audit log entries
- § 5 AI Security: audit log never contains raw prompt/response content

---

## [x] M0 - Preflight DONE (2026-10-03)

## [x] M1 - Local Model Routing
- Added `model.local_only_denied` audit event to `ModelRouter._audit_local_denied`.
- Ensured hard-deny path produces this audit event when `require_local=True` but no local backend is available.
- Created `tests/test_router_local.py` to verify routing paths, audit logging, and run a live Ollama test.

## [x] M2 - Enforceable Constitution
- Created `.guardian/constitution.sha256` hash guard file.
- Created `tests/test_constitution.py` with 6 core assertions mapping to constitutional rules:
  - **CC-1 Auditability**: Verified `tool.request` is always logged. Fixed `ToolExecutor` which was silently failing to log due to a `dict.get` call on a string context.
  - **CC-2 Privacy**: Added explicit redaction of `content`, `prompt`, `messages`, and `response` keys in `guardian.audit.redact.redact_payload` to ensure raw content never enters SQLite.
  - **CC-3 Least Privilege**: Verified sub-agent scope enforcement.
  - **CC-4 Local Only**: Verified cloud models are denied for local-only tasks.
  - **CC-5 Authority**: Verified Level 2 tools require explicit approval.
  - **Constitution Integrity**: Verified hash guard detects tampering.

## [x] M3 - Agent/Human Collaboration Protocol
- Created `guardian/core/collab.py` defining `Escalation`, `EscalationReason`, and `CollaborationSummary`.
- Modified `GuardianCore.process()` to verify user intent using `Planner.verify_plan` when the user requests an action (e.g. "scan", "execute"). 
- Added `Escalation` to `GuardianResponse` to surface clarifying questions to the human (e.g. ambiguous scope, policy approval required).
- Added `agent.handoff` audit logging and `record_agent_handoff`.
- Created `tests/test_collab.py` to verify the collaboration features.

## [x] M4 - Cross-link Router/Constitution
- Completed alongside M1/M2 (`TestCC4_LocalOnlyNeverCloud`).

## [x] M5 - Surface It
- Modified `guardian/core/status.py` and `guardian/cli.py` to render new layers in `guardian status`:
  - Rules & Compliance (DSL Rules, Detection Rules, Legal References)
  - Collaboration Protocol (Framework Status)
  - Constitution & Enforceability (Pass/Fail Hash Check)

## [ ] M6 - Constitution Diff (Stretch)
- Dropped due to time/credit constraints.

All tests pass. Session complete.
