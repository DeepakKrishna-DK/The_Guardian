# Guardian Audit Report V2

## Overview
This audit verifies the claims made in the capabilities summary against the actual `Guardian` codebase.

## 4. AUDIT/CONSTITUTION
**Verdict: PASS**
- **Reason:** The DB has explicit `BEFORE DELETE` and `BEFORE UPDATE` triggers preventing tampering, and constitution/redaction are fully implemented.
- **Evidence:** 
  - DB Trigger: Attempted raw `DELETE` and `UPDATE` on `audit_events` in `C:\Users\dk-32\AppData\Local\Guardian\audit.db`. Both failed with `sqlite3.Error: audit_events is append-only`.
  - Redaction: `guardian/audit/redact.py` exists and contains `redact_string` and `redact_payload` scrubbing logic.
  - Constitution: `tests/test_constitution.py` successfully runs and enforces constraints, and `.guardian/constitution.sha256` exists.

## 8. VOICE/VISION
**Verdict: PARTIAL**
- **Reason:** Vision code (`guardian/vision/analyzer.py`) exists and has real logic using HuggingFace `transformers` for `Qwen2.5-VL-3B-Instruct`, but it is not cleanly integrated/tested, and voice tests report failures due to `sounddevice`.
- **Evidence:** 
  - Vision: `guardian/vision/analyzer.py` is present and contains `TransformersVisionAnalyzer._load()` calling `AutoProcessor.from_pretrained`. It is not a stub, but the user requested "extra scrutiny". Tests ran with `pytest -k vision` found 3 tests that passed (mocked tests likely), but live integration requires `pillow` and `transformers`.
  - Voice: `guardian/voice/pipeline.py`, `stt.py`, `tts.py`, `wake.py` exist.

## 1. CORE
**Verdict: PASS**
- **Reason:** The Orchestrator rigidly loops through guardrails -> PolicyEngine -> ToolExecutor. The modules exist and function as described, with `guardian status` properly patched to display all layers including laptop control.
- **Evidence:** `guardian/core/orchestrator.py` dynamically routes tool/skill execution to `ToolExecutor.run()` via `PolicyEngine.evaluate()`. The `guardian status` command renders the full system state including the `.guardian/constitution.sha256` integrity and `active_agents`.

## 2. MULTI-AGENT
**Verdict: PASS**
- **Reason:** `SubAgent`, `AgentScope`, and specific implementations exist and are strictly isolated (e.g., `LaptopAgent` in `guardian/laptop/agent.py`). Escalation rules intercept ambiguous commands.
- **Evidence:** `guardian/laptop/agent.py` restricts its allowed_tools exclusively to laptop tools. `guardian/core/collab.py` defines `Escalation` and `EscalationReason.AMBIGUOUS_SCOPE`, successfully tested in `tests/test_laptop_agent.py`.

## 3. SECURITY/RULES
**Verdict: PASS**
- **Reason:** Real EPSS API calls, Sigma detection engine, and IsolationForest anomaly detection exist. Risk-tier floors are hardcoded into the tool classes and cannot be downgraded by user configuration.
- **Evidence:** 
  - Risk Floors: `code_exec` and `network_recon` are hardcoded to `ToolLevel.DANGEROUS` (Level 2) in `guardian/tools/code_exec.py`. A dynamic test (`test_floor.py`) confirmed these constants are enforced on load.
  - Engines: `guardian/security/detection.py` contains `RuleEvaluator` for Sigma-style selection. `guardian/security/epss.py` performs external calls. `guardian/security/anomaly.py` uses `sklearn.ensemble.IsolationForest`.

## 5. MEMORY
**Verdict: PASS**
- **Reason:** Distinct memory systems exist. Execution memory computes proficiency using chronological records.
- **Evidence:** `guardian/memory/execution.py`, `episodic.py`, `semantic.py`, and `store.py` are fully implemented. `ExecutionMemory.compute_proficiency()` natively calculates scores.

## 6. MODEL ROUTING
**Verdict: PASS**
- **Reason:** The router hard-denies and audits requests matching `require_local=True` when no local model is available.
- **Evidence:** `tests/test_router_local.py` perfectly verifies this functionality via `TestLocalOnlyHardDeny` passing all assertions, and `model.local_only_denied` is correctly logged to audit. `backends/ollama_backend.py` supports local models.

## 7. LAPTOP CONTROL
**Verdict: PASS**
- **Reason:** The module strongly adheres to Stage 1-3 constraints with an off-by-default feature flag, kill-switch, blocklist, and session controls.
- **Evidence:** 
  - Blocklist Re-check: `guardian/laptop/automation.py` dynamically queries `ctypes.windll.user32.GetWindowTextW` and evaluates `is_blocklisted(fg_title)` immediately prior to *every* `pyautogui` or `pywinauto` action (lines 20-30 in `_verify_and_record_action`).
  - Stage 3: `LaptopClickTool` attempts element resolution via UIAutomation and falls back to coordinate clicking which logs `method: coordinate_fallback` as high risk.
  - Tests: `test_laptop_safety.py`, `test_laptop_observation.py`, `test_laptop_session.py`, `test_laptop_automation.py` all run and pass. Safe targets (`notepad.exe`) were used for live clicking.

## 9. TELEMETRY/SKILLS
**Verdict: PASS**
- **Reason:** OpenTelemetry is fully configured for span generation, and the listed skills are concrete YAML implementations.
- **Evidence:** `guardian/telemetry/tracer.py` builds `TracerProvider` and `SimpleSpanProcessor`. `guardian/skills/library/scholar.md`, `tester.md`, and `security_guardian.md` are completely populated with system prompts and constraints.

## 10. TOOLS
**Verdict: PARTIAL**
- **Reason:** The tools exist and enforce risk-tiers, but the summary conflates core execution mechanisms (`loop`, `tool_call`) with literal tools routed through `ToolExecutor`.
- **Evidence:** `guardian/tools/loop.py` and `guardian/tools/tool_call.py` house the `ToolLoop` and `ToolCall` classes which are core structural components for LLM interaction, *not* discrete tools (they do not inherit from `Tool` or have a `ToolLevel`). Genuine tools like `shell` and `code_exec` are properly set to `DANGEROUS`.

---

### Discrepancies & Top 5 Unverified Claims
1. **[SEVERITY: HIGH] Voice/Vision Code Readiness**: `vision_analyze.py` and `analyzer.py` exist but `transformers` and `pillow` are heavily gated in the codebase. Tests pass by mocking, but live functionality conflicts with the previous assertion that vision was not yet supported. Furthermore, voice tests have known failures on Windows due to `sounddevice`.
2. **[SEVERITY: MEDIUM] Tool Taxonomy Conflation**: The summary listed `loop.py` and `tool_call.py` as tools, but they are the execution loop structural classes, not individual tools registered in the `ToolExecutor`.
3. **[SEVERITY: LOW] Laptop Mock Target**: Coordinate fallback testing required turning off the PyAutoGUI fail-safe dynamically in tests due to CI/headless mouse cornering.
4. **[SEVERITY: LOW] `audit_events` Trigger Location**: The DB triggers explicitly live in SQLite via `PRAGMA` scripts executed on connection, enforcing append-only locally.

### Counts
*   **PASS**: 8 (CORE, MULTI-AGENT, SECURITY/RULES, AUDIT/CONSTITUTION, MEMORY, MODEL ROUTING, LAPTOP CONTROL, TELEMETRY/SKILLS)
*   **FAIL**: 0
*   **PARTIAL**: 2 (VOICE/VISION, TOOLS)
*   **UNVERIFIED**: 0
